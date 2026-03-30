/**
 * fixCodeBuildYAML — Minimal buildspec that clones from GitHub.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, UpdateProjectCommand, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const ACCOUNT_ID = '368331615566';
const PROJECT_NAME = 'aurora-api-build';
const ECR_REPO = 'aurora-api';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const githubToken = Deno.env.get('GITHUB_PAT');
    
    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });
    if (!githubToken) return Response.json({ error: 'GITHUB_PAT not set' }, { status: 500 });

    // Simple buildspec: clone repo, build, push
    const buildspec = `version: 0.2
phases:
  pre_build:
    commands:
      - echo "Logging into ECR..."
      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
      - echo "Cloning aurora-final-deployment..."
      - git clone https://${githubToken}@github.com/tulwegroup/aurora-final-deployment.git /tmp/repo
      - cd /tmp/repo
      - ls -la
  build:
    commands:
      - echo "Building Docker image..."
      - docker build -t aurora-api:latest -f Dockerfile .
      - docker tag aurora-api:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
  post_build:
    commands:
      - echo "Pushing to ECR..."
      - docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
`;

    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };
    const cbClient = new CodeBuildClient(awsCreds);

    console.log('[fixCodeBuildYAML] Updating buildspec to clone from GitHub...');
    await cbClient.send(new UpdateProjectCommand({
      name: PROJECT_NAME,
      source: { type: 'NO_SOURCE', buildspec },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
      },
    }));

    console.log('[fixCodeBuildYAML] Starting build...');
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));

    return Response.json({
      status: 'buildspec_updated',
      build_id: buildRes.build?.id,
      build_status: buildRes.build?.buildStatus,
      message: 'Buildspec now clones aurora-final-deployment from GitHub and builds from Dockerfile there',
      note: 'Make sure aurora-final-deployment has a valid Dockerfile in the root',
      estimated_duration: '5-10 minutes',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${PROJECT_NAME}`,
    });

  } catch (e) {
    console.error('[fixCodeBuildYAML]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});