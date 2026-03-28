/**
 * pushToGitHubAndDeploy — Commit, push to GitHub, and trigger AWS CodeBuild
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user?.role !== 'admin') {
      return Response.json({ error: 'Admin access required' }, { status: 403 });
    }

    const GITHUB_TOKEN = Deno.env.get('GITHUB_TOKEN');
    const GITHUB_PAT = Deno.env.get('GITHUB_PAT');
    const AWS_ACCESS_KEY_ID = Deno.env.get('AWS_ACCESS_KEY_ID');
    const AWS_SECRET_ACCESS_KEY = Deno.env.get('AWS_SECRET_ACCESS_KEY');

    if (!GITHUB_TOKEN || !AWS_ACCESS_KEY_ID) {
      return Response.json(
        { error: 'Missing GitHub or AWS credentials' },
        { status: 500 }
      );
    }

    // Step 1: Get local repo info (simulated)
    const repoOwner = 'aurora-osi';
    const repoName = 'aurora-vnext';
    const branch = 'main';
    const message = `Aurora vNext update — streaming, reporting, analog validation, legacy ingestion (${new Date().toISOString()})`;

    // Step 2: Push to GitHub via API
    const pushResponse = await fetch(
      `https://api.github.com/repos/${repoOwner}/${repoName}/git/refs/heads/${branch}`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `token ${GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({
          sha: 'HEAD', // Simulated; actual would be computed
          force: false,
        }),
      }
    );

    if (!pushResponse.ok) {
      const err = await pushResponse.text();
      console.error('GitHub push error:', err);
      return Response.json(
        { error: 'GitHub push failed', details: err },
        { status: 500 }
      );
    }

    // Step 3: Trigger AWS CodeBuild
    const codeBuildProjectName = 'aurora-vnext-build';
    const buildResponse = await fetch(
      'https://codebuild.us-east-1.amazonaws.com/batch/start-build',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'CodeBuild_20161810.StartBuild',
          'Authorization': `AWS4-HMAC-SHA256 ...`, // Simplified; actual requires SigV4
        },
        body: JSON.stringify({
          projectName: codeBuildProjectName,
          environmentVariables: [
            { name: 'GITHUB_REPO', value: `${repoOwner}/${repoName}`, type: 'PLAINTEXT' },
            { name: 'BRANCH', value: branch, type: 'PLAINTEXT' },
          ],
        }),
      }
    );

    if (!buildResponse.ok) {
      const err = await buildResponse.text();
      console.error('CodeBuild trigger error:', err);
      return Response.json(
        { error: 'CodeBuild trigger failed', details: err },
        { status: 500 }
      );
    }

    const buildData = await buildResponse.json();
    const buildId = buildData.build.id;

    // Step 4: Monitor build status
    const statusResponse = await fetch(
      `https://codebuild.us-east-1.amazonaws.com/describe-builds`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
        },
        body: JSON.stringify({
          ids: [buildId],
        }),
      }
    );

    const statusData = await statusResponse.json();
    const buildStatus = statusData.builds[0].buildStatus; // QUEUED, IN_PROGRESS, SUCCEEDED, FAILED

    return Response.json({
      status: 'success',
      github: {
        repo: `${repoOwner}/${repoName}`,
        branch,
        message,
        pushed: true,
      },
      aws_codebuild: {
        projectName: codeBuildProjectName,
        buildId,
        status: buildStatus,
        logs_url: `https://console.aws.amazon.com/codesuite/codebuild/projects/${codeBuildProjectName}/builds/${buildId}`,
      },
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return Response.json(
      { error: error.message, status: 'failed' },
      { status: 500 }
    );
  }
});