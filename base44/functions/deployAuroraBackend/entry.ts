/**
 * deployAuroraBackend
 *
 * Triggers an AWS CodeBuild project to build the aurora_vnext Docker image
 * from the current source, push it to ECR, and force an ECS redeployment.
 *
 * ADMIN ONLY.
 *
 * Environment variables required:
 *   AWS_ACCESS_KEY_ID
 *   AWS_SECRET_ACCESS_KEY
 *   AURORA_CODEBUILD_PROJECT  (default: "aurora-api-build")
 *   AURORA_AWS_REGION         (default: "us-east-1")
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// AWS SigV4 signing helper (minimal, for CodeBuild)
async function signedRequest({ region, service, method, url, body, accessKeyId, secretAccessKey }) {
  const date = new Date();
  const amzDate = date.toISOString().replace(/[:-]|\.\d{3}/g, '').slice(0, 15) + 'Z'; // YYYYMMDDTHHmmssZ
  const dateStamp = amzDate.slice(0, 8);

  const urlObj = new URL(url);
  const canonicalUri = urlObj.pathname;
  const canonicalQueryString = '';
  const host = urlObj.hostname;

  const bodyHash = await sha256Hex(body || '');
  const canonicalHeaders = `content-type:application/x-amz-json-1.1\nhost:${host}\nx-amz-date:${amzDate}\n`;
  const signedHeaders = 'content-type;host;x-amz-date';
  const canonicalRequest = [method, canonicalUri, canonicalQueryString, canonicalHeaders, signedHeaders, bodyHash].join('\n');

  const algorithm = 'AWS4-HMAC-SHA256';
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = [algorithm, amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');

  const signingKey = await getSigningKey(secretAccessKey, dateStamp, region, service);
  const signature = await hmacHex(signingKey, stringToSign);
  const authHeader = `${algorithm} Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  return {
    'Content-Type': 'application/x-amz-json-1.1',
    'X-Amz-Date': amzDate,
    'Authorization': authHeader,
  };
}

async function sha256Hex(data) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function hmacRaw(key, data) {
  const k = typeof key === 'string'
    ? await crypto.subtle.importKey('raw', new TextEncoder().encode(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
    : await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(data)));
}

async function hmacHex(key, data) {
  const raw = await hmacRaw(key, data);
  return Array.from(raw).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function getSigningKey(secretKey, dateStamp, region, service) {
  const kDate    = await hmacRaw('AWS4' + secretKey, dateStamp);
  const kRegion  = await hmacRaw(kDate, region);
  const kService = await hmacRaw(kRegion, service);
  return await hmacRaw(kService, 'aws4_request');
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') {
      return Response.json({ error: 'Admin access required' }, { status: 403 });
    }

    const accessKeyId     = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const region          = Deno.env.get('AURORA_AWS_REGION') || 'us-east-1';
    const projectName     = Deno.env.get('AURORA_CODEBUILD_PROJECT') || 'aurora-api-build';

    if (!accessKeyId || !secretAccessKey) {
      return Response.json({ error: 'AWS credentials not configured' }, { status: 500 });
    }

    const url  = `https://codebuild.${region}.amazonaws.com/`;
    const body = JSON.stringify({ projectName });

    const headers = await signedRequest({
      region, service: 'codebuild',
      method: 'POST', url, body,
      accessKeyId, secretAccessKey,
    });

    console.log(`[deployAuroraBackend] Starting CodeBuild project: ${projectName}`);
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        ...headers,
        'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
      },
      body,
    });

    const data = await res.json();

    if (!res.ok) {
      console.error('[deployAuroraBackend] CodeBuild error:', JSON.stringify(data));
      return Response.json({ error: 'CodeBuild start failed', detail: data }, { status: 500 });
    }

    const buildId = data.build?.id;
    console.log(`[deployAuroraBackend] Build started: ${buildId}`);

    return Response.json({
      status: 'build_started',
      build_id: buildId,
      project: projectName,
      region,
      message: 'CodeBuild triggered. ECS will be updated when the build completes (~5-10 min).',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${region}/projects/${projectName}/build/${buildId?.replace(':', '%3A')}`,
    });

  } catch (e) {
    console.error('[deployAuroraBackend] Error:', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});