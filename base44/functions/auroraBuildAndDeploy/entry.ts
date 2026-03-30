/**
 * auroraBuildAndDeploy — Trigger CodeBuild / deploy image to ECS.
 * Uses AWS SDK v3 via npm (no hand-rolled SigV4).
 * ADMIN ONLY.
 *
 * Payload options:
 *   { action: "trigger_build", codebuild_project: "aurora-api-build" }
 *   { action: "deploy_image", image_uri: "368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:sha-abc123" }
 *   { action: "force_redeploy" }
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, StartBuildCommand, ListProjectsCommand } from 'npm:@aws-sdk/client-codebuild@3';
import { ECSClient, UpdateServiceCommand, DescribeServicesCommand, DescribeTaskDefinitionCommand, RegisterTaskDefinitionCommand } from 'npm:@aws-sdk/client-ecs@3';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const body = await req.json().catch(() => ({}));
    const { action = 'force_redeploy', codebuild_project, image_uri } = body;

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const region = 'us-east-1';
    const cluster = 'aurora-cluster-osi';
    const serviceName = 'aurora-osi-production';
    const accountId = '368331615566';
    const ecrRepo = 'aurora-api';

    if (!accessKeyId || !secretAccessKey) {
      return Response.json({ error: 'AWS credentials not set' }, { status: 500 });
    }

    const awsCreds = { region, credentials: { accessKeyId, secretAccessKey } };
    const cbClient = new CodeBuildClient(awsCreds);
    const ecsClient = new ECSClient(awsCreds);

    // ── trigger_build ──────────────────────────────────────────────────────
    if (action === 'trigger_build') {
      let projectName = codebuild_project;

      if (!projectName) {
        const listRes = await cbClient.send(new ListProjectsCommand({}));
        const projects = listRes.projects || [];
        if (projects.length === 0) {
          return Response.json({ error: 'No CodeBuild projects found.' }, { status: 400 });
        }
        return Response.json({
          error: 'codebuild_project name required',
          available_projects: projects,
        }, { status: 400 });
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
        estimated_duration: '5-10 minutes',
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${projectName}`,
        what_happens: [
          'Clones tulwegroup/aurora-final-deployment',
          'docker build (copies aurora_vnext/app, runs uvicorn:8000)',
          'push to ECR aurora-api:latest',
          'ECS force-redeployment triggered automatically by buildspec post_build',
        ],
      });
    }

    // ── deploy_image ───────────────────────────────────────────────────────
    if (action === 'deploy_image') {
      const targetImage = image_uri || `${accountId}.dkr.ecr.${region}.amazonaws.com/${ecrRepo}:latest`;

      const svcRes = await ecsClient.send(new DescribeServicesCommand({ cluster, services: [serviceName] }));
      const currentTaskDefArn = svcRes.services?.[0]?.taskDefinition;
      if (!currentTaskDefArn) return Response.json({ error: 'Could not find current task definition' }, { status: 500 });

      const tdRes = await ecsClient.send(new DescribeTaskDefinitionCommand({ taskDefinition: currentTaskDefArn }));
      const currentTd = tdRes.taskDefinition;
      if (!currentTd) return Response.json({ error: 'Could not describe current task definition' }, { status: 500 });

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
        cluster, service: serviceName, taskDefinition: newTaskDefArn, forceNewDeployment: true,
      }));

      console.log(`[auroraBuildAndDeploy] Deployed ${targetImage} → task def revision ${newRevision}`);
      return Response.json({
        action: 'deploy_image',
        status: 'deployment_started',
        image_deployed: targetImage,
        task_def_arn: newTaskDefArn,
        task_def_revision: newRevision,
        estimated_time: '2-3 minutes for new task to become healthy',
        console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${cluster}/services/${serviceName}/deployments`,
      });
    }

    // ── force_redeploy ─────────────────────────────────────────────────────
    const updateRes = await ecsClient.send(new UpdateServiceCommand({
      cluster, service: serviceName, forceNewDeployment: true,
    }));
    const svc = updateRes.service;

    return Response.json({
      action: 'force_redeploy',
      status: 'redeployment_started',
      service: serviceName,
      cluster,
      running_count: svc?.runningCount,
      desired_count: svc?.desiredCount,
      note: 'ECS re-pulls current :latest ECR image. Only fixes the stub if a new image was pushed.',
      console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${cluster}/services/${serviceName}/deployments`,
    });

  } catch (e) {
    console.error('[auroraBuildAndDeploy]', e.message, e.stack);
    return Response.json({ error: e.message }, { status: 500 });
  }
});