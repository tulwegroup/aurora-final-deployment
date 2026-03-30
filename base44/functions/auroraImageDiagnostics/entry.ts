/**
 * auroraImageDiagnostics
 *
 * Proves ECS image mismatch by comparing:
 *   1. ECS task definition image URI (what ECS thinks it's running)
 *   2. ECR repository images (what actually exists in the registry)
 *   3. Live API contract probe (what the running container actually returns)
 *
 * Evidence output lets you confirm stub vs real aurora_vnext source.
 *
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// ── SigV4 helpers ──────────────────────────────────────────────────────────
async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}
async function hmacSHA256(key, data) {
  const k = await crypto.subtle.importKey('raw', typeof key === 'string' ? new TextEncoder().encode(key) : key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(data)));
}
function toHex(b) { return Array.from(b).map(x => x.toString(16).padStart(2, '0')).join(''); }

async function signV4({ method, host, path, body, region, service, accessKeyId, secretAccessKey, extraHeaders = {} }) {
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const bodyHash = await sha256Hex(body);
  const baseHeaders = { 'content-type': 'application/x-amz-json-1.1', 'host': host, 'x-amz-date': amzDate, ...extraHeaders };
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

// ── Live API contract probe ────────────────────────────────────────────────
async function probeAuroraLiveContract(backendUrl) {
  const results = {};

  // 1. Health
  try {
    const r = await fetch(`${backendUrl}/health/live`, { signal: AbortSignal.timeout(8000) });
    results.health_live = { status: r.status, body: await r.json().catch(() => r.text()) };
  } catch (e) { results.health_live = { error: e.message }; }

  // 2. Scan polygon — minimal payload using correct enum casing
  try {
    const r = await fetch(`${backendUrl}/api/v1/scan/polygon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        commodity: 'gold',
        scan_tier: 'SMART',
        environment: 'ONSHORE',
        aoi_polygon: {
          type: 'Polygon',
          coordinates: [[[36.0, -1.0], [36.1, -1.0], [36.1, -0.9], [36.0, -0.9], [36.0, -1.0]]]
        }
      }),
      signal: AbortSignal.timeout(12000),
    });
    const body = await r.json().catch(() => r.text());
    results.scan_polygon = {
      status: r.status,
      body,
      // Detect stub vs real
      has_scan_id: !!(body?.scan_id),
      has_scan_job_id: !!(body?.scan_job_id),
      has_submitted_at: !!(body?.submitted_at),
      is_stub_response: body?.status === 'accepted' && !body?.scan_id,
    };
  } catch (e) { results.scan_polygon = { error: e.message }; }

  // 3. Version/info endpoint
  try {
    const r = await fetch(`${backendUrl}/api/v1/version`, { signal: AbortSignal.timeout(5000) });
    results.version = { status: r.status, body: await r.json().catch(() => r.text()) };
  } catch (e) { results.version = { error: e.message }; }

  // 4. History list
  try {
    const r = await fetch(`${backendUrl}/api/v1/history`, { signal: AbortSignal.timeout(8000) });
    results.history = { status: r.status, body: await r.json().catch(() => r.text()) };
  } catch (e) { results.history = { error: e.message }; }

  return results;
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const backendUrl = (Deno.env.get('AURORA_BACKEND_URL') || 'https://api.aurora-osi.com').replace(/\/$/, '');
    const region = 'us-east-1';
    const cluster = 'aurora-cluster-osi';
    const serviceName = 'aurora-osi-production';
    const ecrRepo = 'aurora-api';
    const accountId = '368331615566';

    if (!accessKeyId || !secretAccessKey) {
      return Response.json({ error: 'AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set' }, { status: 500 });
    }

    const creds = { region, accessKeyId, secretAccessKey };

    // ── 1. Describe ECS service → get active task definition ARN ──────────
    const svcRes = await awsRequest({ service: 'ecs', action: 'DescribeServices', body: { cluster, services: [serviceName] }, ...creds });
    const svc = svcRes.data?.services?.[0];
    const activeTaskDefArn = svc?.taskDefinition || null;
    const runningCount = svc?.runningCount ?? 0;
    const deployments = svc?.deployments || [];

    // ── 2. Describe task definition → get container image ─────────────────
    let taskDefImage = null;
    let taskDefFamily = null;
    let taskDefRevision = null;
    if (activeTaskDefArn) {
      const tdRes = await awsRequest({ service: 'ecs', action: 'DescribeTaskDefinition', body: { taskDefinition: activeTaskDefArn }, ...creds });
      const td = tdRes.data?.taskDefinition;
      taskDefFamily = td?.family;
      taskDefRevision = td?.revision;
      taskDefImage = td?.containerDefinitions?.[0]?.image || null;
    }

    // ── 3. ECR: list images in aurora-api repo ────────────────────────────
    const ecrRes = await awsRequest({
      service: 'ecr', action: 'DescribeImages',
      body: { repositoryName: ecrRepo, registryId: accountId, maxResults: 20 },
      ...creds
    });
    const ecrImages = (ecrRes.data?.imageDetails || []).map(img => ({
      tags: img.imageTags || [],
      digest: img.imageDigest?.slice(0, 20) + '…',
      pushed_at: img.imagePushedAt ? new Date(img.imagePushedAt * 1000).toISOString() : null,
      size_mb: img.imageSizeInBytes ? (img.imageSizeInBytes / 1048576).toFixed(1) : null,
    })).sort((a, b) => new Date(b.pushed_at) - new Date(a.pushed_at));

    // ── 4. ECR: get the manifest for the :latest tag to get its digest ─────
    let latestDigest = null;
    const latestImg = ecrImages.find(i => i.tags.includes('latest'));
    if (latestImg) latestDigest = latestImg.digest;

    // ── 5. Live API contract probe ─────────────────────────────────────────
    const liveProbe = await probeAuroraLiveContract(backendUrl);

    // ── 6. Mismatch analysis ───────────────────────────────────────────────
    const expectedImage = `${accountId}.dkr.ecr.${region}.amazonaws.com/${ecrRepo}:latest`;
    const imageMatchesExpected = taskDefImage === expectedImage;
    const liveIsStub = liveProbe.scan_polygon?.is_stub_response === true;
    const liveHasRealContract = liveProbe.scan_polygon?.has_scan_id && liveProbe.scan_polygon?.has_submitted_at;

    const mismatchEvidence = [];
    if (liveIsStub) {
      mismatchEvidence.push('STUB CONFIRMED: POST /api/v1/scan/polygon returns {status:"accepted"} without scan_id — source code returns {scan_id, scan_job_id, status, submitted_at}');
    }
    if (!liveHasRealContract) {
      mismatchEvidence.push('MISSING FIELDS: scan_id, scan_job_id, submitted_at absent from scan submission response');
    }
    if (ecrImages.length > 0) {
      const latestPush = ecrImages[0].pushed_at;
      mismatchEvidence.push(`ECR latest image pushed: ${latestPush} — if this predates aurora_vnext source, ECR itself is stale`);
    }

    // ── 7. CodeBuild projects list ─────────────────────────────────────────
    const cbRes = await awsRequest({ service: 'codebuild', action: 'ListProjects', body: {}, ...creds });
    const codebuildProjects = cbRes.data?.projects || [];

    return Response.json({
      timestamp: new Date().toISOString(),

      ecs: {
        cluster,
        service: serviceName,
        running_count: runningCount,
        active_task_def_arn: activeTaskDefArn,
        task_def_family: taskDefFamily,
        task_def_revision: taskDefRevision,
        container_image: taskDefImage,
        expected_image: expectedImage,
        image_matches_expected: imageMatchesExpected,
        deployments: deployments.map(d => ({ id: d.id, status: d.status, updated_at: d.updatedAt, task_def: d.taskDefinition?.split('/').pop() })),
      },

      ecr: {
        repository: ecrRepo,
        account: accountId,
        region,
        images: ecrImages.slice(0, 10),
        latest_digest: latestDigest,
        total_images: ecrImages.length,
      },

      live_api: {
        backend_url: backendUrl,
        ...liveProbe,
      },

      mismatch: {
        is_stub: liveIsStub,
        has_real_contract: liveHasRealContract,
        evidence: mismatchEvidence,
        verdict: liveIsStub
          ? 'CONFIRMED: deployed container is a stub, not aurora_vnext source'
          : liveHasRealContract
          ? 'PASS: live API returns real aurora_vnext contract'
          : 'PARTIAL: live API behavior unclear — check evidence above',
      },

      codebuild: {
        projects: codebuildProjects,
        note: codebuildProjects.length === 0
          ? 'No CodeBuild projects found — use auroraBuildAndDeploy to create one or trigger GitHub Actions'
          : `Found ${codebuildProjects.length} project(s). Pass project name to auroraBuildAndDeploy.`,
      },
    });

  } catch (e) {
    console.error('[auroraImageDiagnostics]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});