/**
 * patchGitHubRepo — Push aurora_vnext code to GitHub and trigger rebuild.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const PROJECT_NAME = 'aurora-api-build';
const REPO_OWNER = 'tulwegroup';
const REPO_NAME = 'aurora-final-deployment';
const BRANCH = 'main';

async function ghFileSha(token, path) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}?ref=${BRANCH}`,
    { headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json' } }
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`gh getSha ${path}: ${res.status}`);
  return (await res.json()).sha || null;
}

async function ghPush(token, path, content, msg, sha) {
  const b64 = btoa(unescape(encodeURIComponent(content)));
  const body = { message: msg, content: b64, branch: BRANCH };
  if (sha) body.sha = sha;
  const res = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`,
    {
      method: 'PUT',
      headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`gh push ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const githubToken = Deno.env.get('GITHUB_PAT') || Deno.env.get('GITHUB_TOKEN');
    if (!githubToken) return Response.json({ error: 'GITHUB_PAT not set' }, { status: 500 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });

    const body = await req.json().catch(() => ({}));
    const action = body.action || 'push_and_build';

    if (action === 'check_repo') {
      // Just read existing files to diagnose
      const [mainRes, reqRes, dockerRes] = await Promise.all([
        fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/main.py?ref=${BRANCH}`, { headers: { Authorization: `token ${githubToken}`, Accept: 'application/vnd.github+json' } }),
        fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/requirements.txt?ref=${BRANCH}`, { headers: { Authorization: `token ${githubToken}`, Accept: 'application/vnd.github+json' } }),
        fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/Dockerfile?ref=${BRANCH}`, { headers: { Authorization: `token ${githubToken}`, Accept: 'application/vnd.github+json' } }),
      ]);
      const mainData = mainRes.ok ? await mainRes.json() : null;
      const reqData = reqRes.ok ? await reqRes.json() : null;
      const dockerData = dockerRes.ok ? await dockerRes.json() : null;

      const mainContent = mainData?.content ? atob(mainData.content.replace(/\n/g,'')) : null;
      const reqContent = reqData?.content ? atob(reqData.content.replace(/\n/g,'')) : null;
      const dockerContent = dockerData?.content ? atob(dockerData.content.replace(/\n/g,'')) : null;

      return Response.json({
        repo: `${REPO_OWNER}/${REPO_NAME}`,
        branch: BRANCH,
        files: {
          'main.py': mainContent ? { found: true, has_auth: mainContent.includes('/api/v1/auth/login'), size: mainContent.length, sha: mainData.sha, snippet: mainContent.slice(0, 300) } : { found: false },
          'requirements.txt': reqContent ? { found: true, has_bcrypt: reqContent.includes('bcrypt'), has_pyjwt: reqContent.includes('PyJWT') || reqContent.includes('pyjwt'), content: reqContent } : { found: false },
          'Dockerfile': dockerContent ? { found: true, content: dockerContent } : { found: false },
        },
      });
    }

    // push_and_build: get the content from the request body
    const { main_py, requirements_txt, dockerfile } = body;
    if (!main_py) return Response.json({ error: 'main_py content required in body' }, { status: 400 });

    const msg = `Aurora: auth routes + deps fix (${new Date().toISOString()})`;
    console.log('[patchGitHubRepo] Fetching SHAs...');
    const [mainSha, reqSha, dockerSha] = await Promise.all([
      ghFileSha(githubToken, 'main.py'),
      requirements_txt ? ghFileSha(githubToken, 'requirements.txt') : Promise.resolve(null),
      dockerfile ? ghFileSha(githubToken, 'Dockerfile') : Promise.resolve(null),
    ]);

    console.log('[patchGitHubRepo] Pushing files...');
    const pushOps = [ghPush(githubToken, 'main.py', main_py, msg, mainSha)];
    if (requirements_txt) pushOps.push(ghPush(githubToken, 'requirements.txt', requirements_txt, msg, reqSha));
    if (dockerfile) pushOps.push(ghPush(githubToken, 'Dockerfile', dockerfile, msg, dockerSha));
    await Promise.all(pushOps);
    console.log('[patchGitHubRepo] Pushed successfully, triggering build...');

    const cbClient = new CodeBuildClient({ region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } });
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));
    const build = buildRes.build;

    return Response.json({
      status: 'pushed_and_build_started',
      files_updated: ['main.py', requirements_txt ? 'requirements.txt' : null, dockerfile ? 'Dockerfile' : null].filter(Boolean),
      build_id: build?.id,
      build_status: build?.buildStatus,
      estimated_build_time: '8-12 minutes',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${PROJECT_NAME}`,
    });

  } catch (e) {
    console.error('[patchGitHubRepo]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});