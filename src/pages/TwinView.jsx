/**
 * TwinView — digital twin query interface
 * Phase P §P.5
 *
 * CONSTITUTIONAL RULES:
 *  - Voxel data from GET /twin/{id}/query — verbatim stored values.
 *  - commodity_probs, uncertainty, temporal_score, physics_residual rendered verbatim.
 *  - kernel_weight displayed as stored — no re-derivation.
 *  - No re-scoring, no re-tiering, no depth kernel recomputation in UI.
 *  - Null fields render MissingValue.
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { twin } from "../lib/auroraApi";
import MissingValue, { ValueOrMissing } from "../components/MissingValue";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Loader2, ArrowLeft } from "lucide-react";

export default function TwinView() {
  const { scanId }              = useParams();
  const [meta, setMeta]         = useState(null);
  const [voxels, setVoxels]     = useState(null);
  const [depthMin, setDepthMin] = useState("");
  const [depthMax, setDepthMax] = useState("");
  const [loading, setLoading]   = useState(true);
  const [queryLoading, setQueryLoading] = useState(false);
  const [error, setError]       = useState(null);

  useEffect(() => {
    twin.metadata(scanId)
      .then(setMeta)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [scanId]);

  async function handleQuery(e) {
    e.preventDefault();
    setQueryLoading(true);
    try {
      const body = { scan_id: scanId, limit: 200 };
      if (depthMin) body.depth_min_m = parseFloat(depthMin);
      if (depthMax) body.depth_max_m = parseFloat(depthMax);
      const res = await twin.query(scanId, body);
      setVoxels(res);
    } catch (e) { setError(e.message); }
    finally { setQueryLoading(false); }
  }

  if (loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;
  if (error)   return <div className="p-6 text-destructive text-sm">{error}</div>;

  const fmtPct = v => v !== null && v !== undefined ? `${(v * 100).toFixed(1)}%` : null;
  const fmtN   = v => v !== null && v !== undefined ? v.toFixed(3) : null;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center gap-3">
        <Link to={`/history/${scanId}`} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Digital Twin — {meta?.commodity}</h1>
          <p className="font-mono text-xs text-muted-foreground">{scanId}</p>
        </div>
      </div>

      {meta && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Version",      meta.current_version],
            ["Total Voxels", meta.total_voxels],
            ["Depth Min (m)", meta.depth_range_m?.[0]],
            ["Depth Max (m)", meta.depth_range_m?.[1]],
          ].map(([label, val]) => (
            <Card key={label}>
              <CardContent className="py-3 px-4">
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-lg font-bold tabular-nums mt-0.5">
                  <ValueOrMissing value={val} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Voxel query */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Voxel Query</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleQuery} className="flex items-end gap-3 flex-wrap">
            <div className="space-y-1">
              <Label className="text-xs">Depth min (m)</Label>
              <Input className="w-28" placeholder="e.g. 100" value={depthMin} onChange={e => setDepthMin(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Depth max (m)</Label>
              <Input className="w-28" placeholder="e.g. 500" value={depthMax} onChange={e => setDepthMax(e.target.value)} />
            </div>
            <Button type="submit" disabled={queryLoading}>
              {queryLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Query
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Voxel results — all values verbatim from stored records */}
      {voxels && (
        <Card>
          <CardHeader className="pb-2 flex-row items-center justify-between">
            <CardTitle className="text-sm">Voxels</CardTitle>
            <span className="text-xs text-muted-foreground">
              {voxels.total_matching} matching · version {voxels.twin_version}
            </span>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/40">
                    {["Depth (m)", "Lat", "Lon", "Probability", "Density (kg/m³)", "Temporal", "Physics Res.", "Uncertainty", "Kernel W"].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {voxels.voxels.map(v => {
                    // commodity_probs: dict from API — find first entry value
                    const probVal = v.commodity_probs ? Object.values(v.commodity_probs)[0] : null;
                    return (
                      <tr key={v.voxel_id} className="border-b hover:bg-muted/20">
                        <td className="px-3 py-1.5 tabular-nums">{v.depth_m}</td>
                        <td className="px-3 py-1.5 tabular-nums">{v.lat_center?.toFixed(4) ?? <MissingValue inline />}</td>
                        <td className="px-3 py-1.5 tabular-nums">{v.lon_center?.toFixed(4) ?? <MissingValue inline />}</td>
                        {/* commodity_probs: verbatim from stored voxel — not recomputed */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtPct(probVal) ?? <MissingValue inline />}</td>
                        {/* expected_density: verbatim from stored voxel — not recomputed */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtN(v.expected_density) ?? <MissingValue inline />}</td>
                        {/* temporal_score: propagated verbatim from ScanCell — not recomputed */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtPct(v.temporal_score) ?? <MissingValue inline />}</td>
                        {/* physics_residual: propagated verbatim from ScanCell */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtN(v.physics_residual) ?? <MissingValue inline />}</td>
                        {/* uncertainty: propagated verbatim from ScanCell */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtPct(v.uncertainty) ?? <MissingValue inline />}</td>
                        {/* kernel_weight: stored at build time — not recomputed */}
                        <td className="px-3 py-1.5 tabular-nums">{fmtN(v.kernel_weight) ?? <MissingValue inline />}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}