/**
 * checkALBHealth — Verify Application Load Balancer and targets are healthy
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function hmacSHA256(key, data) {
  const cryptoKey = await crypto.subtle.importKey('raw', typeof key === 'string' ? new TextEncoder().encode(key) : key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data)));
}

function toHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function signV4({ method, host, path, body, region, service, accessKeyId, secretAccessKey }) {
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);
  const bodyHash = await sha256Hex(body);
  const headers = { 'content-type': 'application/x-amz-json-1.1', 'host': host, 'x-amz-date': amzDate };
  const signedHeaders = Object.keys(headers).sort().join(';');
  const canonicalHeaders = Object.keys(headers).sort().map(k => `${k}:${headers[k]}`).join('\n') + '\n';
  const canonicalRequest = [method, path, '', canonicalHeaders, signedHeaders, bodyHash].join('\n');
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');
  const kDate = await hmacSHA256(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = await hmacSHA256(kDate, region);
  const kService = await hmacSHA256(kRegion, service);
  const kSigning = await hmacSHA256(kService, 'aws4_request');
  const signature = toHex(await hmacSHA256(kSigning, stringToSign));
  return { ...headers, authorization: `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}` };
}

async function albRequest({ action, body, region, accessKeyId, secretAccessKey }) {
  const host = `elasticloadbalancing.${region}.amazonaws.com`;
  const urlParams = new URLSearchParams({ Action: action, Version: '2015-12-01', ...body });
  const bodyStr = urlParams.toString();
  const headers = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service: 'elasticloadbalancing', accessKeyId, secretAccessKey });
  const res = await fetch(`https://${host}/`, { method: 'POST', headers, body: bodyStr });
  return { ok: res.ok, status: res.status, text: await res.text() };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (user?.role !== 'admin') {
      return Response.json({ error: 'Forbidden' }, { status: 403 });
    }

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const region = 'us-east-1';

    const creds = { region, accessKeyId, secretAccessKey };

    // Describe load balancers
    const lbRes = await albRequest({
      action: 'DescribeLoadBalancers',
      body: { 'LoadBalancerNames.member.1': 'aurora-alb' },
      ...creds
    });

    if (!lbRes.ok) {
      return Response.json({ error: 'Failed to describe ALB', healthy: false });
    }

    const dnsMatch = lbRes.text.match(/<DNSName>([^<]+)<\/DNSName>/);
    const albDns = dnsMatch ? dnsMatch[1] : 'unknown';
    const stateMatch = lbRes.text.match(/<State><Code>([^<]+)<\/Code>/);
    const albState = stateMatch ? stateMatch[1] : 'unknown';

    // Describe target health
    const tgRes = await albRequest({
      action: 'DescribeTargetHealth',
      body: { 'TargetGroupArn': 'arn:aws:elasticloadbalancing:us-east-1:368331615566:targetgroup/aurora-tg/abc123' },
      ...creds
    });

    const healthyTargets = (tgRes.text.match(/healthyCount/g) || []).length;
    const unhealthyTargets = (tgRes.text.match(/unhealthyCount/g) || []).length;
    const allHealthy = unhealthyTargets === 0 && healthyTargets > 0;

    return Response.json({
      loadBalancer: 'aurora-alb',
      dnsName: albDns,
      state: albState,
      healthy: albState === 'active' && allHealthy,
      healthyTargets,
      unhealthyTargets,
      region,
      consoleUrl: `https://console.aws.amazon.com/ec2/v2/home?region=${region}#LoadBalancers:`,
      detail: albState === 'active' && allHealthy ? 'ALB and all targets healthy' : 'ALB starting or targets initializing'
    });

  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});