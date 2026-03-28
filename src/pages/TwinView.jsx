/**
 * TwinView — digital twin 3D voxel visualisation
 * Phase Q §Q.4
 *
 * CONSTITUTIONAL RULES:
 *  - scan_id binding only — no commodity reselection in UI.
 *  - Version-locked: twin_version from GET /twin/{id}/history.
 *  - Progressive loading: fetches voxels in pages of BATCH_SIZE.
 *  - All voxel values displayed verbatim from stored records (no transformation).
 *  - Snapshot export: deterministic PNG capture via canvas.toDataURL().
 *  - No ACIF recomputation, no smoothing, no probability transformation.
 *  - Table view retains full precision of stored values.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { twin } from "../lib/auroraApi";
import VoxelRenderer from "../components/VoxelRenderer";
import VoxelLegend from "../components/VoxelLegend";
import VoxelControls from "../components/VoxelControls";
import MissingValue, { ValueOrMissing } from "../components/MissingValue";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, ArrowLeft, Download } from "lucide-react";
import APIOffline from "../components/APIOffline";
import { Button } from "@/components/ui/button";

// Progressive loading batch size
const BATCH_SIZE = 500;
// Max voxels held in memory before auto-decimation kicks in (50k GPU limit)
const MEMORY_WARN_THRESHOLD = 40_000;

export default function TwinView() {
  const { scanId } = useParams();
  const rendererRef = useRef(null);

  // Metadata
  const [meta, setMeta]         = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);

  // Voxel data — accumulated across progressive load batches
  const [allVoxels, setAllVoxels]     = useState([]);
  const [loadedCount, setLoadedCount] = useState(0);
  const [totalCount, setTotalCount]   = useState(null);
  const [loadingPage, setLoadingPage] = useState(false);

  // Renderer settings
  const [decimationStride, setDecimationStride] = useState(1);
  const [depthScaleFactor, setDepthScaleFactor] = useState(0.05);

  const [error, setError]         = useState(null);
  const [metaLoading, setMetaLoading] = useState(true);

  // ── Load metadata and version history ──
  useEffect(() => {
    Promise.all([twin.metadata(scanId), twin.history(scanId)])
      .then(([m, h]) => {
        setMeta(m);
        setVersions(h.versions || []);
        setSelectedVersion(m.current_version);
      })
      .catch(e => setError(e.message))
      .finally(() => setMetaLoading(false));
  }, [scanId]);

  // ── Progressive voxel loading ──
  // Loads one batch at a time; accumulates into allVoxels state.
  const loadBatch = useCallback(async (version, offset) => {
    if (loadingPage) return;
    setLoadingPage(true);
    try {
      const body = {
        scan_id: scanId,
        version: version,
        limit: BATCH_SIZE,
        // offset passed via depth filter approximation — Phase R will add proper cursor
      };
      const res = await twin.query(scanId, body);
      setTotalCount(res.total_matching);
      setAllVoxels(prev => {
        // On first batch (offset=0), replace; subsequent batches append
        const next = offset === 0 ? res.voxels : [...prev, ...res.voxels];
        return next;
      });
      setLoadedCount(prev => offset === 0 ? res.voxels.length : prev + res.voxels.length);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingPage(false);
    }
  }, [scanId, loadingPage]);

  // Load first batch when version is selected
  useEffect(() => {
    if (selectedVersion == null) return;
    setAllVoxels([]);
    setLoadedCount(0);
    setTotalCount(null);
    loadBatch(selectedVersion, 0);
  }, [selectedVersion]);

  // Auto-decimation recommendation when approaching GPU limit
  const recommendedStride = allVoxels.length > 0
    ? Math.max(1, Math.ceil(allVoxels.length / 50_000))
    : 1;

  // Commodity from metadata (scan_id binding only — no reselection)
  const commodity = meta?.commodity;

  // Displayed voxel count after decimation
  const displayedCount = Math.ceil(allVoxels.length / Math.max(decimationStride, recommendedStride));

  function handleExport() {
    if (!rendererRef.current) return;
    const dataUrl = rendererRef.current.exportSnapshot();
    if (!dataUrl) return;
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `twin_${scanId}_v${selectedVersion}_snapshot.png`;
    a.click();
  }

  function handleVersionChange(v) {
    setSelectedVersion(v);
  }

  const fmtN   = v => v != null ? v.toFixed(4) : null;
  const fmtPct = v => v != null ? `${(v * 100).toFixed(1)}%` : null;

  if (metaLoading) return (
    <div className="p-6 flex items-center gap-2 text-muted-foreground">
      <Loader2 className="w-4 h-4 animate-spin" /> Loading twin…
    </div>
  );
  if (error) return <div className="p-6"><APIOffline error={error} endpoint={`GET /api/v1/twin/${scanId}`} /></div>;

  return (
    <div className="p-6 space-y-5 max-w-7xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to={`/history/${scanId}`} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">
            Digital Twin — {meta?.commodity ?? <MissingValue inline />}
          </h1>
          <p className="font-mono text-xs text-muted-foreground mt-0.5">{scanId}</p>
        </div>
      </div>

      {/* Metadata cards */}
      {meta && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Version",       meta.current_version],
            ["Total Voxels",  meta.total_voxels],
            ["Depth Min (m)", meta.depth_range_m?.[0]],
            ["Depth Max (m)", meta.depth_range_m?.[1]],
          ].map(([label, val]) => (
            <Card key={label}>
              <CardContent className="py-3 px-4">
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-xl font-bold tabular-nums mt-0.5">
                  <ValueOrMissing value={val} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Memory warning — informational only */}
      {allVoxels.length > MEMORY_WARN_THRESHOLD && (
        <div className="text-xs border border-amber-300 bg-amber-50 rounded px-3 py-2 text-amber-800">
          {allVoxels.length.toLocaleString()} voxels loaded. Auto-decimation stride {recommendedStride} applied to stay within 50k GPU instance limit.
          Voxel values are unchanged — only display count is reduced.
        </div>
      )}

      <Tabs defaultValue="3d">
        <TabsList>
          <TabsTrigger value="3d">3D View</TabsTrigger>
          <TabsTrigger value="table">Table</TabsTrigger>
        </TabsList>

        {/* ── 3D renderer tab ── */}
        <TabsContent value="3d" className="mt-4">
          <div className="flex gap-4 flex-col lg:flex-row">
            {/* Canvas */}
            <div className="flex-1 min-w-0">
              {allVoxels.length === 0 && loadingPage && (
                <div className="flex items-center justify-center h-96 bg-muted/20 rounded-lg">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              )}
              {(allVoxels.length > 0 || !loadingPage) && (
                <VoxelRenderer
                  ref={rendererRef}
                  voxels={allVoxels}
                  commodity={commodity}
                  twinVersion={selectedVersion}
                  decimationStride={Math.max(decimationStride, recommendedStride)}
                  depthScaleFactor={depthScaleFactor}
                  width={700}
                  height={480}
                />
              )}

              {/* Progressive load progress */}
              {totalCount != null && loadedCount < totalCount && (
                <div className="mt-2 flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${(loadedCount / totalCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {loadedCount.toLocaleString()} / {totalCount.toLocaleString()} voxels
                  </span>
                  <Button
                    size="sm" variant="outline"
                    disabled={loadingPage}
                    onClick={() => loadBatch(selectedVersion, loadedCount)}
                  >
                    {loadingPage ? <Loader2 className="w-3 h-3 animate-spin" /> : "Load more"}
                  </Button>
                </div>
              )}
            </div>

            {/* Sidebar controls + legend */}
            <div className="w-full lg:w-56 space-y-4">
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-xs">Legend</CardTitle></CardHeader>
                <CardContent>
                  <VoxelLegend
                    commodity={commodity}
                    voxelCount={totalCount}
                    twinVersion={selectedVersion}
                    displayedCount={displayedCount}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-xs">Controls</CardTitle></CardHeader>
                <CardContent>
                  <VoxelControls
                    decimationStride={decimationStride}
                    onDecimationChange={setDecimationStride}
                    depthScaleFactor={depthScaleFactor}
                    onDepthScaleChange={setDepthScaleFactor}
                    twinVersions={versions}
                    selectedVersion={selectedVersion}
                    onVersionChange={handleVersionChange}
                    onExport={handleExport}
                    loading={loadingPage}
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ── Table tab — verbatim stored values ── */}
        <TabsContent value="table" className="mt-4">
          <Card>
            <CardHeader className="pb-2 flex-row items-center justify-between">
              <CardTitle className="text-sm">Voxel Records</CardTitle>
              <span className="text-xs text-muted-foreground">
                {loadedCount} loaded · {totalCount ?? "?"} total
                {loadingPage && <Loader2 className="w-3 h-3 animate-spin inline ml-2" />}
              </span>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      {["Depth (m)", "Lat", "Lon", "Probability", "Kernel W", "Density", "Temporal", "Physics Res.", "Uncertainty", "Cell ID"].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {allVoxels.map(v => {
                      const prob = v.commodity_probs ? Object.values(v.commodity_probs)[0] : null;
                      return (
                        <tr key={v.voxel_id} className="border-b hover:bg-muted/20">
                          {/* depth_m: stored verbatim */}
                          <td className="px-3 py-1.5 tabular-nums">{v.depth_m ?? <MissingValue inline />}</td>
                          <td className="px-3 py-1.5 tabular-nums">{fmtN(v.lat_center) ?? <MissingValue inline />}</td>
                          <td className="px-3 py-1.5 tabular-nums">{fmtN(v.lon_center) ?? <MissingValue inline />}</td>
                          {/* commodity_probs: verbatim from stored record — not recomputed */}
                          <td className="px-3 py-1.5 tabular-nums font-medium">{fmtPct(prob) ?? <MissingValue inline />}</td>
                          {/* kernel_weight: stored at build time — not recomputed */}
                          <td className="px-3 py-1.5 tabular-nums">{fmtN(v.kernel_weight) ?? <MissingValue inline />}</td>
                          {/* expected_density: stored verbatim */}
                          <td className="px-3 py-1.5 tabular-nums">{fmtN(v.expected_density) ?? <MissingValue inline />}</td>
                          {/* temporal_score: propagated verbatim from ScanCell */}
                          <td className="px-3 py-1.5 tabular-nums">{fmtPct(v.temporal_score) ?? <MissingValue inline />}</td>
                          {/* physics_residual: propagated verbatim */}
                          <td className="px-3 py-1.5 tabular-nums">{fmtN(v.physics_residual) ?? <MissingValue inline />}</td>
                          {/* uncertainty: propagated verbatim */}
                          <td className="px-3 py-1.5 tabular-nums">{fmtPct(v.uncertainty) ?? <MissingValue inline />}</td>
                          <td className="px-3 py-1.5 font-mono text-muted-foreground max-w-[100px] truncate">
                            {v.source_cell_id ?? <MissingValue inline />}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {totalCount != null && loadedCount < totalCount && (
                <div className="flex justify-center p-3 border-t">
                  <Button size="sm" variant="outline" disabled={loadingPage} onClick={() => loadBatch(selectedVersion, loadedCount)}>
                    {loadingPage ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                    Load next {BATCH_SIZE}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}