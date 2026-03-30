/**
 * auroraBuildAndDeploy — Trigger CodeBuild / deploy image to ECS.
 * Uses AWS SDK v3 via npm (no hand-rolled SigV4).
 * ADMIN ONLY.
 *
 * Actions:
 *   trigger_build        — start build on existing project
 *   update_project       — overwrite project buildspec with correct git-clone inline spec, then start build
 *   get_build_status     — check status of a running build by build_id
 *   deploy_image         — register new task def with explicit image URI + force redeploy
 *   force_redeploy       — force redeploy with current :latest
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import {
  CodeBuildClient,
  StartBuildCommand,
  ListProjectsCommand,
  UpdateProjectCommand,
  BatchGetBuildsCommand,
} from 'npm:@aws-sdk/client-codebuild@3';
import {
  ECSClient,
  UpdateServiceCommand,
  DescribeServicesCommand,
  DescribeTaskDefinitionCommand,
  RegisterTaskDefinitionCommand,
} from 'npm:@aws-sdk/client-ecs@3';

const REGION = 'us-east-1';
const ACCOUNT_ID = '368331615566';
const ECR_URI = `${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api`;
const CLUSTER = 'aurora-cluster-osi';
const SERVICE_NAME = 'aurora-osi-production';
const PROJECT_NAME = 'aurora-api-build';

function buildInlineBuildspec(githubToken) {
  const cloneUrl = `https://${githubToken}@github.com/tulwegroup/aurora-final-deployment.git`;
  return [
    'version: 0.2',
    'phases:',
    '  pre_build:',
    '    commands:',
    `      - git clone ${cloneUrl} repo`,
    `      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com`,
    '  build:',
    '    commands:',
    '      - docker build -t aurora-api -f repo/Dockerfile repo/',
    `      - docker tag aurora-api:latest ${ECR_URI}:latest`,
    '  post_build:',
    '    commands:',
    `      - docker push ${ECR_URI}:latest`,
    '      - echo "Deploy complete"',
  ].join('\n');
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const body = await req.json().catch(() => ({}));
    const { action = 'force_redeploy', codebuild_project, image_uri, build_id } = body;

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const githubToken = Deno.env.get('GITHUB_PAT') || Deno.env.get('GITHUB_TOKEN');

    if (!accessKeyId || !secretAccessKey) {
      return Response.json({ error: 'AWS credentials not set' }, { status: 500 });
    }

    const awsCreds = { region: REGION, credentials: { accessKeyId, secretAccessKey } };
    const cbClient = new CodeBuildClient(awsCreds);
    const ecsClient = new ECSClient(awsCreds);
    const projectName = codebuild_project || PROJECT_NAME;

    // ── get_build_status ───────────────────────────────────────────────────
    if (action === 'get_build_status') {
      if (!build_id) return Response.json({ error: 'build_id required' }, { status: 400 });
      const res = await cbClient.send(new BatchGetBuildsCommand({ ids: [build_id] }));
      const b = res.builds?.[0];
      if (!b) return Response.json({ error: 'Build not found' }, { status: 404 });
      return Response.json({
        build_id: b.id,
        build_status: b.buildStatus,
        current_phase: b.currentPhase,
        start_time: b.startTime,
        end_time: b.endTime,
        phases: b.phases?.map(p => ({ name: p.phaseType, status: p.phaseStatus, duration_seconds: p.durationInSeconds })),
        logs_url: b.logs?.deepLink,
      });
    }

    // ── update_project (overwrite buildspec then start) ────────────────────
    if (action === 'update_project') {
      if (!githubToken) return Response.json({ error: 'GITHUB_PAT not set' }, { status: 500 });

      const inlineBuildspec = buildInlineBuildspec(githubToken);

      console.log(`[auroraBuildAndDeploy] Updating project ${projectName} with correct buildspec...`);
      await cbClient.send(new UpdateProjectCommand({
        name: projectName,
        source: {
          type: 'NO_SOURCE',
          buildspec: inlineBuildspec,
        },
        environment: {
          type: 'LINUX_CONTAINER',
          image: 'aws/codebuild/standard:7.0',
          computeType: 'BUILD_GENERAL1_MEDIUM',
          privilegedMode: true,
        },
      }));
      console.log(`[auroraBuildAndDeploy] Project updated, starting build...`);

      const buildRes = await cbClient.send(new StartBuildCommand({ projectName }));
      const build = buildRes.build;

      return Response.json({
        action: 'update_project',
        status: 'project_updated_and_build_started',
        build_id: build?.id,
        build_status: build?.buildStatus,
        project: projectName,
        buildspec: 'git clone aurora-final-deployment → docker build → ECR push → ECS redeploy',
        estimated_duration: '8-12 minutes',
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${projectName}`,
      });
    }

    // ── trigger_build ──────────────────────────────────────────────────────
    if (action === 'trigger_build') {
      if (!projectName) {
        const listRes = await cbClient.send(new ListProjectsCommand({}));
        return Response.json({ error: 'codebuild_project required', available_projects: listRes.projects || [] }, { status: 400 });
      }

      console.log(`[auroraBuildAndDeploy] Starting build on project: ${projectName}`);
      const buildRes = await cbClient.send(new StartBuildCommand({ projectName }));
      const build = buildRes.build;

      return Response.json({
        action: 'trigger_build',
        status: 'build_started',
        build_id: build?.id,
        build_status: build?.buildStatus,
        project: projectName,
        estimated_duration: '8-12 minutes',
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${projectName}`,
      });
    }

    // ── deploy_image ───────────────────────────────────────────────────────
    if (action === 'deploy_image') {
      const targetImage = image_uri || `${ECR_URI}:latest`;

      const svcRes = await ecsClient.send(new DescribeServicesCommand({ cluster: CLUSTER, services: [SERVICE_NAME] }));
      const currentTaskDefArn = svcRes.services?.[0]?.taskDefinition;
      if (!currentTaskDefArn) return Response.json({ error: 'Could not find current task definition' }, { status: 500 });

      const tdRes = await ecsClient.send(new DescribeTaskDefinitionCommand({ taskDefinition: currentTaskDefArn }));
      const currentTd = tdRes.taskDefinition;
      if (!currentTd) return Response.json({ error: 'Could not describe task definition' }, { status: 500 });

      const newTd = {
        family: currentTd.family,
        networkMode: currentTd.networkMode,
        requiresCompatibilities: currentTd.requiresCompatibilities,
        cpu: currentTd.cpu,
        memory: currentTd.memory,
        executionRoleArn: currentTd.executionRoleArn,
        taskRoleArn: currentTd.taskRoleArn,
        containerDefinitions: currentTd.containerDefinitions.map((c, i) =>
          i === 0 ? { ...c, image: targetImage } : c
        ),
      };

      const regRes = await ecsClient.send(new RegisterTaskDefinitionCommand(newTd));
      const newTaskDefArn = regRes.taskDefinition?.taskDefinitionArn;
      const newRevision = regRes.taskDefinition?.revision;

      await ecsClient.send(new UpdateServiceCommand({
        cluster: CLUSTER, service: SERVICE_NAME, taskDefinition: newTaskDefArn, forceNewDeployment: true,
      }));

      return Response.json({
        action: 'deploy_image',
        status: 'deployment_started',
        image_deployed: targetImage,
        task_def_arn: newTaskDefArn,
        task_def_revision: newRevision,
        estimated_time: '2-3 minutes',
        console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services/${SERVICE_NAME}/deployments`,
      });
    }

    // ── force_redeploy ─────────────────────────────────────────────────────
    const updateRes = await ecsClient.send(new UpdateServiceCommand({
      cluster: CLUSTER, service: SERVICE_NAME, forceNewDeployment: true,
    }));
    const svc = updateRes.service;

    return Response.json({
      action: 'force_redeploy',
      status: 'redeployment_started',
      service: SERVICE_NAME,
      cluster: CLUSTER,
      running_count: svc?.runningCount,
      desired_count: svc?.desiredCount,
      console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services/${SERVICE_NAME}/deployments`,
    });

  } catch (e) {
    console.error('[auroraBuildAndDeploy]', e.message, e.stack);
    return Response.json({ error: e.message }, { status: 500 });
  }
});