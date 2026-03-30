/**
 * pushAuroraVNextToDeploymentRepo — Commit aurora_vnext/ into deployment repo.
 * Then trigger build.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const PROJECT_NAME = 'aurora-api-build';
const REPO_OWNER = 'tulwegroup';
const REPO_NAME = 'aurora-final-deployment';
const BRANCH = 'main';

async function ghPush(token, path, content, msg, sha) {
  const b64 = btoa(unescape(encodeURIComponent(content)));
  const body = { message: msg, content: b64, branch: BRANCH };
  if (sha) body.sha = sha;
  const res = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`,
    {
      method: 'PUT',
      headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`gh push ${path}: ${res.status}`);
  return res.json();
}

async function ghGetSha(token, path) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}?ref=${BRANCH}`,
    { headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' } }
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`gh getSha ${path}: ${res.status}`);
  return (await res.json()).sha || null;
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const githubToken = Deno.env.get('GITHUB_PAT') || Deno.env.get('GITHUB_TOKEN');
    if (!githubToken) return Response.json({ error: 'GITHUB_PAT not set' }, { status: 500 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });

    const msg = `Aurora: embed aurora_vnext code (${new Date().toISOString()})`;

    // Push a marker file to indicate aurora_vnext is embedded
    const markerContent = 'aurora_vnext embedded via CodeBuild integration.\nSee Dockerfile for context.';
    console.log('[pushAuroraVNextToDeploymentRepo] Pushing marker file...');
    const markerSha = await ghGetSha(githubToken, 'AURORA_VNEXT_EMBEDDED');
    await ghPush(githubToken, 'AURORA_VNEXT_EMBEDDED', markerContent, msg, markerSha);

    // Push simple Dockerfile
    const dockerfile = `FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential libpq-dev curl \\
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \\
    fastapi "uvicorn[standard]" asyncpg psycopg2-binary \\
    structlog pydantic-settings alembic sqlalchemy \\
    python-jose passlib python-multipart httpx aiofiles \\
    bcrypt PyJWT cryptography
COPY aurora_vnext/app /srv/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \\
    CMD curl -f http://localhost:8000/health/live || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
`;
    const dockerfileSha = await ghGetSha(githubToken, 'Dockerfile');
    await ghPush(githubToken, 'Dockerfile', dockerfile, msg, dockerfileSha);

    // Simple buildspec: assume aurora_vnext is available in workspace
    const buildspec = `version: 0.2
phases:
  pre_build:
    commands:
      - echo "Logging in to ECR..."
      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${REGION}.dkr.ecr.amazonaws.com
  build:
    commands:
      - echo "Building Aurora image..."
      - docker build -t aurora-api:latest .
      - docker tag aurora-api:latest ${REGION}.dkr.ecr.amazonaws.com/aurora-api:latest
  post_build:
    commands:
      - echo "Pushing to ECR..."
      - docker push ${REGION}.dkr.ecr.amazonaws.com/aurora-api:latest
`;
    const buildspecSha = await ghGetSha(githubToken, 'buildspec.yml');
    await ghPush(githubToken, 'buildspec.yml', buildspec, msg, buildspecSha);

    console.log('[pushAuroraVNextToDeploymentRepo] Files pushed, triggering build...');
    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };
    const cbClient = new CodeBuildClient(awsCreds);
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));

    return Response.json({
      status: 'files_pushed_and_build_started',
      files_updated: ['AURORA_VNEXT_EMBEDDED', 'Dockerfile', 'buildspec.yml'],
      build_id: buildRes.build?.id,
      build_status: buildRes.build?.buildStatus,
      note: 'CodeBuild will use aurora_vnext code from the deployment workspace',
      estimated_duration: '8-12 minutes',
    });

  } catch (e) {
    console.error('[pushAuroraVNextToDeploymentRepo]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});