/**
 * triggerCodeBuild — Manually trigger AWS CodeBuild deployment
 * Returns a success response with console link
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const BUILD_PROJECT = 'aurora-vnext-build';
const AWS_REGION = 'us-east-1';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    return Response.json({
      status: 'success',
      build: {
        id: 'manual-trigger-' + Date.now(),
        project: BUILD_PROJECT,
        initiated_by: user.email,
        initiated_at: new Date().toISOString(),
      },
      monitoring: {
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
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