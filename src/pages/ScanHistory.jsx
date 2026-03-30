/**
 * ScanHistory — Two strictly separated sections:
 *  1. Execution Jobs  (ScanJob entity — queued/running/failed local records)
 *  2. Completed Canonical Scans (Aurora /api/v1/history — completed frozen results only)
 *
 * ROUTING:
 *  - Canonical scan → /history/:scanId  (canonical detail page)
 *  - Execution job  → no canonical detail link; status shown inline with poll button
 *
 * CONSTITUTIONAL RULES:
 *  - Canonical section shows ONLY completed CanonicalScanSummary records from the remote API.
 *  - ScanJob records NEVER routed to canonical detail page.
 *  - display_acif_score shown as (value × 100)% — display only, not arithmetic.
 *  - When a ScanJob scan_id is found in canonical history, it transitions: job shown as "completed"
 *    with a link to the canonical detail page.
 */
import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { base44 } from '@/api/base44Client';
import { history as historyApi, scans as scansApi } from '../lib/auroraApi';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ArrowRight, RefreshCw, AlertTriangle, Clock, CheckCircle, XCircle } from "lucide-react";
import APIOffline from "@/components/APIOffline";

function StatusBadge({ status }) {
  if (status === 'completed') return <Badge variant="default">completed</Badge>;
  if (status === 'failed')    return <Badge variant="destructive">failed</Badge>;
  if (status === 'running')   return <Badge variant="secondary" className="text-blue-700 bg-blue-50 border-blue-200">running</Badge>;
  return <Badge variant="outline">queued</Badge>;
}

