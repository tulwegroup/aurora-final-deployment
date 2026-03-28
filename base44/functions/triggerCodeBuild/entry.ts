/**
 * triggerCodeBuild — Manually trigger AWS CodeBuild deployment via AWS CLI
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
    const AURORA_DB_HOST = Deno.env.get('AURORA_DB_HOST');

    if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY) {
      return Response.json(
        {
          status: 'error',
          message: 'AWS credentials not configured in secrets',
          action: 'Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY',
        },
        { status: 500 }
      );
    }

    // Use AWS CLI via subprocess to trigger build
    const command = new Deno.Command('aws', {
      args: [
        'codebuild',
        'start-build',
        `--project-name=${BUILD_PROJECT}`,
        `--region=${AWS_REGION}`,
        '--environment-variables-override',
        `name=TRIGGERED_BY,value=${user.email},type=PLAINTEXT`,
        `name=BUILD_TIMESTAMP,value=${new Date().toISOString()},type=PLAINTEXT`,
      ],
      env: {
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_DEFAULT_REGION: AWS_REGION,
      },
      stdout: 'piped',
      stderr: 'piped',
    });

    const process = command.spawn();
    const { success, stdout, stderr } = await process.output();

    if (!success) {
      const errorMsg = new TextDecoder().decode(stderr);
      console.error('AWS CLI error:', errorMsg);

      // Provide fallback manual link
      if (errorMsg.includes('NoCredentialsError') || errorMsg.includes('InvalidClientTokenId')) {
        return Response.json(
          {
            status: 'error',
            message: 'AWS credentials invalid',
            details: 'Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct',
            fallback_action: `Visit: https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
          },
          { status: 401 }
        );
      }

      return Response.json(
        {
          status: 'error',
          message: 'Failed to start CodeBuild',
          details: errorMsg.slice(0, 300),
          fallback_action: `Visit: https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}`,
        },
        { status: 500 }
      );
    }

    const output = JSON.parse(new TextDecoder().decode(stdout));
    const buildId = output.build?.id;

    if (!buildId) {
      return Response.json(
        {
          status: 'error',
          message: 'No build ID returned from AWS',
        },
        { status: 500 }
      );
    }

    return Response.json({
      status: 'success',
      message: 'CodeBuild triggered successfully',
      build: {
        id: buildId,
        project: BUILD_PROJECT,
        status: 'queued',
        initiated_by: user.email,
        initiated_at: new Date().toISOString(),
      },
      monitoring: {
        console_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/history`,
        build_log_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${BUILD_PROJECT}/history?builds=${buildId}`,
      },
    });
  } catch (error) {
    console.error('triggerCodeBuild error:', error.message);
    return Response.json(
      {
        status: 'error',
        message: error.message || 'Failed to trigger CodeBuild',
      },
      { status: 500 }
    );
  }
});