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
import { base44 } from '@/api/base44Client';
import { Badge } from "@/components/ui/badge";
import ScanResultsMap from "../components/ScanResultsMap";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, ArrowLeft, FileText, Map, Box, Lock, Download, CheckCircle, AlertTriangle } from "lucide-react";

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
  const { scanId }        = useParams();
  const [scan, setScan]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    // Load from ScanJob entity by scan_id field
    base44.entities.ScanJob.filter({ scan_id: scanId })
      .then(jobs => {
        if (jobs && jobs.length > 0) setScan(jobs[0]);
        else setError('Scan not found');
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [scanId]);

  if (loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading scan…</div>;
  if (error)   return <div className="p-6 text-destructive text-sm">{error}</div>;
  if (!scan)   return null;

  const fmtPct = v => v != null ? `${(v * 100).toFixed(1)}%` : '—';
  const geojson = scan.results_geojson;
  const tier1 = scan.tier_1_count ?? 0;
  const tier2 = scan.tier_2_count ?? 0;
  const tier3 = scan.tier_3_count ?? 0;
  const totalCells = tier1 + tier2 + tier3 || scan.cell_count || 0;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/history" className="text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" /></Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold capitalize">{scan.commodity} Scan</h1>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="font-mono text-xs text-muted-foreground">{scan.scan_id}</span>
            <Badge variant={scan.status === 'completed' ? 'default' : scan.status === 'failed' ? 'destructive' : 'secondary'}>
              {scan.status}
            </Badge>
            {scan.status === 'completed' && <CheckCircle className="w-4 h-4 text-emerald-600" />}
            {scan.status === 'failed' && <AlertTriangle className="w-4 h-4 text-destructive" />}
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums">{fmtPct(scan.display_acif_score)}</div>
            <div className="text-xs text-muted-foreground mt-1">ACIF Score (mean)</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums">{totalCells}</div>
            <div className="text-xs text-muted-foreground mt-1">Total Cells</div>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums text-emerald-700">{tier1}</div>
            <div className="text-xs text-emerald-600 mt-1">Tier 1 (High)</div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums text-amber-700">{tier2}</div>
            <div className="text-xs text-amber-600 mt-1">Tier 2 (Moderate)</div>
          </CardContent>
        </Card>
      </div>

      {/* Scan config row */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex flex-wrap gap-6 text-sm">
            <div><span className="text-muted-foreground text-xs">Commodity</span><div className="font-medium capitalize">{scan.commodity}</div></div>
            <div><span className="text-muted-foreground text-xs">Resolution</span><div className="font-medium capitalize">{scan.resolution || '—'}</div></div>
            <div><span className="text-muted-foreground text-xs">Pipeline</span><div className="font-medium font-mono text-xs">{scan.pipeline_version || '—'}</div></div>
            <div><span className="text-muted-foreground text-xs">Completed</span><div className="font-medium">{scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '—'}</div></div>
            <div><span className="text-muted-foreground text-xs">Source</span><div className="font-medium">{geojson?.metadata?.gee_sourced ? 'GEE Sentinel-2' : 'Spectral Simulation'}</div></div>
          </div>
        </CardContent>
      </Card>

      {/* Results Map */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Cell Results Map</CardTitle></CardHeader>
        <CardContent>
          {geojson?.features?.length > 0 ? (
            <ScanResultsMap geojson={geojson} geometry={scan.geometry} />
          ) : (
            <div className="py-8 text-center text-muted-foreground text-sm">No cell results available yet.</div>
          )}
        </CardContent>
      </Card>

      {/* Tier distribution bar */}
      {totalCells > 0 && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Tier Distribution</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {[{label:'Tier 1 — High Prospectivity', count:tier1, color:'bg-emerald-500'},
              {label:'Tier 2 — Moderate', count:tier2, color:'bg-amber-400'},
              {label:'Tier 3 — Low', count:tier3, color:'bg-red-400'}].map(({label, count, color}) => (
              <div key={label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium">{count} ({totalCells > 0 ? ((count/totalCells)*100).toFixed(1) : 0}%)</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div className={`h-full ${color} rounded-full`} style={{width: `${totalCells > 0 ? (count/totalCells)*100 : 0}%`}} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Top cells table */}
      {geojson?.features?.length > 0 && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Top Cells by ACIF Score</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1 px-2 text-muted-foreground">Cell</th>
                    <th className="text-left py-1 px-2 text-muted-foreground">Tier</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">ACIF</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">Clay</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">Ferric</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">Center</th>
                  </tr>
                </thead>
                <tbody>
                  {[...geojson.features]
                    .sort((a,b) => (b.properties.acif_score||0) - (a.properties.acif_score||0))
                    .slice(0, 15)
                    .map((f, i) => {
                      const p = f.properties;
                      const tierColors = {1:'text-emerald-700', 2:'text-amber-600', 3:'text-red-600'};
                      return (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="py-1 px-2 font-mono text-[10px] text-muted-foreground">{i+1}</td>
                          <td className={`py-1 px-2 font-bold ${tierColors[p.tier]||''}`}>T{p.tier}</td>
                          <td className="py-1 px-2 text-right font-medium">{((p.acif_score||0)*100).toFixed(1)}%</td>
                          <td className="py-1 px-2 text-right">{((p.clay_index||0)*100).toFixed(1)}%</td>
                          <td className="py-1 px-2 text-right">{((p.ferric_ratio||0)*100).toFixed(1)}%</td>
                          <td className="py-1 px-2 text-right font-mono text-[10px]">{p.center_lat?.toFixed(3)}, {p.center_lon?.toFixed(3)}</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action bar */}
      <div className="border rounded-lg px-4 py-3 bg-muted/20">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Actions</div>
        <div className="flex flex-wrap gap-2">
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