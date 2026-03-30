import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { ECSClient, DescribeTaskDefinitionCommand, DescribeServicesCommand } from 'npm:@aws-sdk/client-ecs@3';

const REGION = 'us-east-1';
const CLUSTER = 'aurora-cluster-osi';
const SERVICE_NAME = 'aurora-osi-production';

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

  const creds = { region: REGION, credentials: {
    accessKeyId: Deno.env.get('AWS_ACCESS_KEY_ID'),
    secretAccessKey: Deno.env.get('AWS_SECRET_ACCESS_KEY'),
  }};
  const ecs = new ECSClient(creds);

  const svcRes = await ecs.send(new DescribeServicesCommand({ cluster: CLUSTER, services: [SERVICE_NAME] }));
  const svc = svcRes.services?.[0];
  const taskDefArn = svc?.taskDefinition;
  const deployments = svc?.deployments?.map(d => ({
    id: d.id,
    status: d.status,
    taskDef: d.taskDefinition,
    runningCount: d.runningCount,
    desiredCount: d.desiredCount,
    failedTasks: d.failedTasks,
    rolloutState: d.rolloutState,
    rolloutStateReason: d.rolloutStateReason,
    createdAt: d.createdAt,
    updatedAt: d.updatedAt,
  }));

  const tdRes = await ecs.send(new DescribeTaskDefinitionCommand({ taskDefinition: taskDefArn }));
  const td = tdRes.taskDefinition;
  const containers = td?.containerDefinitions?.map(c => ({
    name: c.name,
    image: c.image,
    portMappings: c.portMappings,
    environment: c.environment,
    logConfiguration: c.logConfiguration,
    command: c.command,
    entryPoint: c.entryPoint,
  }));

  return Response.json({
    service_status: svc?.status,
    running_count: svc?.runningCount,
    desired_count: svc?.desiredCount,
    current_task_def: taskDefArn,
    deployments,
    containers,
    execution_role: td?.executionRoleArn,
    task_role: td?.taskRoleArn,
    cpu: td?.cpu,
    memory: td?.memory,
  });
});