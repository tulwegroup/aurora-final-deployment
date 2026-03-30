/**
 * Patches the ECS task definition to add CloudWatch logging,
 * then forces a new deployment so we can see startup errors.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import {
  ECSClient,
  DescribeServicesCommand,
  DescribeTaskDefinitionCommand,
  RegisterTaskDefinitionCommand,
  UpdateServiceCommand,
} from 'npm:@aws-sdk/client-ecs@3';
import {
  CloudWatchLogsClient,
  CreateLogGroupCommand,
} from 'npm:@aws-sdk/client-cloudwatch-logs@3';

const REGION = 'us-east-1';
const CLUSTER = 'aurora-cluster-osi';
const SERVICE_NAME = 'aurora-osi-production';
const LOG_GROUP = '/ecs/aurora-osi-production';

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

  const creds = {
    region: REGION,
    credentials: {
      accessKeyId: Deno.env.get('AWS_ACCESS_KEY_ID'),
      secretAccessKey: Deno.env.get('AWS_SECRET_ACCESS_KEY'),
    },
  };
  const ecs = new ECSClient(creds);
  const logs = new CloudWatchLogsClient(creds);

  // 1. Create log group (ignore if already exists)
  try {
    await logs.send(new CreateLogGroupCommand({ logGroupName: LOG_GROUP }));
    console.log(`[patch] Created log group ${LOG_GROUP}`);
  } catch (e) {
    if (!e.message?.includes('already exists')) throw e;
    console.log(`[patch] Log group already exists`);
  }

  // 2. Get current task definition
  const svcRes = await ecs.send(new DescribeServicesCommand({ cluster: CLUSTER, services: [SERVICE_NAME] }));
  const currentTaskDefArn = svcRes.services?.[0]?.taskDefinition;
  const tdRes = await ecs.send(new DescribeTaskDefinitionCommand({ taskDefinition: currentTaskDefArn }));
  const currentTd = tdRes.taskDefinition;

  // 3. Register new revision with logging added
  const newContainers = currentTd.containerDefinitions.map((c, i) => {
    if (i !== 0) return c;
    return {
      ...c,
      logConfiguration: {
        logDriver: 'awslogs',
        options: {
          'awslogs-group': LOG_GROUP,
          'awslogs-region': REGION,
          'awslogs-stream-prefix': 'ecs',
        },
      },
    };
  });

  const regRes = await ecs.send(new RegisterTaskDefinitionCommand({
    family: currentTd.family,
    networkMode: currentTd.networkMode,
    requiresCompatibilities: currentTd.requiresCompatibilities,
    cpu: currentTd.cpu,
    memory: currentTd.memory,
    executionRoleArn: currentTd.executionRoleArn,
    taskRoleArn: currentTd.taskRoleArn,
    containerDefinitions: newContainers,
  }));

  const newTaskDefArn = regRes.taskDefinition?.taskDefinitionArn;
  const newRevision = regRes.taskDefinition?.revision;
  console.log(`[patch] Registered task def revision ${newRevision}`);

  // 4. Force deploy with new task def
  await ecs.send(new UpdateServiceCommand({
    cluster: CLUSTER,
    service: SERVICE_NAME,
    taskDefinition: newTaskDefArn,
    forceNewDeployment: true,
  }));

  return Response.json({
    status: 'done',
    log_group_created: LOG_GROUP,
    new_task_def_arn: newTaskDefArn,
    new_revision: newRevision,
    message: 'New task deploying with CloudWatch logging. Check logs in 60s.',
    log_url: `https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#logsV2:log-groups/log-group/${encodeURIComponent(LOG_GROUP)}`,
  });
});