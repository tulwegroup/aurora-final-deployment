/**
 * auroraCreateBuildPipeline
 *
 * Creates a CodeBuild project using NO_SOURCE type with an inline buildspec
 * that clones aurora-final-deployment via HTTPS+token, builds the Dockerfile,
 * and pushes aurora-api:latest to ECR. Bypasses OAuth credential registration.
 *
 * Then immediately starts a build.
 *
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}
async function hmacSHA256(key, data) {
  const k = await crypto.subtle.importKey('raw', typeof key === 'string' ? new TextEncoder().encode(key) : key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(data)));
}
function toHex(b) { return Array.from(b).map(x => x.toString(16).padStart(2, '0')).join(''); }

async function signV4({ method, host, path, body, region, service, accessKeyId, secretAccessKey }) {
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const bodyHash = await sha256Hex(body);
  const baseHeaders = { 'content-type': 'application/x-amz-json-1.1', 'host': host, 'x-amz-date': amzDate };
  const sortedKeys = Object.keys(baseHeaders).sort();
  const signedHeaders = sortedKeys.join(';');
  const canonicalHeaders = sortedKeys.map(k => `${k}:${baseHeaders[k]}`).join('\n') + '\n';
  const canonicalRequest = [method, path, '', canonicalHeaders, signedHeaders, bodyHash].join('\n');
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');
  const kDate = await hmacSHA256(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = await hmacSHA256(kDate, region);
  const kService = await hmacSHA256(kRegion, service);
  const kSigning = await hmacSHA256(kService, 'aws4_request');
  const signature = toHex(await hmacSHA256(kSigning, stringToSign));
  return { ...baseHeaders, authorization: `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}` };
}

async function cbRequest({ action, body, region, accessKeyId, secretAccessKey }) {
  const host = `codebuild.${region}.amazonaws.com`;
  const bodyStr = JSON.stringify(body);
  const headers = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service: 'codebuild', accessKeyId, secretAccessKey });
  headers['X-Amz-Target'] = `CodeBuild_20161810.${action}`;
  const res = await fetch(`https://${host}/`, { method: 'POST', headers, body: bodyStr });
  const data = await res.json().catch(() => ({}));
  console.log(`[CB ${action}] status=${res.status} data=${JSON.stringify(data).slice(0, 300)}`);
  return { ok: res.ok, status: res.status, data };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const reqBody = await req.json().catch(() => ({}));
    const { action = 'create_and_build', start_only = false } = reqBody;

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const githubToken = Deno.env.get('GITHUB_PAT') || Deno.env.get('GITHUB_TOKEN');
    const region = 'us-east-1';
    const accountId = '368331615566';
    const ecrUri = `${accountId}.dkr.ecr.${region}.amazonaws.com/aurora-api`;
    const projectName = 'aurora-api-build';

    if (!accessKeyId || !secretAccessKey) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });
    if (!githubToken) return Response.json({ error: 'GITHUB_PAT or GITHUB_TOKEN not set' }, { status: 500 });

    const creds = { region, accessKeyId, secretAccessKey };

    // ── If start_only: just start build on existing project ───────────────
    if (start_only) {
      const startRes = await cbRequest({ action: 'StartBuild', body: { projectName }, ...creds });
      if (!startRes.ok) return Response.json({ error: 'Build start failed', detail: startRes.data }, { status: 500 });
      const build = startRes.data?.build;
      return Response.json({
        status: 'build_started',
        build_id: build?.id,
        build_status: build?.buildStatus,
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${projectName}`,
      });
    }

    // ── Inline buildspec using NO_SOURCE + git clone via token ────────────
    // This bypasses the need to register GitHub OAuth credentials in CodeBuild
    const cloneUrl = `https://${githubToken}@github.com/tulwegroup/aurora-final-deployment.git`;

    const inlineBuildspec = [
      'version: 0.2',
      'phases:',
      '  install:',
      '    runtime-versions:',
      '      docker: 20',
      '  pre_build:',
      '    commands:',
      `      - git clone ${cloneUrl} repo`,
      '      - cd repo',
      `      - aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${accountId}.dkr.ecr.${region}.amazonaws.com`,
      '      - COMMIT_SHA=$(git -C . rev-parse --short HEAD)',
      '  build:',
      '    commands:',
      '      - cd repo',
      `      - docker build -t aurora-api -f Dockerfile .`,
      `      - docker tag aurora-api:latest ${ecrUri}:latest`,
      `      - docker tag aurora-api:latest ${ecrUri}:$COMMIT_SHA`,
      '  post_build:',
      '    commands:',
      '      - cd repo',
      `      - docker push ${ecrUri}:latest`,
      `      - docker push ${ecrUri}:$COMMIT_SHA`,
      `      - aws ecs update-service --cluster aurora-cluster-osi --service aurora-osi-production --force-new-deployment --region ${region}`,
      '      - echo "Deploy complete"',
    ].join('\n');

    const projectDef = {
      name: projectName,
      description: 'Build aurora-vnext API image and deploy to ECS',
      source: {
        type: 'NO_SOURCE',
        buildspec: inlineBuildspec,
      },
      artifacts: {
        type: 'NO_ARTIFACTS',
      },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
      },
      serviceRole: `arn:aws:iam::${accountId}:role/codebuild-aurora-service-role`,
    };

    // Try to create; if exists, update it
    let createRes = await cbRequest({ action: 'CreateProject', body: projectDef, ...creds });

    if (!createRes.ok) {
      const detail = JSON.stringify(createRes.data);
      const alreadyExists = detail.includes('already exists') || detail.includes('ResourceAlreadyExists');

      if (alreadyExists) {
        // Update instead
        console.log('[auroraCreateBuildPipeline] Project exists, updating...');
        const updateRes = await cbRequest({ action: 'UpdateProject', body: projectDef, ...creds });
        if (!updateRes.ok) {
          return Response.json({ error: 'Failed to update existing project', detail: updateRes.data }, { status: 500 });
        }
        createRes = updateRes;
      } else {
        // Creation genuinely failed
        const isIAMError = detail.includes('role') || detail.includes('Role') || detail.includes('AccessDenied') || detail.includes('InvalidInput');
        return Response.json({
          error: 'CodeBuild CreateProject failed',
          detail: createRes.data,
          root_cause: isIAMError
            ? 'IAM service role missing or wrong. CodeBuild needs a service role with ECR push + ECS UpdateService + CloudWatch Logs permissions.'
            : 'Check detail above',
          required_role: `arn:aws:iam::${accountId}:role/codebuild-aurora-service-role`,
          manual_alternative: {
            instructions: [
              '1. Go to AWS CodeBuild console: https://console.aws.amazon.com/codesuite/codebuild/us-east-1/projects/create',
              '2. Project name: aurora-api-build',
              '3. Source: No source',
              '4. Environment: Managed image, Amazon Linux, Standard, aws/codebuild/standard:7.0, privileged mode ON',
              '5. Buildspec: Insert build commands (paste the buildspec below)',
              '6. Service role: Create new or use existing with ECR+ECS permissions',
              '7. Create project, then click Start build',
            ],
            buildspec_to_paste: inlineBuildspec,
          },
        }, { status: 500 });
      }
    }

    if (action === 'create_project') {
      return Response.json({
        status: 'project_ready',
        project: projectName,
        next_step: `Call auroraCreateBuildPipeline with { start_only: true } to start the build`,
      });
    }

    // Start build immediately
    const startRes = await cbRequest({ action: 'StartBuild', body: { projectName }, ...creds });

    if (!startRes.ok) {
      return Response.json({
        project_status: 'created_or_updated',
        error: 'Build start failed',
        detail: startRes.data,
        manual_start: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${projectName}`,
      }, { status: 500 });
    }

    const build = startRes.data?.build;
    return Response.json({
      status: 'build_started',
      project: projectName,
      build_id: build?.id,
      build_status: build?.buildStatus,
      source_repo: 'tulwegroup/aurora-final-deployment',
      dockerfile: 'Dockerfile (builds aurora_vnext/app → ECR aurora-api:latest)',
      estimated_duration: '5-10 minutes',
      what_happens: [
        'git clone aurora-final-deployment',
        'docker build from Dockerfile (copies aurora_vnext/app, runs uvicorn)',
        'push to ECR as :latest and :<commit-sha>',
        'force ECS redeployment to pull new image',
      ],
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${projectName}`,
      verify_after: 'Wait ~8 min then run auroraImageDiagnostics to confirm live contract',
    });

  } catch (e) {
    console.error('[auroraCreateBuildPipeline]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});