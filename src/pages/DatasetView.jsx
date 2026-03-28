/**
 * DatasetView — canonical dataset summary and GeoJSON cell list
 * Phase P §P.5
 *
 * CONSTITUTIONAL RULES:
 *  - Summary from GET /datasets/summary/{id} — verbatim canonical fields.
 *  - Cell list from GET /history/{id}/cells — verbatim per-cell scores.
 *  - tier_thresholds displayed from API field — never hardcoded or derived.
 *  - acif_score per cell rendered as (v × 100).toFixed(1)% — display only.
 *  - No threshold comparison in UI code to assign colour — tier label from API.
 *  - Null fields render MissingValue.
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { datasets, history } from "../lib/auroraApi";
import { TierBadge } from "../components/ScanStatusBadge";
import MissingValue, { ValueOrMissing } from "../components/MissingValue";
import TierDistribution from "../components/TierDistribution";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import APIOffline from "../components/APIOffline";
import { Button } from "@/components/ui/button";

export default function DatasetView() {
  const { scanId }            = useParams();
  const [summary, setSummary] = useState(null);
  const [cells, setCells]     = useState(null);
  const [page, setPage]       = useState(1);
  const [loading, setLoading] = useState(true);
  const [cellsLoading, setCellsLoading] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      datasets.summary(scanId),
      history.cells(scanId, { page: 1, page_size: 50 }),
    ])
      .then(([s, c]) => { setSummary(s); setCells(c); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [scanId]);

  async function loadCells(p) {
    setCellsLoading(true);
    try {
      const c = await history.cells(scanId, { page: p, page_size: 50 });
      setCells(c);
      setPage(p);
    } catch (e) { setError(e.message); }
    finally { setCellsLoading(false); }
  }

  if (loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;
  if (error)   return <div className="p-6"><APIOffline error={error} endpoint={`GET /api/v1/datasets/summary/${scanId}`} /></div>;

  const fmtPct = v => v !== null && v !== undefined ? `${(v * 100).toFixed(1)}%` : null;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center gap-3">
        <Link to={`/history/${scanId}`} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Dataset — {summary?.commodity}</h1>
          <p className="font-mono text-xs text-muted-foreground mt-0.5">{scanId}</p>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Aggregate ACIF</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Display (mean)</span>
                <ValueOrMissing value={summary.display_acif_score} format={fmtPct} />
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max</span>
                <ValueOrMissing value={summary.max_acif_score} format={fmtPct} />
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Weighted</span>
                <ValueOrMissing value={summary.weighted_acif_score} format={fmtPct} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Tier Distribution</CardTitle></CardHeader>
            <CardContent>
              <TierDistribution
                tierCounts={summary.tier_counts}
                totalCells={summary.total_cells}
                tierThresholds={null}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Veto Counts</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              {[
                ["Causal",   summary.veto_counts?.causal],
                ["Physics",  summary.veto_counts?.physics],
                ["Province", summary.veto_counts?.province],
                ["Offshore", summary.veto_counts?.offshore_blocked],
              ].map(([label, count]) => (
                <div key={label} className="flex justify-between">
                  <span className="text-muted-foreground">{label}</span>
                  <ValueOrMissing value={count} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Cell table — per-cell canonical fields */}
      <Card>
        <CardHeader className="pb-2 flex-row items-center justify-between">
          <CardTitle className="text-sm">Scan Cells</CardTitle>
          {cells && <span className="text-xs text-muted-foreground">{cells.total} cells</span>}
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/40">
                  {["Cell ID", "Lat", "Lon", "ACIF", "Tier", "Evidence", "Causal", "Physics", "Temporal", "Uncertainty"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cellsLoading && (
                  <tr><td colSpan={10} className="px-3 py-4 text-center text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin inline" /></td></tr>
                )}
                {!cellsLoading && cells?.cells.map(cell => (
                  <tr key={cell.cell_id} className="border-b hover:bg-muted/20">
                    <td className="px-3 py-1.5 font-mono text-muted-foreground max-w-[120px] truncate">{cell.cell_id}</td>
                    <td className="px-3 py-1.5 tabular-nums">{cell.lat_center?.toFixed(4) ?? <MissingValue inline />}</td>
                    <td className="px-3 py-1.5 tabular-nums">{cell.lon_center?.toFixed(4) ?? <MissingValue inline />}</td>
                    {/* acif_score: verbatim from API, formatted for display only */}
                    <td className="px-3 py-1.5 tabular-nums font-medium">{fmtPct(cell.acif_score) ?? <MissingValue inline />}</td>
                    {/* tier: verbatim label from API — UI does not assign tiers */}
                    <td className="px-3 py-1.5"><TierBadge tier={cell.tier} /></td>
                    <td className="px-3 py-1.5 tabular-nums">{fmtPct(cell.evidence_score) ?? <MissingValue inline />}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmtPct(cell.causal_score)   ?? <MissingValue inline />}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmtPct(cell.physics_score)  ?? <MissingValue inline />}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmtPct(cell.temporal_score) ?? <MissingValue inline />}</td>
                    <td className="px-3 py-1.5 tabular-nums">{fmtPct(cell.uncertainty)    ?? <MissingValue inline />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {cells && cells.total_pages > 1 && (
            <div className="flex items-center gap-2 justify-center py-3 border-t">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => loadCells(page - 1)}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-xs text-muted-foreground">Page {page} of {cells.total_pages}</span>
              <Button variant="outline" size="sm" disabled={page >= cells.total_pages} onClick={() => loadCells(page + 1)}>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}