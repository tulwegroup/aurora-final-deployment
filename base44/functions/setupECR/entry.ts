/**
 * setupECR — Create ECR repository and return push commands
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

async function hmacSHA256(key, data) {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    typeof key === 'string' ? new TextEncoder().encode(key) : key,
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  return new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data)));
}

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
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

async function ecrRequest({ target, body, region, accessKeyId, secretAccessKey }) {
  const host = `ecr.${region}.amazonaws.com`;
  const bodyStr = JSON.stringify(body);
  const headers = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service: 'ecr', accessKeyId, secretAccessKey });
  headers['x-amz-target'] = target;
  const res = await fetch(`https://${host}/`, { method: 'POST', headers, body: bodyStr });
  const json = await res.json();
  return { ok: res.ok, data: json };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const awsAccessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const region = 'us-east-1';
    const accountId = '368331615566';
    const repoName = 'aurora-api';

    const creds = { region, accessKeyId: awsAccessKeyId, secretAccessKey: awsSecretAccessKey };

    // Try to create repo (ignore if already exists)
    const createRes = await ecrRequest({
      target: 'AmazonEC2ContainerRegistry_V20150921.CreateRepository',
      body: {
        repositoryName: repoName,
        imageScanningConfiguration: { scanOnPush: true },
        encryptionConfiguration: { encryptionType: 'AES256' }
      },
      ...creds
    });

    const repoUri = createRes.ok
      ? createRes.data.repository.repositoryUri
      : `${accountId}.dkr.ecr.${region}.amazonaws.com/${repoName}`;

    const imageTag = `${repoUri}:latest`;

    return Response.json({
      status: 'success',
      repoUri,
      imageTag,
      accountId,
      region,
      commands: [
        `# Step 1: Authenticate Docker to ECR`,
        `aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${accountId}.dkr.ecr.${region}.amazonaws.com`,
        ``,
        `# Step 2: Build the Docker image (run from aurora_vnext directory)`,
        `cd aurora_vnext`,
        `docker build -f infra/docker/Dockerfile.api -t ${imageTag} .`,
        ``,
        `# Step 3: Push to ECR`,
        `docker push ${imageTag}`,
        ``,
        `# Step 4: Come back here and click "Update ECS Service" once push is done`,
      ]
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});