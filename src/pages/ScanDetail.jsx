/**
 * ScanDetail — full CanonicalScan record view
 * Phase P §P.4
 *
 * CONSTITUTIONAL RULES:
 *  - All fields from GET /history/{id} (frozen CanonicalScan).
 *  - tier_thresholds_used displayed verbatim — never recomputed.
 *  - No ACIF arithmetic. Percentage display: (value × 100).toFixed(1) only.
 *  - Veto counts and offshore stats rendered verbatim.
 *  - parent_scan_id shown if present (reprocess lineage).
 *  - Null fields render MissingValue — no fallback substitution.
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { history } from "../lib/auroraApi";
import { ScanStatusBadge, SystemStatusBadge, TierBadge } from "../components/ScanStatusBadge";
import MissingValue, { ValueOrMissing } from "../components/MissingValue";
import ScoreGrid from "../components/ScoreGrid";
import TierDistribution from "../components/TierDistribution";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, ArrowLeft, GitBranch, FileText, Map, Box, Lock, Download } from "lucide-react";
import APIOffline from "../components/APIOffline";

function Field({ label, children }) {
  return (
    <div className="space-y-0.5">
      <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function VetoRow({ label, count }) {
  return (
    <div className="flex justify-between text-sm py-1 border-b last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <ValueOrMissing value={count} label="Count unavailable" />
    </div>
  );
}

export default function ScanDetail() {
  const { scanId }          = useParams();
  const [scan, setScan]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  function load() {
    setLoading(true);
    history.get(scanId)
      .then(setScan)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [scanId]);

  if (loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;
  if (error)   return <div className="p-6"><APIOffline error={error} endpoint={`GET /api/v1/history/${scanId}`} /></div>;
  if (!scan)   return null;

  const fmtPct = v => v !== null && v !== undefined ? `${(v * 100).toFixed(1)}%` : null;

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to="/history" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">{scan.commodity}</h1>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="font-mono text-xs text-muted-foreground">{scan.scan_id}</span>
            <ScanStatusBadge status={scan.status} />
            {scan.system_status && <SystemStatusBadge status={scan.system_status} />}
          </div>
        </div>
      </div>

      {/* Reprocess lineage */}
      {scan.parent_scan_id && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground border rounded px-3 py-2 bg-muted/30">
          <GitBranch className="w-3.5 h-3.5" />
          Reprocessed from{" "}
          <Link to={`/history/${scan.parent_scan_id}`} className="underline font-mono">
            {scan.parent_scan_id}
          </Link>
          {scan.reprocess_reason && <span>— {scan.reprocess_reason}</span>}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* ACIF aggregate — verbatim from canonical record */}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">ACIF Score</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div>
              <div className="text-3xl font-bold tabular-nums">
                <ValueOrMissing value={scan.display_acif_score} format={fmtPct} label="ACIF unavailable" />
              </div>
              <div className="text-xs text-muted-foreground">Mean (display)</div>
            </div>
            <div className="text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max</span>
                <ValueOrMissing value={scan.max_acif_score} format={fmtPct} label="Max unavailable" />
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Weighted</span>
                <ValueOrMissing value={scan.weighted_acif_score} format={fmtPct} label="Weighted unavailable" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Scan metadata */}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Scan Config</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Field label="Tier">{scan.scan_tier}</Field>
            <Field label="Environment">{scan.environment}</Field>
            <Field label="Total Cells"><ValueOrMissing value={scan.total_cells} /></Field>
            <Field label="Completed">
              {scan.completed_at ? new Date(scan.completed_at).toLocaleString() : <MissingValue inline />}
            </Field>
          </CardContent>
        </Card>

        {/* Tier distribution — from canonical tier_counts */}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Tier Distribution</CardTitle></CardHeader>
          <CardContent>
            <TierDistribution
              tierCounts={scan.tier_counts}
              totalCells={scan.total_cells}
              tierThresholds={scan.tier_thresholds_used}
            />
          </CardContent>
        </Card>
      </div>

      {/* Component scores — verbatim from canonical record */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Component Score Means</CardTitle></CardHeader>
        <CardContent>
          <ScoreGrid scan={scan} />
        </CardContent>
      </Card>

      {/* Veto summary */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Hard Veto Counts</CardTitle></CardHeader>
        <CardContent>
          <VetoRow label="Causal veto"          count={scan.causal_veto_cell_count} />
          <VetoRow label="Physics veto"         count={scan.physics_veto_cell_count} />
          <VetoRow label="Province veto"        count={scan.province_veto_cell_count} />
          <VetoRow label="Offshore blocked"     count={scan.offshore_blocked_cell_count} />
        </CardContent>
      </Card>

      {/* Version registry — verbatim snapshot */}
      {scan.version_registry && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Version Registry (frozen at completion)</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
              {Object.entries(scan.version_registry).map(([k, v]) => (
                <div key={k} className="flex justify-between py-0.5 border-b last:border-0">
                  <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono">{v}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action bar — links to related pages */}
      <div className="border rounded-lg px-4 py-3 bg-muted/20">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Actions</div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/datasets/${scanId}`}>
            <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border hover:bg-muted transition-colors">
              <Download className="w-3.5 h-3.5" /> Dataset
            </button>
          </Link>
          <Link to={`/twin/${scanId}`}>
            <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border hover:bg-muted transition-colors">
              <Box className="w-3.5 h-3.5" /> Digital Twin
            </button>
          </Link>
          <Link to={`/reports/${scanId}`}>
            <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border hover:bg-muted transition-colors">
              <FileText className="w-3.5 h-3.5" /> Generate Report
            </button>
          </Link>
          <Link to={`/map-export/${scanId}`}>
            <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border hover:bg-muted transition-colors">
              <Map className="w-3.5 h-3.5" /> Map Export
            </button>
          </Link>
          <Link to={`/data-room`}>
            <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border hover:bg-muted transition-colors">
              <Lock className="w-3.5 h-3.5" /> Data Room
            </button>
          </Link>
        </div>
      </div>
    </div>
  );
}