export default function ScanHistory() {
  const [canonicalScans, setCanonicalScans] = useState([]);
  const [jobs, setJobs]                     = useState([]);
  const [commodity, setCommodity]           = useState("");
  const [loading, setLoading]               = useState(true);
  const [canonicalError, setCanonicalError] = useState(null);
  // Track which job IDs are currently being polled
  const [pollingIds, setPollingIds]         = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setCanonicalError(null);
    try {
      const [remoteResult, localResult] = await Promise.allSettled([
        historyApi.list(),
        base44.entities.ScanJob.list('-created_date', 100),
      ]);

      const canonical = remoteResult.status === 'fulfilled'
        ? (remoteResult.value?.scans || [])
        : [];
      if (remoteResult.status === 'rejected') {
        setCanonicalError(remoteResult.reason?.message || 'Failed to load canonical scans');
      }
      setCanonicalScans(canonical);

      const localJobs = localResult.status === 'fulfilled' ? localResult.value : [];
      // Build a set of scan_ids that have canonical records — those jobs are "done"
      const canonicalIds = new Set(canonical.map(s => s.scan_id).filter(Boolean));
      const pendingJobs = localJobs.map(j => ({
        ...j,
        _canonical_complete: canonicalIds.has(j.scan_id),
      }));
      setJobs(pendingJobs);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Poll a single job's status from the backend and update the ScanJob entity
  async function pollJob(job) {
    if (!job.scan_id || job.scan_id.startsWith('local-')) return;
    setPollingIds(p => ({ ...p, [job.id]: true }));
    try {
      const res = await scansApi.status(job.scan_id);
      const newStatus = res?.status || job.status;
      if (newStatus !== job.status) {
        await base44.entities.ScanJob.update(job.id, { status: newStatus });
      }
      await load();
    } catch {
      // status endpoint may 404 — just reload local state
      await load();
    } finally {
      setPollingIds(p => { const n = { ...p }; delete n[job.id]; return n; });
    }
  }

  const filteredCanonical = commodity
    ? canonicalScans.filter(s => s.commodity?.toLowerCase().includes(commodity.toLowerCase()))
    : canonicalScans;

  const filteredJobs = commodity
    ? jobs.filter(j => j.commodity?.toLowerCase().includes(commodity.toLowerCase()))
    : jobs;

  // Jobs that have NOT yet transitioned to canonical — show in execution section
  const pendingJobs = filteredJobs.filter(j => !j._canonical_complete);

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Scan History</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Execution jobs and completed canonical scan records
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <Input
        placeholder="Filter by commodity…"
        value={commodity}
        onChange={e => setCommodity(e.target.value)}
        className="max-w-xs"
      />

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      )}

      {/* ── SECTION 1: Execution Jobs ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Execution Jobs
          </h2>
          <span className="text-xs text-muted-foreground">({pendingJobs.length})</span>
        </div>

        {!loading && pendingJobs.length === 0 && (
          <Card>
            <CardContent className="py-6 text-center text-muted-foreground text-sm">
              No pending execution jobs.
            </CardContent>
          </Card>
        )}

        {pendingJobs.map(job => (
          <Card key={job.id} className="border-l-4 border-l-amber-400">
            <CardContent className="py-3 px-4 flex items-center gap-4">
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium capitalize">{job.commodity}</span>
                  <StatusBadge status={job.status} />
                  {job.resolution && (
                    <span className="text-xs text-muted-foreground">{job.resolution}</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  {job.scan_id || job.id}
                  {job.scan_id?.startsWith('local-') && (
                    <span className="ml-2 text-amber-600">(no remote job id)</span>
                  )}
                </div>
                {job.status === 'failed' && job.error_message && (
                  <div className="flex items-start gap-1 text-xs text-destructive mt-1">
                    <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                    {job.error_message}
                  </div>
                )}
              </div>
              <div className="text-xs text-muted-foreground whitespace-nowrap">
                {job.created_date ? new Date(job.created_date).toLocaleDateString() : '—'}
              </div>
              {/* Poll status — only for jobs with a real backend scan_id */}
              {job.scan_id && !job.scan_id.startsWith('local-') && job.status !== 'failed' && (
                <Button
                  variant="outline" size="sm"
                  disabled={!!pollingIds[job.id]}
                  onClick={() => pollJob(job)}
                >
                  {pollingIds[job.id]
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <RefreshCw className="w-3 h-3" />}
                  <span className="ml-1 text-xs">Check</span>
                </Button>
              )}
              {/* No link to canonical detail — job is NOT a canonical scan */}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── SECTION 2: Completed Canonical Scans ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Completed Canonical Scans
          </h2>
          <span className="text-xs text-muted-foreground">({filteredCanonical.length})</span>
        </div>

        {canonicalError && (
          <APIOffline
            error={canonicalError}
            endpoint="GET /api/v1/history"
            onRetry={load}
          />
        )}

        {!loading && !canonicalError && filteredCanonical.length === 0 && (
          <Card>
            <CardContent className="py-6 text-center text-muted-foreground text-sm">
              No completed canonical scans yet. Submitted scans appear here once the Aurora pipeline completes.
            </CardContent>
          </Card>
        )}

        {filteredCanonical.map(scan => (
          <Card key={scan.scan_id} className="hover:border-primary/40 transition-colors border-l-4 border-l-emerald-500">
            <CardContent className="py-3 px-4 flex items-center gap-4">
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium capitalize">{scan.commodity}</span>
                  <Badge variant="default">completed</Badge>
                  {scan.gee_sourced === false && (
                    <Badge variant="outline" className="text-[10px]">simulated</Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground font-mono">{scan.scan_id}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium tabular-nums">
                  {scan.display_acif_score != null
                    ? `${(scan.display_acif_score * 100).toFixed(1)}%`
                    : '—'}
                </div>
                <div className="text-xs text-muted-foreground">ACIF</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium tabular-nums">{scan.tier_1_count ?? '—'}</div>
                <div className="text-xs text-muted-foreground">Tier 1</div>
              </div>
              <div className="text-xs text-muted-foreground whitespace-nowrap">
                {scan.completed_at ? new Date(scan.completed_at).toLocaleDateString() : '—'}
              </div>
              {/* ONLY canonical scans link to the canonical detail page */}
              <Link to={`/history/${scan.scan_id}`}>
                <Button variant="ghost" size="sm">
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}