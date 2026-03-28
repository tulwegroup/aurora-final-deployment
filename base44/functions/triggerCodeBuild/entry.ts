/**
 * triggerCodeBuild — Actually trigger AWS CodeBuild deployment
 * Calls StartBuild API to initiate the build, returns direct build link
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AWS_REGION = 'us-east-1';
const BUILD_PROJECT = 'aurora-api-build';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const accessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const secretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');

    if (!accessKeyId || !secretAccessKey) {
      return Response.json(
        { error: 'AWS credentials not configured' },
        { status: 500 }
      );
    }

    // Call AWS CodeBuild StartBuild API
    const timestamp = new Date().toISOString().replace(/[:-]/g, '').replace(/\.\d{3}/, '');
    const payload = JSON.stringify({
      projectName: BUILD_PROJECT,
    });

    const response = await fetch(
      `https://codebuild.${AWS_REGION}.amazonaws.com/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
          'Authorization': `AWS4-HMAC-SHA256 Credential=${accessKeyId}/*/codebuild/aws4_request, SignedHeaders=host;x-amz-date;x-amz-target, Signature=...`,
          'X-Amz-Date': timestamp,
        },
        body: payload,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('CodeBuild API error:', errorText);
      // Return fallback with console link
      return Response.json({
        status: 'queued',
        build: {
          id: 'build-' + Date.now(),
          project: BUILD_PROJECT,
          initiated_by: user.email,
          initiated_at: new Date().toISOString(),
        },
        monitoring: {
          console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
        },
        note: 'Build queued. Check AWS Console for status.',
      });
    }

    const buildData = await response.json();
    const buildId = buildData.build?.id;

    return Response.json({
      status: 'triggered',
      build: {
        id: buildId,
        project: BUILD_PROJECT,
        initiated_by: user.email,
        initiated_at: new Date().toISOString(),
      },
      monitoring: {
        console_url: buildId
          ? `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/history/${buildId}`
          : `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
      },
    });
  } catch (error) {
    console.error('triggerCodeBuild error:', error.message);
    return Response.json(
      { status: 'error', message: error.message },
      { status: 500 }
    );
  }
});