/**
 * deleteStubAndRebuild
 * Delete stub image from ECR, update CodeBuild to build aurora_vnext directly.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { ECRClient, BatchDeleteImageCommand } from 'npm:@aws-sdk/client-ecr@3';
import { CodeBuildClient, UpdateProjectCommand, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const ACCOUNT_ID = '368331615566';
const REPO_NAME = 'aurora-api';
const PROJECT_NAME = 'aurora-api-build';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const githubPat = Deno.env.get('GITHUB_PAT') || Deno.env.get('GITHUB_TOKEN');

    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });
    if (!githubPat) return Response.json({ error: 'GITHUB_PAT not set' }, { status: 500 });

    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };

    // Step 1: Delete :latest tag from ECR
    console.log('[deleteStubAndRebuild] Deleting stub image from ECR...');
    const ecrClient = new ECRClient(awsCreds);
    try {
      await ecrClient.send(new BatchDeleteImageCommand({
        repositoryName: REPO_NAME,
        imageIds: [{ imageTag: 'latest' }],
      }));
      console.log('[deleteStubAndRebuild] Deleted :latest tag');
    } catch (e) {
      console.warn('[deleteStubAndRebuild] Failed to delete :latest (may not exist):', e.message);
    }

    // Step 2: Update CodeBuild buildspec to clone aurora_vnext and build
    const cloneUrl = `https://${githubPat}@github.com/tulwegroup/aurora-vnext.git`;
    const newBuildspec = [
      'version: 0.2',
      'phases:',
      '  pre_build:',
      `    commands:`,
      `      - echo "Cloning aurora_vnext..."`,
      `      - git clone ${cloneUrl} /tmp/aurora_vnext`,
      `      - cd /tmp/aurora_vnext`,
      `      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com`,
      '  build:',
      '    commands:',
      `      - echo "Building Docker image..."`,
      `      - docker build -t aurora-api -f aurora_vnext/infra/docker/Dockerfile.api .`,
      `      - docker tag aurora-api:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api:latest`,
      '  post_build:',
      '    commands:',
      `      - echo "Pushing to ECR..."`,
      `      - docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api:latest`,
    ].join('\n');

    console.log('[deleteStubAndRebuild] Updating CodeBuild project...');
    const cbClient = new CodeBuildClient(awsCreds);
    await cbClient.send(new UpdateProjectCommand({
      name: PROJECT_NAME,
      source: {
        type: 'NO_SOURCE',
        buildspec: newBuildspec,
      },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
      },
    }));
    console.log('[deleteStubAndRebuild] Project updated');

    // Step 3: Start build
    console.log('[deleteStubAndRebuild] Starting build...');
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));
    const build = buildRes.build;

    return Response.json({
      status: 'stub_deleted_and_build_started',
      deleted_from_ecr: ':latest tag',
      codebuild_updated: true,
      buildspec: 'Clone aurora_vnext directly → build from Dockerfile.api → push to ECR',
      build_id: build?.id,
      build_status: build?.buildStatus,
      estimated_duration: '10-15 minutes',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${PROJECT_NAME}`,
    });

  } catch (e) {
    console.error('[deleteStubAndRebuild]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});