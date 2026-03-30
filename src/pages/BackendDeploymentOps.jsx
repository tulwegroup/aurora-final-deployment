/**
 * BackendDeploymentOps
 * 
 * Step-by-step operator console for:
 * 1. Proving ECS image mismatch
 * 2. Building and deploying the real aurora_vnext backend
 * 3. Verifying the live API contract post-deploy
 */
import { useState } from "react";
import { base44 } from '@/api/base44Client';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, CheckCircle, XCircle, AlertTriangle, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";

function StatusBadge({ ok, trueLabel = "PASS", falseLabel = "FAIL" }) {
  return ok
    ? <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300">{trueLabel}</Badge>
    : <Badge variant="destructive">{falseLabel}</Badge>;
}

function JsonViewer({ data, title }) {
  const [open, setOpen] = useState(false);
  if (!data) return null;
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(o => !o)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {title || "Raw JSON"}
      </button>
      {open && (
        <pre className="mt-1 text-xs bg-muted rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap break-all">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function Step({ number, title, status, children }) {
  const borderColor = status === 'pass' ? 'border-l-emerald-500' : status === 'fail' ? 'border-l-red-500' : status === 'running' ? 'border-l-blue-400' : 'border-l-muted';
  return (
    <Card className={`border-l-4 ${borderColor}`}>
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0">{number}</span>
          {title}
          {status === 'pass' && <CheckCircle className="w-4 h-4 text-emerald-600 ml-auto" />}
          {status === 'fail' && <XCircle className="w-4 h-4 text-red-500 ml-auto" />}
          {status === 'running' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin ml-auto" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-2 text-sm">{children}</CardContent>
    </Card>
  );
}

export default function BackendDeploymentOps() {
  const [diag, setDiag] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);

  const [buildProject, setBuildProject] = useState('');
  const [deployImageUri, setDeployImageUri] = useState('');
  const [buildResult, setBuildResult] = useState(null);
  const [buildLoading, setBuildLoading] = useState(false);

  const [deployResult, setDeployResult] = useState(null);
  const [deployLoading, setDeployLoading] = useState(false);

  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyLoading, setVerifyLoading] = useState(false);

  async function runDiagnostics() {
    setDiagLoading(true);
    setDiag(null);
    try {
      const res = await base44.functions.invoke('auroraImageDiagnostics', {});
      setDiag(res.data);
    } finally {
      setDiagLoading(false);
    }
  }

  async function triggerBuild() {
    if (!buildProject.trim()) return;
    setBuildLoading(true);
    setBuildResult(null);
    try {
      const res = await base44.functions.invoke('auroraBuildAndDeploy', {
        action: 'trigger_build',
        codebuild_project: buildProject.trim(),
      });
      setBuildResult(res.data);
    } finally {
      setBuildLoading(false);
    }
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
    } finally {
      setDeployLoading(false);
    }
  }

  async function verifyContract() {
    setVerifyLoading(true);
    setVerifyResult(null);
    try {
      const res = await base44.functions.invoke('auroraImageDiagnostics', {});
      setVerifyResult(res.data);
    } finally {
      setVerifyLoading(false);
    }
  }

  const isStub = diag?.mismatch?.is_stub;
  const hasRealContract = diag?.mismatch?.has_real_contract;
  const verifyIsReal = verifyResult?.mismatch?.has_real_contract;

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Backend Deployment Ops</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Diagnose, fix, and verify the deployed aurora_vnext backend image.
        </p>
      </div>

      {/* ── STEP 1: Prove mismatch ── */}
      <Step number="1" title="Prove Image Mismatch" status={diag ? (isStub ? 'fail' : hasRealContract ? 'pass' : 'fail') : undefined}>
        <p className="text-muted-foreground">
          Reads ECS task definition, ECR image registry, and probes the live API contract to confirm whether the deployed container is the real aurora_vnext source or a stub.
        </p>
        <Button onClick={runDiagnostics} disabled={diagLoading} variant="outline" size="sm">
          {diagLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
          Run Diagnostics
        </Button>

        {diag && (
          <div className="space-y-3 mt-2">
            {/* Verdict */}
            <div className={`rounded-lg px-4 py-3 text-sm font-medium border ${isStub ? 'bg-red-50 border-red-300 text-red-800' : hasRealContract ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'bg-amber-50 border-amber-300 text-amber-800'}`}>
              {diag.mismatch?.verdict}
            </div>

            {/* Evidence list */}
            {diag.mismatch?.evidence?.length > 0 && (
              <ul className="space-y-1">
                {diag.mismatch.evidence.map((e, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0 mt-0.5" />
                    {e}
                  </li>
                ))}
              </ul>
            )}

            {/* ECS + ECR summary */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-muted/40 rounded p-3 space-y-1">
                <div className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px]">ECS Task Definition</div>
                <div><span className="text-muted-foreground">Image:</span> <span className="font-mono break-all">{diag.ecs?.container_image || '—'}</span></div>
                <div><span className="text-muted-foreground">Revision:</span> {diag.ecs?.task_def_revision || '—'}</div>
                <div><span className="text-muted-foreground">Running tasks:</span> {diag.ecs?.running_count ?? '—'}</div>
              </div>
              <div className="bg-muted/40 rounded p-3 space-y-1">
                <div className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px]">ECR Images</div>
                {(diag.ecr?.images || []).slice(0, 4).map((img, i) => (
                  <div key={i} className="flex items-center gap-2 flex-wrap">
                    {img.tags.map(t => <span key={t} className="font-mono bg-muted rounded px-1">{t}</span>)}
                    <span className="text-muted-foreground">{img.pushed_at?.slice(0, 10)}</span>
                    <span className="text-muted-foreground">{img.size_mb}MB</span>
                  </div>
                ))}
                {!diag.ecr?.images?.length && <div className="text-muted-foreground">No images found</div>}
              </div>
            </div>

            {/* Live API scan polygon probe */}
            <div className="bg-muted/40 rounded p-3 text-xs space-y-1">
              <div className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px]">Live API: POST /api/v1/scan/polygon</div>
              <div className="flex items-center gap-2">
                <StatusBadge ok={diag.live_api?.scan_polygon?.has_scan_id} trueLabel="scan_id ✓" falseLabel="scan_id ✗" />
                <StatusBadge ok={diag.live_api?.scan_polygon?.has_scan_job_id} trueLabel="scan_job_id ✓" falseLabel="scan_job_id ✗" />
                <StatusBadge ok={diag.live_api?.scan_polygon?.has_submitted_at} trueLabel="submitted_at ✓" falseLabel="submitted_at ✗" />
                {diag.live_api?.scan_polygon?.is_stub_response && <Badge variant="destructive">STUB</Badge>}
              </div>
              <div className="font-mono text-muted-foreground">HTTP {diag.live_api?.scan_polygon?.status}</div>
            </div>

            {/* CodeBuild projects */}
            {diag.codebuild?.projects?.length > 0 && (
              <div className="text-xs text-muted-foreground">
                <span className="font-semibold">CodeBuild projects found: </span>
                {diag.codebuild.projects.join(', ')}
              </div>
            )}

            <JsonViewer data={diag} title="Full diagnostics JSON" />
          </div>
        )}
      </Step>

      {/* ── STEP 2: Trigger build ── */}
      <Step number="2" title="Trigger CodeBuild (build real aurora_vnext image)" status={buildResult ? (buildResult.error ? 'fail' : 'pass') : undefined}>
        <p className="text-muted-foreground">
          Starts the CodeBuild project that builds the real Dockerfile from your GitHub source and pushes to ECR. Get the project name from Step 1 diagnostics.
        </p>
        <div className="flex items-center gap-2">
          <Input
            className="max-w-xs text-sm"
            placeholder="CodeBuild project name…"
            value={buildProject}
            onChange={e => setBuildProject(e.target.value)}
          />
          <Button size="sm" disabled={buildLoading || !buildProject.trim()} onClick={triggerBuild}>
            {buildLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
            Start Build
          </Button>
        </div>
        {buildResult && (
          <div className="space-y-2 mt-1">
            {buildResult.error
              ? <div className="text-destructive text-xs">{buildResult.error}</div>
              : (
                <div className="text-xs space-y-1">
                  <div className="text-emerald-700 font-medium">Build started: {buildResult.build_id}</div>
                  <div className="text-muted-foreground">{buildResult.estimated_duration}</div>
                  {buildResult.console_url && (
                    <a href={buildResult.console_url} target="_blank" rel="noopener noreferrer" className="text-primary underline">
                      Open CodeBuild Console →
                    </a>
                  )}
                  <div className="text-muted-foreground mt-1">{buildResult.next_step}</div>
                </div>
              )
            }
            {buildResult.available_projects && (
              <div className="text-xs">
                <div className="font-medium">Available projects:</div>
                {buildResult.available_projects.map(p => (
                  <button key={p} onClick={() => setBuildProject(p)} className="block text-primary underline">{p}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </Step>

      {/* ── STEP 3: Deploy image ── */}
      <Step number="3" title="Deploy Image to ECS" status={deployResult ? (deployResult.error ? 'fail' : 'pass') : undefined}>
        <p className="text-muted-foreground">
          Once the build completes, paste the specific ECR image URI (with commit tag) here to register a new task definition and force ECS to run it. Leave blank to force-redeploy :latest.
        </p>
        <div className="flex items-center gap-2">
          <Input
            className="text-sm"
            placeholder="368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:sha-abc123  (or leave blank for :latest)"
            value={deployImageUri}
            onChange={e => setDeployImageUri(e.target.value)}
          />
        </div>
        <Button size="sm" disabled={deployLoading} onClick={deployImage}>
          {deployLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
          {deployImageUri.trim() ? 'Deploy Specific Image' : 'Force Redeploy :latest'}
        </Button>
        {deployResult && (
          <div className="text-xs space-y-1 mt-1">
            {deployResult.error
              ? <div className="text-destructive">{deployResult.error}</div>
              : (
                <>
                  <div className="text-emerald-700 font-medium">
                    {deployResult.status === 'deployment_started' ? '✓ Deployment started' : '✓ Redeployment started'}
                  </div>
                  {deployResult.image_deployed && <div className="font-mono text-muted-foreground">{deployResult.image_deployed}</div>}
                  {deployResult.task_def_revision && <div className="text-muted-foreground">Task def revision: {deployResult.task_def_revision}</div>}
                  <div className="text-muted-foreground">{deployResult.estimated_time}</div>
                  {deployResult.console_url && (
                    <a href={deployResult.console_url} target="_blank" rel="noopener noreferrer" className="text-primary underline block">
                      Open ECS Deployments Console →
                    </a>
                  )}
                </>
              )
            }
            <JsonViewer data={deployResult} title="Full response" />
          </div>
        )}
      </Step>

      {/* ── STEP 4: Verify live contract ── */}
      <Step number="4" title="Verify Live API Contract" status={verifyResult ? (verifyResult.mismatch?.has_real_contract ? 'pass' : 'fail') : undefined}>
        <p className="text-muted-foreground">
          Re-probe the live API after ~3 minutes to confirm the real aurora_vnext backend is now serving the correct contract.
        </p>
        <Button size="sm" variant="outline" disabled={verifyLoading} onClick={verifyContract}>
          {verifyLoading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
          Verify Live Contract
        </Button>

        {verifyResult && (
          <div className="space-y-2 mt-1">
            <div className={`rounded px-3 py-2 text-sm font-medium border ${verifyIsReal ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'bg-red-50 border-red-300 text-red-800'}`}>
              {verifyResult.mismatch?.verdict}
            </div>

            {verifyIsReal && (
              <div className="text-xs space-y-1 text-muted-foreground">
                <div className="font-semibold text-foreground">Contract fields verified:</div>
                <div className="flex gap-2 flex-wrap">
                  <StatusBadge ok={verifyResult.live_api?.scan_polygon?.has_scan_id} trueLabel="scan_id ✓" falseLabel="scan_id ✗" />
                  <StatusBadge ok={verifyResult.live_api?.scan_polygon?.has_scan_job_id} trueLabel="scan_job_id ✓" falseLabel="scan_job_id ✗" />
                  <StatusBadge ok={verifyResult.live_api?.scan_polygon?.has_submitted_at} trueLabel="submitted_at ✓" falseLabel="submitted_at ✗" />
                </div>
                <div className="mt-1">Next: submit a real scan from Map Scan Builder and confirm it appears in history.</div>
              </div>
            )}

            <JsonViewer data={verifyResult?.live_api} title="Live API probe results" />
          </div>
        )}
      </Step>
    </div>
  );
}