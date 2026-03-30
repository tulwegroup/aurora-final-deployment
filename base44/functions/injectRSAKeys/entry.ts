/**
 * Generates a fresh RSA-2048 key pair using Web Crypto API,
 * injects AURORA_JWT_PRIVATE_KEY + AURORA_JWT_PUBLIC_KEY into the ECS task def,
 * and forces a new deployment.
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

const REGION = 'us-east-1';
const CLUSTER = 'aurora-cluster-osi';
const SERVICE_NAME = 'aurora-osi-production';

// Convert ArrayBuffer to base64
function bufToB64(buf) {
  const bytes = new Uint8Array(buf);
  let str = '';
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str);
}

// Wrap base64 DER in PEM
function toPem(b64, label) {
  const lines = b64.match(/.{1,64}/g).join('\n');
  return `-----BEGIN ${label}-----\n${lines}\n-----END ${label}-----\n`;
}

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

  // 1. Generate RSA-2048 key pair
  const keyPair = await crypto.subtle.generateKey(
    { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
    true,
    ['sign', 'verify']
  );

  const privateDer = await crypto.subtle.exportKey('pkcs8', keyPair.privateKey);
  const publicDer  = await crypto.subtle.exportKey('spki',  keyPair.publicKey);

  const privatePem = toPem(bufToB64(privateDer), 'PRIVATE KEY');
  const publicPem  = toPem(bufToB64(publicDer),  'PUBLIC KEY');

  console.log('[injectRSAKeys] Key pair generated successfully');

  // 2. Get current task definition
  const creds = { region: REGION, credentials: {
    accessKeyId: Deno.env.get('AWS_ACCESS_KEY_ID'),
    secretAccessKey: Deno.env.get('AWS_SECRET_ACCESS_KEY'),
  }};
  const ecs = new ECSClient(creds);

  const svcRes = await ecs.send(new DescribeServicesCommand({ cluster: CLUSTER, services: [SERVICE_NAME] }));
  const currentTaskDefArn = svcRes.services?.[0]?.taskDefinition;
  const tdRes = await ecs.send(new DescribeTaskDefinitionCommand({ taskDefinition: currentTaskDefArn }));
  const currentTd = tdRes.taskDefinition;

  // 3. Patch container env — replace placeholder keys, add RSA keys
  const newContainers = currentTd.containerDefinitions.map((c, i) => {
    if (i !== 0) return c;

    // Remove old placeholder key vars, then add real ones
    const filteredEnv = (c.environment || []).filter(e =>
      e.name !== 'AURORA_JWT_PRIVATE_KEY' &&
      e.name !== 'AURORA_JWT_PUBLIC_KEY'
    );

    return {
      ...c,
      environment: [
        ...filteredEnv,
        { name: 'AURORA_JWT_PRIVATE_KEY', value: privatePem },
        { name: 'AURORA_JWT_PUBLIC_KEY',  value: publicPem  },
      ],
    };
  });

  // 4. Register new task def revision
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
  const newRevision   = regRes.taskDefinition?.revision;
  console.log(`[injectRSAKeys] Registered task def revision ${newRevision}`);

  // 5. Force redeploy
  await ecs.send(new UpdateServiceCommand({
    cluster: CLUSTER,
    service: SERVICE_NAME,
    taskDefinition: newTaskDefArn,
    forceNewDeployment: true,
  }));

  return Response.json({
    status: 'done',
    new_task_def_arn: newTaskDefArn,
    new_revision: newRevision,
    keys_injected: ['AURORA_JWT_PRIVATE_KEY', 'AURORA_JWT_PUBLIC_KEY'],
    message: 'RSA keys injected. Container restarting — wait ~60s then test /auth/login.',
  });
});