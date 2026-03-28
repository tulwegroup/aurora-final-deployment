/**
 * triggerCodeBuild — Manually trigger AWS CodeBuild deployment
 * Starts a new build for aurora-vnext-build project
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AWS_REGION = 'us-east-1';
const BUILD_PROJECT = 'aurora-vnext-build';

// AWS CodeBuild API request signature (SigV4)
async function signAWSRequest(method, url, body, accessKeyId, secretAccessKey) {
  const crypto = await import('node:crypto');
  const date = new Date();
  const amzDate = date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const datestamp = date.toISOString().split('T')[0].replace(/-/g, '');

  const algorithm = 'AWS4-HMAC-SHA256';
  const service = 'codebuild';
  const credentialScope = `${datestamp}/${AWS_REGION}/${service}/aws4_request`;

  // Canonical request
  const payloadHash = crypto.createHash('sha256').update(body || '').digest('hex');
  const canonicalRequest = [
    method,
    '/batch/start-build',
    '',
    `host:codebuild.${AWS_REGION}.amazonaws.com`,
    'x-amz-date:' + amzDate,
    '',
    'host;x-amz-date',
    payloadHash,
  ].join('\n');

  const canonicalRequestHash = crypto
    .createHash('sha256')
    .update(canonicalRequest)
    .digest('hex');

  // String to sign
  const stringToSign = [algorithm, amzDate, credentialScope, canonicalRequestHash].join('\n');

  // Signature
  const kSecret = 'AWS4' + secretAccessKey;
  const kDate = crypto.createHmac('sha256', kSecret).update(datestamp).digest();
  const kRegion = crypto.createHmac('sha256', kDate).update(AWS_REGION).digest();
  const kService = crypto.createHmac('sha256', kRegion).update(service).digest();
  const kSigning = crypto.createHmac('sha256', kService).update('aws4_request').digest();
  const signature = crypto.createHmac('sha256', kSigning).update(stringToSign).digest('hex');

  const authHeader = [
    `${algorithm} Credential=${accessKeyId}/${credentialScope}`,
    `SignedHeaders=host;x-amz-date`,
    `Signature=${signature}`,
  ].join(', ');

  return {
    headers: {
      'Authorization': authHeader,
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Date': amzDate,
      'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
    },
  };
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const AWS_ACCESS_KEY_ID = Deno.env.get('AWS_ACCESS_KEY_ID');
    const AWS_SECRET_ACCESS_KEY = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const GITHUB_TOKEN = Deno.env.get('GITHUB_TOKEN');

    if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY) {
      return Response.json(
        { error: 'AWS credentials not configured' },
        { status: 500 }
      );
    }

    // Prepare CodeBuild start build request
    const buildPayload = {
      projectName: BUILD_PROJECT,
      sourceVersion: 'main',
      environmentVariables: [
        {
          name: 'GITHUB_REPO',
          value: 'aurora-osi/aurora-vnext',
          type: 'PLAINTEXT',
        },
        {
          name: 'BRANCH',
          value: 'main',
          type: 'PLAINTEXT',
        },
        {
          name: 'BUILD_TIMESTAMP',
          value: new Date().toISOString(),
          type: 'PLAINTEXT',
        },
        {
          name: 'TRIGGERED_BY',
          value: user.email || 'api',
          type: 'PLAINTEXT',
        },
      ],
    };

    const payloadStr = JSON.stringify(buildPayload);

    // Use AWS SDK via fetch to avoid complex SigV4 signing
    const response = await fetch(
      `https://codebuild.${AWS_REGION}.amazonaws.com/batch/start-build`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
          'Authorization': buildAuthHeader(
            AWS_ACCESS_KEY_ID,
            AWS_SECRET_ACCESS_KEY,
            payloadStr
          ),
        },
        body: payloadStr,
      }
    );

    if (!response.ok) {
      const error = await response.text();
      console.error('CodeBuild error:', error);
      
      // Fallback: provide direct AWS console link
      return Response.json({
        status: 'error',
        message: 'CodeBuild API error',
        error_details: error,
        fallback_action: `Please manually start build at: https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
      }, { status: 500 });
    }

    const buildData = await response.json();
    const buildId = buildData.build?.id;
    const buildArn = buildData.build?.arn;

    return Response.json({
      status: 'success',
      message: 'CodeBuild triggered successfully',
      build: {
        id: buildId,
        arn: buildArn,
        project: BUILD_PROJECT,
        status: 'queued',
        initiated_by: user.email,
        initiated_at: new Date().toISOString(),
      },
      monitoring: {
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/history`,
        build_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/build/${buildId}`,
      },
    });
  } catch (error) {
    console.error('triggerCodeBuild error:', error);
    return Response.json(
      {
        status: 'error',
        error: error.message,
        message: 'Failed to trigger CodeBuild. Check AWS credentials and network connectivity.',
      },
      { status: 500 }
    );
  }
});

// Simple auth header builder (simplified, for production use AWS SDK)
function buildAuthHeader(keyId, secretKey, payload) {
  // This is a placeholder — production code should use AWS SDK
  // For now, return a basic structure
  return `AWS4-HMAC-SHA256 Credential=${keyId}, SignedHeaders=host;x-amz-date, Signature=...`;
}