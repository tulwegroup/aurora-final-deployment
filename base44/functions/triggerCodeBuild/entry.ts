/**
 * triggerCodeBuild — Manually trigger AWS CodeBuild deployment
 * Uses AWS SDK v3 (available via npm:)
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AWS_REGION = 'us-east-1';
const BUILD_PROJECT = 'aurora-vnext-build';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const AWS_ACCESS_KEY_ID = Deno.env.get('AWS_ACCESS_KEY_ID');
    const AWS_SECRET_ACCESS_KEY = Deno.env.get('AWS_SECRET_ACCESS_KEY');

    if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY) {
      return Response.json(
        {
          status: 'error',
          message: 'AWS credentials not configured in secrets',
          action: 'Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in dashboard settings',
        },
        { status: 500 }
      );
    }

    // Make direct HTTP request to AWS CodeBuild API with SigV4 signing
    const payload = {
      projectName: BUILD_PROJECT,
      sourceVersion: 'main',
      environmentVariablesOverride: [
        { name: 'TRIGGERED_BY', value: user.email, type: 'PLAINTEXT' },
        { name: 'BUILD_TIMESTAMP', value: new Date().toISOString(), type: 'PLAINTEXT' },
      ],
    };

    const payloadJson = JSON.stringify(payload);
    const url = `https://codebuild.${AWS_REGION}.amazonaws.com/batch/start-build`;

    // Use AWS Signature Version 4
    const response = await makeAWSRequest(
      'POST',
      url,
      payloadJson,
      AWS_ACCESS_KEY_ID,
      AWS_SECRET_ACCESS_KEY,
      AWS_REGION
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('AWS CodeBuild API error:', errorText);

      return Response.json(
        {
          status: 'error',
          message: 'CodeBuild API request failed',
          http_status: response.status,
          fallback: `Manually trigger at: https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
        },
        { status: response.status }
      );
    }

    const buildData = await response.json();
    const buildId = buildData.build?.id;

    if (!buildId) {
      return Response.json(
        {
          status: 'error',
          message: 'No build ID in AWS response',
          details: buildData,
        },
        { status: 500 }
      );
    }

    return Response.json({
      status: 'success',
      build: {
        id: buildId,
        project: BUILD_PROJECT,
        initiated_by: user.email,
        initiated_at: new Date().toISOString(),
      },
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/build/${buildId}`,
    });
  } catch (error) {
    console.error('triggerCodeBuild error:', error.message);
    return Response.json(
      { status: 'error', message: error.message },
      { status: 500 }
    );
  }
});

/**
 * AWS Signature Version 4 signing
 */
async function makeAWSRequest(method, url, body, accessKeyId, secretAccessKey, region) {
  const service = 'codebuild';
  const host = `codebuild.${region}.amazonaws.com`;
  const now = new Date();
  
  // Format dates
  const amzDate = now.toISOString().replace(/[:-]/g, '').split('.')[0] + 'Z';
  const dateStamp = now.toISOString().split('T')[0].replace(/-/g, '');

  // Hash payload
  const payloadHash = await sha256Hash(body);

  // Canonical request
  const canonicalHeaders = `host:${host}\nx-amz-date:${amzDate}\n`;
  const signedHeaders = 'host;x-amz-date';
  const canonicalRequest = `${method}\n/batch/start-build\n\n${canonicalHeaders}\n${signedHeaders}\n${payloadHash}`;

  // String to sign
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const canonicalRequestHash = await sha256Hash(canonicalRequest);
  const stringToSign = `AWS4-HMAC-SHA256\n${amzDate}\n${credentialScope}\n${canonicalRequestHash}`;

  // Calculate signature
  const signature = await calculateSignature(stringToSign, secretAccessKey, dateStamp, region, service);

  // Authorization header
  const authHeader = `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  // Make request
  return fetch(url, {
    method,
    headers: {
      'Host': host,
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Date': amzDate,
      'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
      'Authorization': authHeader,
    },
    body,
  });
}

async function sha256Hash(data) {
  const encoder = new TextEncoder();
  const buffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

async function calculateSignature(stringToSign, secretAccessKey, dateStamp, region, service) {
  const encoder = new TextEncoder();
  
  // Key derivation
  const kSecret = encoder.encode('AWS4' + secretAccessKey);
  const kDate = await hmacSha256(kSecret, dateStamp);
  const kRegion = await hmacSha256(kDate, region);
  const kService = await hmacSha256(kRegion, service);
  const kSigning = await hmacSha256(kService, 'aws4_request');
  
  // Sign string
  const signature = await hmacSha256(kSigning, stringToSign);
  return signature;
}

async function hmacSha256(key, message) {
  const encoder = new TextEncoder();
  const keyData = key instanceof Uint8Array ? key : encoder.encode(key);
  const msgData = encoder.encode(message);

  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', cryptoKey, msgData);
  
  // Convert to hex if it's an ArrayBuffer, return as-is for Uint8Array
  if (signature instanceof ArrayBuffer) {
    const array = new Uint8Array(signature);
    return array.map(b => b.toString(16).padStart(2, '0')).join('');
  }
  return signature;
}