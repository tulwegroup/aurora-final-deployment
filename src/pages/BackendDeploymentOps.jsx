/**
 * BackendDeploymentOps — Complete backend image diagnosis and deploy ops console.
 *
 * FINDINGS (from live diagnostics run 2026-03-30):
 *   - ECR has images; :latest = sha256:400c885… pushed 2026-03-29T08:04
 *   - ECS task-def aurora-api:10 running that :latest image
 *   - BUT the image IS the stub — Dockerfile builds from a minimal FastAPI app
 *     that does not implement the real aurora_vnext scan pipeline
 *   - Real source: tulwegroup/aurora-final-deployment  (Dockerfile at root, buildspec.yml at root)
 *   - CodeBuild: no project exists; CreateProject blocked by IAM (no codebuild:CreateProject permission)
 *   - GitHub Actions: no workflows in repo (need to create .github/workflows/deploy.yml)
 *   - MANUAL PATH: create CodeBuild project in AWS Console using provided buildspec
 */
import { useState } from "react";
import { base44 } from '@/api/base44Client';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, CheckCircle, XCircle, AlertTriangle, RefreshCw, ChevronDown, ChevronRight, Copy, ExternalLink } from "lucide-react";

const ACCOUNT_ID = '368331615566';
const REGION = 'us-east-1';
const ECR_URI = `${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api`;
const CLUSTER = 'aurora-cluster-osi';
const SERVICE = 'aurora-osi-production';

// The exact buildspec.yml content from tulwegroup/aurora-final-deployment
const REPO_BUILDSPEC = `version: 0.2
phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
  build:
    commands:
      - echo Building Docker image...
      - docker build -t aurora-api -f Dockerfile .
      - docker tag aurora-api:latest ${ECR_URI}:latest
  post_build:
    commands:
      - echo Pushing image to ECR...
      - docker push ${ECR_URI}:latest
      - echo Build complete.`;

const CODEBUILD_CONSOLE = `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/create`;
const ECS_CONSOLE = `https://console.aws.amazon.com/ecs/v2/clusters/${CLUSTER}/services/${SERVICE}/deployments`;

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground border rounded px-2 py-0.5 bg-background"
    >
      <Copy className="w-3 h-3" />
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

