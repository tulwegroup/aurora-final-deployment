import { useEffect, useState } from "react";
import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { base44 } from '@/api/base44Client';
import { history as historyApi } from "../lib/auroraApi";
import { Badge } from "@/components/ui/badge";
import ScanResultsMap from "../components/ScanResultsMap";
import ScanProgressVisualization from "../components/ScanProgressVisualization";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, ArrowLeft, FileText, Map, Lock, CheckCircle, AlertTriangle, RefreshCw } from "lucide-react";

export default function ScanDetail() {
  const { scanId } = useParams();
  const [scan, setScan] = useState(null);
  const [cells, setCells] = useState([]);
  const [datasets, setDatasets] = useState(null);
  const [twinMetadata, setTwinMetadata] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scanSource, setScanSource] = useState(null);

  useEffect(() => {
    const fetchScan = async () => {
      try {
        // CANONICAL ONLY — reject execution jobs
        const canonicalScan = await historyApi.get(scanId);
        setScan(canonicalScan);
        setScanSource("canonical");
        setError(null);

        // Fetch cell-level details and datasets
        const [cellsRes, datasetsRes, twinRes] = await Promise.allSettled([
          historyApi.cells(scanId),
          base44.functions
            .invoke("auroraProxy", {
              method: "GET",
              path: `/api/v1/datasets/summary/${scanId}`,
            })
            .then((r) => r.data?.data),
          base44.functions
            .invoke("auroraProxy", {
              method: "GET",
              path: `/api/v1/twin/${scanId}`,
            })
            .then((r) => r.data?.data),
        ]);

        if (cellsRes.status === "fulfilled") {
          setCells(cellsRes.value?.features || []);
        }
        if (datasetsRes.status === "fulfilled") {
          setDatasets(datasetsRes.value);
        }
        if (twinRes.status === "fulfilled") {
          setTwinMetadata(twinRes.value);
        }
      } catch (e) {
        // No fallback to execution jobs — strict separation
        setError(`${e.message} (Must be a completed canonical scan)`);
      } finally {
        setLoading(false);
      }
    };

    fetchScan();
  }, [scanId]);

  if (!scan && loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading scan…</div>;
  if (error) return <div className="p-6 text-destructive text-sm">{error}</div>;
  if (!scan) return null;

  const geojson = scan.results_geojson;
  const tier1 = scan.tier_1_count ?? 0;
  const tier2 = scan.tier_2_count ?? 0;
  const tier3 = scan.tier_3_count ?? 0;
  const totalCells = tier1 + tier2 + tier3 || scan.cell_count || 0;
  const isRunning = scan.status === 'running';
  const isInsufficientData = scan.status === 'completed_insufficient_data';

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/history" className="text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" /></Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold capitalize">{scan.commodity} Scan</h1>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="font-mono text-xs text-muted-foreground">{scan.scan_id}</span>
            <Badge variant={scan.status === 'completed' ? 'default' : scan.status === 'failed' ? 'destructive' : 'secondary'}>
              {isRunning ? (
                <span className="flex items-center gap-1"><RefreshCw className="w-3 h-3 animate-spin" /> Running</span>
              ) : scan.status === 'completed' ? 'Completed' : scan.status === 'completed_insufficient_data' ? 'No Data' : 'Failed'}
            </Badge>
            {scan.status === 'completed' && <CheckCircle className="w-4 h-4 text-emerald-600" />}
            {scan.status === 'failed' && <AlertTriangle className="w-4 h-4 text-destructive" />}
            {scanSource === 'canonical' && <Badge variant="outline" className="text-[10px]">canonical</Badge>}
          </div>
        </div>
      </div>

      {/* Live scanning progress visualization */}
      {isRunning && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-3">
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Live Scan Progress</CardTitle></CardHeader>
              <CardContent>
                <ScanProgressVisualization scan={scan} />
              </CardContent>
            </Card>
          </div>
          <div>
            <Card className="bg-blue-50 border-blue-200 h-full">
              <CardContent className="pt-4 space-y-2 text-sm">
                <div>
                  <div className="text-xs text-blue-600 font-semibold uppercase">Status</div>
                  <div className="text-blue-900 font-medium">Processing…</div>
                </div>
                <div>
                  <div className="text-xs text-blue-600 font-semibold uppercase">ETA</div>
                  <div className="text-blue-900 font-medium">Computing…</div>
                </div>
                <div className="text-xs text-blue-700 mt-4 p-2 bg-white rounded">
                  <p>Sampling {scan.cell_count || '?'} cells from Earth Engine's Sentinel-2, Sentinel-1, Landsat 8, and SRTM archives.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums">{scan.display_acif_score != null ? `${(scan.display_acif_score * 100).toFixed(1)}%` : '—'}</div>
            <div className="text-xs text-muted-foreground mt-1">ACIF Score (mean)</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold tabular-nums">{scan.cell_count || 0}</div>
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
            <div><span className="text-muted-foreground text-xs">Completed</span><div className="font-medium">{scan.completed_at ? new Date(scan.completed_at).toLocaleString() : (isRunning ? 'In progress…' : '—')}</div></div>
            <div><span className="text-muted-foreground text-xs">Geographic Bounds</span><div className="font-mono text-xs">{scan.min_lat?.toFixed(3)}, {scan.min_lon?.toFixed(3)} → {scan.max_lat?.toFixed(3)}, {scan.max_lon?.toFixed(3)}</div></div>
          </div>
        </CardContent>
      </Card>

      {/* SECTION 2: Geological Gates */}
      {scan.geological_gates && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Geological Gates</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(scan.geological_gates).map(([gateName, gateResult]) => {
              const isPass = gateResult.status === "PASS" || gateResult.pass_rate > 0.5;
              return (
                <div key={gateName} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium capitalize text-sm">{gateName.replace(/_/g, " ")}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {gateResult.confidence ? `Confidence: ${(gateResult.confidence * 100).toFixed(1)}%` : `Pass rate: ${(gateResult.pass_rate * 100).toFixed(1)}%`}
                    </div>
                  </div>
                  <Badge variant={isPass ? "default" : "outline"}>
                    {isPass ? "PASS" : "WEAK"}
                  </Badge>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* SECTION 3: ACIF Modality Averages */}
      {scan.modality_contributions && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">ACIF Modality Averages</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Object.entries(scan.modality_contributions).map(([modality, value]) => (
                <div key={modality} className="border rounded p-3">
                  <div className="text-xs text-muted-foreground uppercase tracking-wide">{modality.replace(/_/g, " ")}</div>
                  <div className="text-xl font-bold mt-1">{(value * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* SECTION 4: Digital Twin Metadata */}
      {twinMetadata && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Digital Twin — Subsurface Profile</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">Voxel Dimensions</span><span className="font-mono">{twinMetadata.voxel_size_m}m</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Total Voxels</span><span className="font-mono">{twinMetadata.voxel_count || "—"}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Max Depth</span><span className="font-mono">{twinMetadata.max_depth_m || "—"}m</span></div>
            {twinMetadata.download_url && (
              <a href={twinMetadata.download_url} target="_blank" rel="noopener noreferrer" className="text-primary underline text-xs mt-2 block">
                Download Twin Data →
              </a>
            )}
          </CardContent>
        </Card>
      )}

      {/* SECTION 5: GIS/Raster Spec */}
      {datasets && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">GIS / Raster Specification</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">CRS</span><span className="font-mono">{datasets.crs || "EPSG:4326"}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Pixel Size</span><span className="font-mono">{datasets.pixel_size_m || "—"}m</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Available Bands</span><span className="font-mono text-xs">{(datasets.bands || []).join(", ") || "—"}</span></div>
            {datasets.export_formats && (
              <div className="mt-3 flex flex-wrap gap-2">
                {datasets.export_formats.map((fmt) => (
                  <a key={fmt} href={`/api/v1/datasets/export/${scanId}?format=${fmt}`} target="_blank" rel="noopener noreferrer" className="text-xs text-primary underline">
                    {fmt.toUpperCase()}
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Insufficient Data Failure Mode */}
      {isInsufficientData && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="pt-4 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-amber-900">Insufficient Data — Scan Could Not Be Scored</div>
                <p className="text-xs text-amber-800 mt-1">The scan completed but lacked sufficient sensor data to compute prospectivity scores.</p>
              </div>
            </div>
            
            {geojson?.metadata && (
              <div className="bg-white rounded p-3 space-y-2 text-xs border border-amber-200">
                <div className="font-medium text-foreground">Data Quality Summary</div>
                <div className="grid grid-cols-2 gap-2">
                  <div>Cells Sampled: <span className="font-mono">{geojson.metadata.sampled_cells}</span></div>
                  <div>Cells Scored: <span className="font-mono">{geojson.metadata.scored_cells}</span></div>
                  <div>S2 Coverage: <span className="font-mono">{geojson.metadata.sensor_coverage?.s2_percent || 0}%</span></div>
                  <div>S1 Coverage: <span className="font-mono">{geojson.metadata.sensor_coverage?.s1_percent || 0}%</span></div>
                </div>
              </div>
            )}
            
            <div className="bg-slate-50 rounded p-3 text-xs space-y-2 border">
              <div className="font-medium text-slate-900">Possible Causes</div>
              <ul className="list-disc list-inside text-slate-700 space-y-0.5">
                <li>Satellite imagery unavailable for AOI during query period</li>
                <li>GEE service account authentication issue</li>
                <li>Data filtering returned empty collection</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Results Map (only if scored) */}
      {!isInsufficientData && !isRunning && (
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
      )}

      {/* Tier distribution bar */}
      {!isInsufficientData && !isRunning && totalCells > 0 && (
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
      {!isInsufficientData && !isRunning && geojson?.features?.length > 0 && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Top Cells by ACIF Score</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1 px-2 text-muted-foreground">Rank</th>
                    <th className="text-left py-1 px-2 text-muted-foreground">Tier</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">ACIF</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">Lat</th>
                    <th className="text-right py-1 px-2 text-muted-foreground">Lon</th>
                  </tr>
                </thead>
                <tbody>
                  {[...geojson.features]
                    .filter(f => f.properties.tier !== 'DATA_MISSING')
                    .sort((a,b) => (b.properties.acif_score||0) - (a.properties.acif_score||0))
                    .slice(0, 15)
                    .map((f, i) => {
                      const p = f.properties;
                      const tierColors = {TIER_1:'text-emerald-700', TIER_2:'text-amber-600', TIER_3:'text-red-600'};
                      return (
                        <tr key={i} className="border-b hover:bg-muted/30">
                          <td className="py-1 px-2 font-mono text-[10px] text-muted-foreground">{i+1}</td>
                          <td className={`py-1 px-2 font-bold ${tierColors[p.tier]||''}`}>{p.tier}</td>
                          <td className="py-1 px-2 text-right font-medium">{((p.acif_score||0)*100).toFixed(1)}%</td>
                          <td className="py-1 px-2 text-right font-mono text-[10px]">{f.geometry.coordinates[1]?.toFixed(3)}</td>
                          <td className="py-1 px-2 text-right font-mono text-[10px]">{f.geometry.coordinates[0]?.toFixed(3)}</td>
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
          {scan.status === 'completed' && (
            <>
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
            </>
          )}
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