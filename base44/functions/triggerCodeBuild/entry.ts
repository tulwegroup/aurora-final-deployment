/**
 * triggerCodeBuild — Build Aurora API using GitHub source + CodeBuild
 * Uses AWS CodeStar Connection (OAuth) for GitHub auth
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const BUILDSPEC = {
  version: '0.2',
  phases: {
    pre_build: {
      commands: [
        'echo "Logging in to Amazon ECR..."',
        'aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 368331615566.dkr.ecr.us-east-1.amazonaws.com',
      ]
    },
    build: {
      commands: [
        'echo "Building Docker image..."',
        'docker build -f Dockerfile.minimal -t 368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest .',
      ]
    },
    post_build: {
      commands: [
        'echo "Pushing image..."',
        'docker push 368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest',
      ]
    }
  }
};

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function hmacSHA256(key, data) {
  const cryptoKey = await crypto.subtle.importKey('raw', typeof key === 'string' ? new TextEncoder().encode(key) : key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data)));
}

function toHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function signV4({ method, host, path, body, region, service, accessKeyId, secretAccessKey }) {
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const bodyHash = await sha256Hex(body);
  const headers = { 'content-type': 'application/x-amz-json-1.1', 'host': host, 'x-amz-date': amzDate };
  const signedHeaders = Object.keys(headers).sort().join(';');
  const canonicalHeaders = Object.keys(headers).sort().map(k => `${k}:${headers[k]}`).join('\n') + '\n';
  const canonicalRequest = [method, path, '', canonicalHeaders, signedHeaders, bodyHash].join('\n');
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');
  const kDate = await hmacSHA256(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = await hmacSHA256(kDate, region);
  const kService = await hmacSHA256(kRegion, service);
  const kSigning = await hmacSHA256(kService, 'aws4_request');
  const signature = toHex(await hmacSHA256(kSigning, stringToSign));
  return { ...headers, authorization: `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}` };
}

async function awsRequest({ service, target, body, region, accessKeyId, secretAccessKey }) {
  const host = `${service}.${region}.amazonaws.com`;
  const bodyStr = JSON.stringify(body);
  const headers = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service, accessKeyId, secretAccessKey });
  headers['x-amz-target'] = target;
  const res = await fetch(`https://${host}/`, { method: 'POST', headers, body: bodyStr });
  const json = await res.json().catch(() => ({}));
  return { ok: res.status < 300, status: res.status, data: json, error: json.message };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') {
      return Response.json({ error: 'Forbidden' }, { status: 403 });
    }

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const codestarConnectionArn = Deno.env.get('CODESTAR_CONNECTION_ARN') || 'arn:aws:codestar-connections:us-east-1:368331615566:connection/aurora-github';
    const region = 'us-east-1';
    const accountId = '368331615566';
    const projectName = 'aurora-api-build';
    const creds = { region, accessKeyId, secretAccessKey };

    const body = await req.json().catch(() => ({}));
    const action = body.action || 'start';

    if (action === 'status') {
      const res = await awsRequest({
        service: 'codebuild',
        target: 'CodeBuild_20161006.ListBuildsForProject',
        body: { projectName, sortOrder: 'DESCENDING' },
        ...creds
      });

      if (!res.ok || !res.data.ids?.length) {
        return Response.json({ status: 'no_builds', builds: [] });
      }

      const batchRes = await awsRequest({
        service: 'codebuild',
        target: 'CodeBuild_20161006.BatchGetBuilds',
        body: { ids: res.data.ids.slice(0, 5) },
        ...creds
      });

      const builds = (batchRes.data.builds || []).map(b => ({
        id: b.id,
        status: b.buildStatus,
        phase: b.currentPhase,
        startTime: b.startTime,
        endTime: b.endTime,
        logs: b.logs?.deepLink,
      }));

      return Response.json({ status: 'ok', builds });
    }

    // Create or update project with CodeStar GitHub connection (OAuth)
    const projectDef = {
      name: projectName,
      source: {
        type: 'GITHUB',
        location: 'https://github.com/aurora-osi/aurora-osi-production',
        gitCloneDepth: 1,
        buildspec: JSON.stringify(BUILDSPEC),
        sourceIdentifier: codestarConnectionArn,
      },
      artifacts: { type: 'NO_ARTIFACTS' },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
        environmentVariables: [],
      },
      serviceRole: `arn:aws:iam::${accountId}:role/aurora-codebuild-role`,
      timeoutInMinutes: 30,
    };

    const updateRes = await awsRequest({
      service: 'codebuild',
      target: 'CodeBuild_20161006.UpdateProject',
      body: projectDef,
      ...creds
    });

    if (!updateRes.ok) {
      const createRes = await awsRequest({
        service: 'codebuild',
        target: 'CodeBuild_20161006.CreateProject',
        body: projectDef,
        ...creds
      });
      if (!createRes.ok) {
        return Response.json({ error: `Create failed: ${createRes.error}` }, { status: 500 });
      }
    }

    // Start build
    const buildRes = await awsRequest({
      service: 'codebuild',
      target: 'CodeBuild_20161006.StartBuild',
      body: { projectName, sourceVersion: 'refs/heads/main' },
      ...creds
    });

    if (!buildRes.ok) {
      return Response.json({ error: `Build start failed: ${buildRes.error}` }, { status: 500 });
    }

    const build = buildRes.data.build;
    return Response.json({
      status: 'success',
      message: 'Build started (GitHub OAuth via CodeStar Connection)',
      buildId: build.id,
      buildStatus: build.buildStatus,
      logsUrl: `https://console.aws.amazon.com/codesuite/codebuild/${accountId}/projects/${projectName}`,
      estimatedTime: '5-10 minutes',
      imageTag: `${accountId}.dkr.ecr.${region}.amazonaws.com/aurora-api:latest`,
    });

  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});