/**
 * auroraBuildAndDeploy
 *
 * Builds the real aurora_vnext Docker image and deploys it to ECS.
 *
 * Strategy:
 *   1. Trigger CodeBuild to build from GitHub source (if project exists)
 *   2. OR register a new task definition pointing at a specific ECR image tag
 *      and force ECS redeployment (if build already done externally)
 *
 * Payload options:
 *   { action: "trigger_build", codebuild_project: "aurora-api-build" }
 *   { action: "deploy_image", image_uri: "368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:sha-abc123" }
 *   { action: "force_redeploy" }   — re-pulls :latest and restarts
 *
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// ── SigV4 ─────────────────────────────────────────────────────────────────
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

async function awsRequest({ service, region, action, body, accessKeyId, secretAccessKey }) {
  const host = `${service}.${region}.amazonaws.com`;
  const bodyStr = JSON.stringify(body);
  const headers = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service, accessKeyId, secretAccessKey });
  const targetMap = {
    ecs: `AmazonEC2ContainerServiceV20141113.${action}`,
    ecr: `AmazonEC2ContainerRegistry_V20150921.${action}`,
    codebuild: `CodeBuild_20161810.${action}`,
  };
  if (targetMap[service]) headers['X-Amz-Target'] = targetMap[service];
  const res = await fetch(`https://${host}/`, { method: 'POST', headers, body: bodyStr });
  return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
}

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
    const creds = { region, accessKeyId, secretAccessKey };

    // ── ACTION: trigger_build ─────────────────────────────────────────────
    if (action === 'trigger_build') {
      if (!codebuild_project) {
        // Auto-discover: list projects
        const listRes = await awsRequest({ service: 'codebuild', action: 'ListProjects', body: {}, ...creds });
        const projects = listRes.data?.projects || [];
        if (projects.length === 0) {
          return Response.json({
            error: 'No CodeBuild projects found. Create a CodeBuild project in AWS console that builds from your aurora_vnext GitHub repo.',
            hint: 'Project should: git clone aurora-vnext, docker build -t aurora-api:$CODEBUILD_BUILD_NUMBER ., push to ECR, then call auroraBuildAndDeploy with action=deploy_image',
            codebuild_console: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects`,
          }, { status: 400 });
        }
        return Response.json({
          error: 'codebuild_project name required',
          available_projects: projects,
          hint: 'Pass { action: "trigger_build", codebuild_project: "<name from above>" }',
        }, { status: 400 });
      }

      const buildRes = await awsRequest({
        service: 'codebuild', action: 'StartBuild',
        body: {
          projectName: codebuild_project,
          environmentVariablesOverride: [
            { name: 'ECR_REPO', value: `${accountId}.dkr.ecr.${region}.amazonaws.com/${ecrRepo}`, type: 'PLAINTEXT' },
            { name: 'AWS_REGION', value: region, type: 'PLAINTEXT' },
          ],
        },
        ...creds
      });

      if (!buildRes.ok) {
        return Response.json({ error: 'CodeBuild start failed', detail: buildRes.data }, { status: 500 });
      }

      const build = buildRes.data?.build;
      return Response.json({
        action: 'trigger_build',
        status: 'build_started',
        build_id: build?.id,
        build_status: build?.buildStatus,
        project: codebuild_project,
        estimated_duration: '5-15 minutes',
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${codebuild_project}`,
        next_step: 'Once build completes, call auroraBuildAndDeploy with { action: "deploy_image", image_uri: "...:sha-<commit>" }',
      });
    }

    // ── ACTION: deploy_image ──────────────────────────────────────────────
    if (action === 'deploy_image') {
      const targetImage = image_uri || `${accountId}.dkr.ecr.${region}.amazonaws.com/${ecrRepo}:latest`;

      // Get current task definition to clone it with new image
      const svcRes = await awsRequest({ service: 'ecs', action: 'DescribeServices', body: { cluster, services: [serviceName] }, ...creds });
      const currentTaskDefArn = svcRes.data?.services?.[0]?.taskDefinition;
      if (!currentTaskDefArn) {
        return Response.json({ error: 'Could not find current task definition' }, { status: 500 });
      }

      const tdRes = await awsRequest({ service: 'ecs', action: 'DescribeTaskDefinition', body: { taskDefinition: currentTaskDefArn }, ...creds });
      const currentTd = tdRes.data?.taskDefinition;
      if (!currentTd) {
        return Response.json({ error: 'Could not describe current task definition' }, { status: 500 });
      }

      // Register new task definition revision with updated image
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

      const regRes = await awsRequest({ service: 'ecs', action: 'RegisterTaskDefinition', body: newTd, ...creds });
      if (!regRes.ok) {
        return Response.json({ error: 'Failed to register task definition', detail: regRes.data }, { status: 500 });
      }

      const newTaskDefArn = regRes.data?.taskDefinition?.taskDefinitionArn;
      const newRevision = regRes.data?.taskDefinition?.revision;

      // Update ECS service to use new task definition
      const updateRes = await awsRequest({
        service: 'ecs', action: 'UpdateService',
        body: { cluster, service: serviceName, taskDefinition: newTaskDefArn, forceNewDeployment: true },
        ...creds
      });

      if (!updateRes.ok) {
        return Response.json({ error: 'ECS service update failed', detail: updateRes.data }, { status: 500 });
      }

      console.log(`[auroraBuildAndDeploy] Deployed image ${targetImage} → task def revision ${newRevision}`);
      return Response.json({
        action: 'deploy_image',
        status: 'deployment_started',
        image_deployed: targetImage,
        task_def_arn: newTaskDefArn,
        task_def_revision: newRevision,
        cluster,
        service: serviceName,
        estimated_time: '2-3 minutes for new task to become healthy',
        console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${cluster}/services/${serviceName}/deployments`,
        verify_step: 'Call auroraImageDiagnostics after ~3 minutes to verify live contract',
      });
    }

    // ── ACTION: force_redeploy ────────────────────────────────────────────
    const updateRes = await awsRequest({
      service: 'ecs', action: 'UpdateService',
      body: { cluster, service: serviceName, forceNewDeployment: true },
      ...creds
    });

    if (!updateRes.ok) {
      return Response.json({ error: 'Force redeploy failed', detail: updateRes.data }, { status: 500 });
    }

    const svc = updateRes.data?.service;
    return Response.json({
      action: 'force_redeploy',
      status: 'redeployment_started',
      service: serviceName,
      cluster,
      running_count: svc?.runningCount,
      desired_count: svc?.desiredCount,
      note: 'ECS will pull the current :latest ECR image and restart. If ECR :latest is still the stub, this alone will not fix the mismatch.',
      console_url: `https://console.aws.amazon.com/ecs/v2/clusters/${cluster}/services/${serviceName}/deployments`,
    });

  } catch (e) {
    console.error('[auroraBuildAndDeploy]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});