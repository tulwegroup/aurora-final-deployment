/**
 * triggerCodeBuild — Create CodeBuild project (if needed) and trigger a build
 * Pulls from GitHub, builds Docker image, pushes to ECR
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

async function hmacSHA256(key, data) {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    typeof key === 'string' ? new TextEncoder().encode(key) : key,
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  return new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data)));
}

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
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
  return { ok: res.status < 300, status: res.status, data: json };
}

async function iamRequest({ action, params, accessKeyId, secretAccessKey }) {
  const host = 'iam.amazonaws.com';
  const region = 'us-east-1';
  const service = 'iam';
  const urlParams = new URLSearchParams({ Action: action, Version: '2010-05-08', ...params });
  const bodyStr = urlParams.toString();

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const bodyHash = await sha256Hex(bodyStr);
  const contentType = 'application/x-www-form-urlencoded';
  const hdrs = { 'content-type': contentType, 'host': host, 'x-amz-date': amzDate };
  const signedHeaders = Object.keys(hdrs).sort().join(';');
  const canonicalHeaders = Object.keys(hdrs).sort().map(k => `${k}:${hdrs[k]}`).join('\n') + '\n';
  const canonicalRequest = ['POST', '/', '', canonicalHeaders, signedHeaders, bodyHash].join('\n');
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');
  const kDate = await hmacSHA256(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = await hmacSHA256(kDate, region);
  const kService = await hmacSHA256(kRegion, service);
  const kSigning = await hmacSHA256(kService, 'aws4_request');
  const signature = toHex(await hmacSHA256(kSigning, stringToSign));
  const authorization = `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  const res = await fetch(`https://${host}/`, {
    method: 'POST',
    headers: { 'content-type': contentType, 'host': host, 'x-amz-date': amzDate, 'authorization': authorization },
    body: bodyStr
  });
  const text = await res.text();
  return { ok: res.status < 300, text };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const githubToken = Deno.env.get('GITHUB_TOKEN');
    const region = 'us-east-1';
    const accountId = '368331615566';
    const repoUri = `${accountId}.dkr.ecr.${region}.amazonaws.com/aurora-api`;
    const projectName = 'aurora-api-build';
    const githubRepo = 'https://github.com/tulwegroup/aurora-final-deployment';
    const creds = { region, accessKeyId, secretAccessKey };

    const { action = 'start' } = await req.json().catch(() => ({}));

    // ── Get build status ──
    if (action === 'status') {
      const res = await awsRequest({
        service: 'codebuild', target: 'CodeBuild_20161006.ListBuildsForProject',
        body: { projectName, sortOrder: 'DESCENDING' }, ...creds
      });
      if (!res.ok || !res.data.ids?.length) return Response.json({ status: 'no_builds', builds: [] });

      const batchRes = await awsRequest({
        service: 'codebuild', target: 'CodeBuild_20161006.BatchGetBuilds',
        body: { ids: res.data.ids.slice(0, 5) }, ...creds
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

    // ── Create IAM role for CodeBuild ──
    const roleName = 'aurora-codebuild-role';
    const trustPolicy = JSON.stringify({
      Version: '2012-10-17',
      Statement: [{ Effect: 'Allow', Principal: { Service: 'codebuild.amazonaws.com' }, Action: 'sts:AssumeRole' }]
    });

    await iamRequest({
      action: 'CreateRole',
      params: { RoleName: roleName, AssumeRolePolicyDocument: trustPolicy },
      ...creds
    });

    // Attach policies
    for (const arn of [
      'arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser',
      'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess',
    ]) {
      await iamRequest({ action: 'AttachRolePolicy', params: { RoleName: roleName, PolicyArn: arn }, ...creds });
    }

    // Wait for IAM propagation (IAM is eventually consistent)
    await new Promise(r => setTimeout(r, 10000));

    // ── Register GitHub credentials ──
    await awsRequest({
      service: 'codebuild', target: 'CodeBuild_20161006.ImportSourceCredentials',
      body: { serverType: 'GITHUB', authType: 'PERSONAL_ACCESS_TOKEN', token: githubToken },
      ...creds
    });

    // ── Create CodeBuild project ──
    const buildspec = {
      version: '0.2',
      phases: {
        pre_build: {
          commands: [
            `aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${accountId}.dkr.ecr.${region}.amazonaws.com`,
            `docker pull public.ecr.aws/docker/library/python:3.11-slim`,
            `docker tag public.ecr.aws/docker/library/python:3.11-slim python:3.11-slim`
          ]
        },
        build: {
          commands: [
            // Write a patched Dockerfile that copies source BEFORE pip install
            `cat > /tmp/Dockerfile.patched << 'DOCKERFILE'\nFROM python:3.11-slim\nWORKDIR /app\nRUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*\nCOPY src/aurora_vnext/pyproject.toml ./\nRUN python3 -c "import tomllib, subprocess, sys; d=tomllib.load(open(\x27pyproject.toml\x27,\x27rb\x27)); deps=d.get(\x27project\x27,{}).get(\x27dependencies\x27,[]); subprocess.check_call([sys.executable,\x27-m\x27,\x27pip\x27,\x27install\x27,\x27--no-cache-dir\x27]+deps)"\nCOPY src/aurora_vnext/app ./app\nCOPY src/aurora_vnext/ ./\nEXPOSE 8000\nCMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\nDOCKERFILE`,
            `docker build -f /tmp/Dockerfile.patched -t ${repoUri}:latest -t ${repoUri}:$CODEBUILD_RESOLVED_SOURCE_VERSION .`
          ]
        },
        post_build: {
          commands: [
            `docker push ${repoUri}:latest`,
            `docker push ${repoUri}:$CODEBUILD_RESOLVED_SOURCE_VERSION`,
            `echo Build complete: ${repoUri}:latest`
          ]
        }
      }
    };

    // Update project if exists, create if not
    const updateRes = await awsRequest({
      service: 'codebuild', target: 'CodeBuild_20161006.UpdateProject',
      body: {
        name: projectName,
        source: {
          type: 'GITHUB',
          location: githubRepo,
          buildspec: JSON.stringify(buildspec),
        },
        artifacts: { type: 'NO_ARTIFACTS' },
        environment: {
          type: 'LINUX_CONTAINER',
          image: 'aws/codebuild/standard:7.0',
          computeType: 'BUILD_GENERAL1_MEDIUM',
          privilegedMode: true,
        },
        serviceRole: `arn:aws:iam::${accountId}:role/${roleName}`,
      },
      ...creds
    });

    if (!updateRes.ok) {
      // Project doesn't exist yet — create it
      const createRes = await awsRequest({
        service: 'codebuild', target: 'CodeBuild_20161006.CreateProject',
        body: {
          name: projectName,
          source: { type: 'GITHUB', location: githubRepo, buildspec: JSON.stringify(buildspec) },
          artifacts: { type: 'NO_ARTIFACTS' },
          environment: {
            type: 'LINUX_CONTAINER',
            image: 'aws/codebuild/standard:7.0',
            computeType: 'BUILD_GENERAL1_MEDIUM',
            privilegedMode: true,
          },
          serviceRole: `arn:aws:iam::${accountId}:role/${roleName}`,
          timeoutInMinutes: 30,
        },
        ...creds
      });
      if (!createRes.ok) {
        return Response.json({ error: `Failed to create/update project: ${JSON.stringify(createRes.data)}` }, { status: 500 });
      }
    }

    // ── Start the build ──
    const buildRes = await awsRequest({
      service: 'codebuild', target: 'CodeBuild_20161006.StartBuild',
      body: { projectName },
      ...creds
    });

    if (!buildRes.ok) {
      return Response.json({ error: `Failed to start build: ${JSON.stringify(buildRes.data)}` }, { status: 500 });
    }

    const build = buildRes.data.build;
    return Response.json({
      status: 'success',
      message: 'Build started! Docker image will be built from GitHub and pushed to ECR.',
      buildId: build.id,
      buildStatus: build.buildStatus,
      logsUrl: build.logs?.deepLink || `https://console.aws.amazon.com/codesuite/codebuild/${accountId}/projects/${projectName}/build/${encodeURIComponent(build.id)}/log`,
      estimatedTime: '5-10 minutes',
      imageTag: `${repoUri}:latest`,
    });

  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});