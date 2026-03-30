/**
 * fixCodeBuildSpec — Update buildspec to clone aurora_vnext into working directory.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, UpdateProjectCommand, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const ACCOUNT_ID = '368331615566';
const PROJECT_NAME = 'aurora-api-build';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });

    const buildspec = [
      'version: 0.2',
      'phases:',
      '  pre_build:',
      '    commands:',
      '      - echo "Logging in to ECR..."',
      `      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com`,
      '  build:',
      '    commands:',
      '      - echo "Building from Dockerfile with embedded aurora_vnext..."',
      `      - docker build -t aurora-api:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api:latest .`,
      '  post_build:',
      '    commands:',
      `      - docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api:latest`,
      '      - echo "Push complete"',
    ].join('\n');

    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };
    const cbClient = new CodeBuildClient(awsCreds);

    console.log('[fixCodeBuildSpec] Updating buildspec...');
    await cbClient.send(new UpdateProjectCommand({
      name: PROJECT_NAME,
      source: {
        type: 'NO_SOURCE',
        buildspec,
      },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
      },
    }));

    console.log('[fixCodeBuildSpec] Starting build...');
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));
    const build = buildRes.build;

    return Response.json({
      status: 'buildspec_fixed_and_build_started',
      buildspec: 'Use local Dockerfile (aurora-final-deployment) with embedded aurora_vnext context',
      build_id: build?.id,
      build_status: build?.buildStatus,
      estimated_duration: '5-10 minutes',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${PROJECT_NAME}`,
    });

  } catch (e) {
    console.error('[fixCodeBuildSpec]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});