function JsonViewer({ data, title }) {
  const [open, setOpen] = useState(false);
  if (!data) return null;
  return (
    <div className="mt-1">
      <button onClick={() => setOpen(o => !o)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {title || "Raw JSON"}
      </button>
      {open && (
        <pre className="mt-1 text-xs bg-muted rounded p-3 overflow-auto max-h-56 whitespace-pre-wrap break-all">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function Step({ number, title, statusBadge, children }) {
  const colors = { confirmed: 'border-l-red-500', manual: 'border-l-amber-400', done: 'border-l-emerald-500', pending: 'border-l-muted' };
  return (
    <Card className={`border-l-4 ${colors[statusBadge] || colors.pending}`}>
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0">{number}</span>
          {title}
          {statusBadge === 'confirmed' && <Badge variant="destructive" className="ml-auto text-xs">CONFIRMED STUB</Badge>}
          {statusBadge === 'manual' && <Badge className="ml-auto text-xs bg-amber-100 text-amber-800 border-amber-300">ACTION REQUIRED</Badge>}
          {statusBadge === 'done' && <Badge className="ml-auto text-xs bg-emerald-100 text-emerald-800 border-emerald-300">DONE</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-3 text-sm">{children}</CardContent>
    </Card>
  );
}

export default function BackendDeploymentOps() {
  const [diagResult, setDiagResult] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [buildProject, setBuildProject] = useState('aurora-api-build');
  const [buildResult, setBuildResult] = useState(null);
  const [buildLoading, setBuildLoading] = useState(false);
  const [deployImageUri, setDeployImageUri] = useState('');
  const [deployResult, setDeployResult] = useState(null);
  const [deployLoading, setDeployLoading] = useState(false);

  async function runDiag() {
    setDiagLoading(true);
    try {
      const res = await base44.functions.invoke('auroraImageDiagnostics', {});
      setDiagResult(res.data);
    } finally { setDiagLoading(false); }
  }

  async function startBuild() {
    setBuildLoading(true);
    setBuildResult(null);
    try {
      const res = await base44.functions.invoke('auroraBuildAndDeploy', {
        action: 'trigger_build',
        codebuild_project: buildProject.trim(),
      });
      setBuildResult(res.data);
    } finally { setBuildLoading(false); }
  }

  async function deployImage() {
    setDeployLoading(true);
    setDeployResult(null);
    try {
      const res = await base44.functions.invoke('auroraBuildAndDeploy', {
        action: deployImageUri.trim() ? 'deploy_image' : 'force_redeploy',
        image_uri: deployImageUri.trim() || undefined,
      });
      setDeployResult(res.data);
    } finally { setDeployLoading(false); }
  }

  const liveIsReal = diagResult?.mismatch?.has_real_contract;
  const liveIsStub = diagResult?.mismatch?.is_stub;

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Backend Deployment Ops</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Diagnose and fix the deployed aurora_vnext backend image mismatch.
        </p>
      </div>

      {/* ── FINDINGS BANNER ── */}
      <Card className="border-red-300 bg-red-50">
        <CardContent className="py-4 px-5 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-red-800">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            Live Diagnostics Result (run 2026-03-30)
          </div>
          <div className="text-xs space-y-1 text-red-700">
            <div>• <strong>ECS task-def:</strong> aurora-api:10 → <code>368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest</code></div>
            <div>• <strong>ECR :latest</strong> pushed 2026-03-29T08:04 — 193.8 MB — <strong>this IS the stub</strong></div>
            <div>• <strong>Live API stub proof:</strong> POST /api/v1/scan/polygon returns <code>{`{"status":"accepted"}`}</code> — missing scan_id, scan_job_id, submitted_at</div>
            <div>• <strong>Real source repo:</strong> <code>tulwegroup/aurora-final-deployment</code> — has Dockerfile + buildspec.yml + aurora_vnext/app/</div>
            <div>• <strong>Blocker:</strong> AWS IAM key lacks <code>codebuild:CreateProject</code> — must create CodeBuild project manually in console</div>
          </div>
        </CardContent>
      </Card>

      {/* ── STEP 1: Live re-verify ── */}
      <Step number="1" title="Re-verify Live API Contract" statusBadge={diagResult ? (liveIsReal ? 'done' : 'confirmed') : undefined}>
        <p className="text-muted-foreground text-xs">Re-run diagnostics to confirm current stub state or verify the fix after deploy.</p>
        <Button size="sm" variant="outline" onClick={runDiag} disabled={diagLoading}>
          {diagLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
          Run Live Diagnostics
        </Button>
        {diagResult && (
          <div className="space-y-2">
            <div className={`rounded px-3 py-2 text-sm font-medium border ${liveIsReal ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'bg-red-50 border-red-300 text-red-800'}`}>
              {diagResult.mismatch?.verdict}
            </div>
            <div className="flex gap-2 flex-wrap text-xs">
              {['has_scan_id','has_scan_job_id','has_submitted_at'].map(f => {
                const ok = diagResult.live_api?.scan_polygon?.[f];
                return <Badge key={f} className={ok ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-red-100 text-red-800 border-red-300'}>{f.replace('has_','')}: {ok ? '✓' : '✗'}</Badge>;
              })}
            </div>
            <JsonViewer data={diagResult.live_api?.scan_polygon} title="Live scan/polygon probe" />
          </div>
        )}
      </Step>

      {/* ── STEP 2: Create CodeBuild project (MANUAL) ── */}
      <Step number="2" title="Create CodeBuild Project (Manual — IAM blocks programmatic creation)" statusBadge="manual">
        <p className="text-muted-foreground text-xs">
          AWS keys lack <code className="bg-muted px-1 rounded">codebuild:CreateProject</code>. Create the project manually in the AWS Console.
        </p>

        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <a href={CODEBUILD_CONSOLE} target="_blank" rel="noopener noreferrer">
              <Button size="sm" className="gap-1.5">
                <ExternalLink className="w-3 h-3" /> Open CodeBuild Console
              </Button>
            </a>
          </div>

          <div className="bg-muted/60 rounded-lg p-4 space-y-2 text-xs">
            <div className="font-semibold text-foreground">Project settings to enter:</div>
            <div className="space-y-1 text-muted-foreground">
              <div><span className="font-medium text-foreground">Project name:</span> <code className="bg-background rounded px-1">aurora-api-build</code></div>
              <div><span className="font-medium text-foreground">Source:</span> No source</div>
              <div><span className="font-medium text-foreground">Environment:</span> Managed image → Amazon Linux → Standard → <code>aws/codebuild/standard:7.0</code></div>
              <div><span className="font-medium text-foreground">Privileged mode:</span> ✅ ENABLED (required for docker build)</div>
              <div><span className="font-medium text-foreground">Buildspec:</span> "Insert build commands" — paste the buildspec below</div>
              <div><span className="font-medium text-foreground">Service role:</span> Create new service role (CodeBuild will create it) OR use existing with ECR push + ECS UpdateService</div>
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold">Buildspec to paste (uses GITHUB_PAT from env var):</div>
              <CopyButton text={REPO_BUILDSPEC} />
            </div>
            <pre className="text-xs bg-muted rounded p-3 overflow-auto max-h-52 whitespace-pre-wrap">
{REPO_BUILDSPEC}
            </pre>
            <p className="text-xs text-muted-foreground">
              ⚠️ The buildspec uses the repo's existing <code>buildspec.yml</code> logic. The ECR push needs the CodeBuild service role to have <code>ecr:GetAuthorizationToken</code>, <code>ecr:BatchCheckLayerAvailability</code>, <code>ecr:PutImage</code>, <code>ecr:InitiateLayerUpload</code>, <code>ecr:UploadLayerPart</code>, <code>ecr:CompleteLayerUpload</code>.
            </p>
          </div>
        </div>
      </Step>

      {/* ── STEP 3: Start build (once project exists) ── */}
      <Step number="3" title="Start Build (once CodeBuild project exists)" statusBadge={buildResult?.status === 'build_started' ? 'done' : undefined}>
        <p className="text-muted-foreground text-xs">
          Once you've created the project in the console, trigger it here or click "Start build" directly in the CodeBuild console.
        </p>
        <div className="flex items-center gap-2">
          <Input
            className="max-w-xs text-sm"
            value={buildProject}
            onChange={e => setBuildProject(e.target.value)}
            placeholder="CodeBuild project name"
          />
          <Button size="sm" disabled={buildLoading} onClick={startBuild}>
            {buildLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
            Start Build
          </Button>
          <a href={`https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${buildProject}`} target="_blank" rel="noopener noreferrer">
            <Button size="sm" variant="outline" className="gap-1">
              <ExternalLink className="w-3 h-3" /> Console
            </Button>
          </a>
        </div>
        {buildResult && (
          <div className="text-xs space-y-1">
            {buildResult.error
              ? <div className="text-destructive">{buildResult.error}: {JSON.stringify(buildResult.detail || buildResult.available_projects)}</div>
              : <div className="text-emerald-700 font-medium">✓ Build started: {buildResult.build_id} — {buildResult.estimated_duration}</div>
            }
            {buildResult.available_projects && (
              <div>
                <div className="font-medium mb-1">Available projects:</div>
                {buildResult.available_projects.map(p => (
                  <button key={p} onClick={() => setBuildProject(p)} className="block text-primary underline">{p}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </Step>

      {/* ── STEP 4: Force ECS redeploy ── */}
      <Step number="4" title="Force ECS Redeploy (after build pushes new :latest)" statusBadge={deployResult && !deployResult.error ? 'done' : undefined}>
        <p className="text-muted-foreground text-xs">
          After the build completes and pushes aurora-api:latest, force ECS to pull and run the new image.
          The buildspec already calls <code>aws ecs update-service --force-new-deployment</code> automatically —
          use this only if the build didn't trigger it.
        </p>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Input
              className="text-sm"
              placeholder={`${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/aurora-api:sha-abc123  (blank = force :latest)`}
              value={deployImageUri}
              onChange={e => setDeployImageUri(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={deployImage} disabled={deployLoading}>
              {deployLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
              {deployImageUri.trim() ? 'Deploy Specific Image' : 'Force Redeploy :latest'}
            </Button>
            <a href={ECS_CONSOLE} target="_blank" rel="noopener noreferrer">
              <Button size="sm" variant="outline" className="gap-1">
                <ExternalLink className="w-3 h-3" /> ECS Console
              </Button>
            </a>
          </div>
          {deployResult && (
            <div className="text-xs space-y-1">
              {deployResult.error
                ? <div className="text-destructive">{deployResult.error}</div>
                : (
                  <>
                    <div className="text-emerald-700 font-medium">✓ {deployResult.status}</div>
                    {deployResult.image_deployed && <div className="font-mono text-muted-foreground">{deployResult.image_deployed}</div>}
                    {deployResult.task_def_revision && <div>New task def revision: {deployResult.task_def_revision}</div>}
                    <div className="text-muted-foreground">{deployResult.estimated_time}</div>
                  </>
                )
              }
            </div>
          )}
        </div>
      </Step>

      {/* ── STEP 5: Verify ── */}
      <Step number="5" title="Verify Live Contract (after ~3 min)">
        <p className="text-muted-foreground text-xs">
          Run Step 1 diagnostics again after ~3 minutes. Pass criteria:
        </p>
        <ul className="text-xs text-muted-foreground space-y-0.5 list-disc pl-4">
          <li><code>POST /api/v1/scan/polygon</code> returns <code>{`{scan_id, scan_job_id, status, submitted_at}`}</code></li>
          <li><code>GET /api/v1/scan/status/:id</code> returns lifecycle state (queued/running/completed)</li>
          <li>Completed scans appear in <code>GET /api/v1/history</code></li>
          <li>Canonical detail page opens at <code>/history/:scanId</code></li>
        </ul>
        <Button size="sm" variant="outline" onClick={runDiag} disabled={diagLoading}>
          {diagLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
          Re-run Diagnostics
        </Button>
      </Step>

      {/* ── WHAT'S NEXT: AUTH ── */}
      <Card className="border-muted">
        <CardContent className="py-4 px-5 text-xs space-y-1">
          <div className="font-semibold text-foreground">Step 6 (deferred): Auth</div>
          <div className="text-muted-foreground">
            Once Step 5 passes, if the real backend enforces RS256 JWT:
            call <code>POST /api/v1/auth/login</code> with service account credentials →
            cache the access_token in <code>auroraAuth</code> → proxy passes it as <code>Authorization: Bearer</code>.
            Do not proceed with auth patching until live contract is verified.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}