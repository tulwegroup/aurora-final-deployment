/**
 * IntelligenceDossier — Enterprise Aurora ACIF Subsurface Intelligence
 * 
 * High-stakes dossier rendering with spatial analysis, resource estimation, ranked targets
 */
import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Loader2, TrendingUp, AlertTriangle, MapPin, Zap, DollarSign,
  BarChart3, Eye, Lock, Download, RefreshCw
} from "lucide-react";
import APIOffline from "../components/APIOffline";

const INVESTMENT_GRADE_COLORS = {
  "Investment Grade": "bg-emerald-100 text-emerald-800",
  "Prospective": "bg-blue-100 text-blue-800",
  "Exploration Stage": "bg-amber-100 text-amber-800",
};

function SpatialHeatmapPlaceholder({ clusters }) {
  if (!clusters || clusters.length === 0) {
    return <div className="text-center py-10 text-muted-foreground">No spatial clusters detected</div>;
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clusters.map(c => (
          <div key={c.id} className="border rounded p-4 space-y-2">
            <div className="font-medium text-sm">{c.id}</div>
            <div className="text-xs text-muted-foreground space-y-1">
              <div>Centroid: {parseFloat(c.centroid.lat).toFixed(4)}°, {parseFloat(c.centroid.lon).toFixed(4)}°</div>
              <div>Cells: {c.cell_count} | Avg ACIF: {c.avg_acif}</div>
              <div>Extent: {c.spatial_extent_km}km</div>
            </div>
            <div className="w-full bg-muted rounded overflow-hidden h-2">
              <div
                className="bg-red-500 h-full"
                style={{ width: `${Math.min(parseFloat(c.avg_acif) * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DigitalTwinVisualization({ twin }) {
  if (!twin) return <div className="text-muted-foreground text-sm">Twin data unavailable</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Depth Probability Decay</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {Object.entries(twin.depth_probability_profile || {}).map(([depth, prob]) => (
              <div key={depth} className="flex items-center gap-2">
                <span className="w-24 text-muted-foreground">{depth}</span>
                <div className="flex-1 bg-muted rounded overflow-hidden h-3">
                  <div
                    className="bg-blue-500 h-full transition-all"
                    style={{ width: `${prob * 100}%` }}
                  />
                </div>
                <span className="w-10 text-right">{(prob * 100).toFixed(0)}%</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Drilling Window</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-1">
            <div>
              <span className="text-muted-foreground">Optimal:</span>{" "}
              <span className="font-mono font-bold">
                {twin.optimal_drilling_window_m?.min || "—"}-
                {twin.optimal_drilling_window_m?.optimal || "—"}m
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Confidence:</span>{" "}
              <span className="font-bold">{(twin.window_confidence_score * 100).toFixed(0)}%</span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">{twin.cross_section_interpretation}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ResourceEstimationChart({ tonnage, epvi }) {
  if (!tonnage || !epvi) return <div className="text-muted-foreground text-sm">Resource data unavailable</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Tonnage (Monte Carlo)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span>P10 (Upside):</span>
              <span className="font-mono font-bold text-emerald-600">{(tonnage.p10_tonnes / 1e6).toFixed(1)}M t</span>
            </div>
            <div className="flex justify-between">
              <span>P50 (Best Est):</span>
              <span className="font-mono font-bold">{(tonnage.p50_tonnes / 1e6).toFixed(1)}M t</span>
            </div>
            <div className="flex justify-between">
              <span>P90 (Downside):</span>
              <span className="font-mono font-bold text-red-600">{(tonnage.p90_tonnes / 1e6).toFixed(1)}M t</span>
            </div>
            <div className="text-[10px] text-muted-foreground mt-2">
              Confidence: {tonnage.confidence}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Economic Value (EPVI)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs">
            <div>
              <span className="text-muted-foreground">Risk-adjusted:</span>
              <div className="font-mono font-bold text-lg">${(epvi.epvi_usd / 1e9).toFixed(2)}B</div>
            </div>
            <div className="space-y-0.5 mt-2 text-[10px]">
              <div>Upside (ACIF 0.85): ${(epvi.upside_if_acif_85 / 1e9).toFixed(2)}B</div>
              <div>Downside (ACIF 0.55): ${(epvi.downside_if_acif_55 / 1e9).toFixed(2)}B</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Risk Profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Uncertainty:</span>
              <span className="font-bold">{epvi.risk_discount_factor}</span>
            </div>
            <div className="text-[10px] text-muted-foreground">
              Reflects ACIF confidence decay and geological maturity
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RankedTargetsTable({ targets }) {
  if (!targets || targets.length === 0) {
    return <div className="text-muted-foreground text-sm">No targets available</div>;
  }

  return (
    <div className="overflow-x-auto border rounded">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-muted/40">
            <th className="px-3 py-2 text-left font-medium">#</th>
            <th className="px-3 py-2 text-left font-medium">Coordinates</th>
            <th className="px-3 py-2 text-left font-medium">ACIF</th>
            <th className="px-3 py-2 text-left font-medium">Signal</th>
            <th className="px-3 py-2 text-left font-medium">Depth Window</th>
            <th className="px-3 py-2 text-left font-medium">Confidence</th>
            <th className="px-3 py-2 text-left font-medium">Priority</th>
          </tr>
        </thead>
        <tbody>
          {targets.map(t => (
            <tr key={t.target_id} className="border-b hover:bg-muted/20">
              <td className="px-3 py-2 font-bold">{t.rank}</td>
              <td className="px-3 py-2 font-mono text-[10px]">
                {String(t.centroid_lat).slice(0, 8)}, {String(t.centroid_lon).slice(0, 8)}
              </td>
              <td className="px-3 py-2 font-bold">{t.acif}</td>
              <td className="px-3 py-2 text-muted-foreground">{t.dominant_signal}</td>
              <td className="px-3 py-2 font-mono">{t.depth_window_m}</td>
              <td className="px-3 py-2">
                <span className="text-green-600 font-bold">{t.confidence_pct}%</span>
              </td>
              <td className="px-3 py-2">
                <Badge
                  variant={t.drilling_priority === "immediate" ? "default" : "outline"}
                  className="text-[10px]"
                >
                  {t.drilling_priority}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function IntelligenceDossier() {
  const { scanId } = useParams();
  const [commodity, setCommodity] = useState("gold");
  const [dossier, setDossier] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generateDossier = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDossier(null);
    try {
      const payload = {
        scan_id: scanId || "demo-scan",
        commodity: commodity,
        acif_score: 0.7412,
        tier_counts: { TIER_1: 12, TIER_2: 47, TIER_3: 88, BELOW: 153 },
        system_status: "PASS_CONFIRMED",
        cells_data: [],
      };
      const res = await base44.functions.invoke("generateGeologicalReport", payload);
      setDossier(res.data);
    } catch (e) {
      setError(e.message || "Failed to generate dossier");
    } finally {
      setLoading(false);
    }
  }, [scanId, commodity]);

  return (
    <div className="p-6 max-w-7xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Eye className="w-7 h-7" /> Aurora ACIF Intelligence Dossier
        </h1>
        <p className="text-sm text-muted-foreground">
          Enterprise subsurface intelligence: spatial analysis, resource estimation, ranked targets
        </p>
      </div>

      <Card>
        <CardContent className="py-4 flex items-end gap-4 flex-wrap">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground uppercase">Commodity</label>
            <select
              className="text-sm border rounded px-2 py-1.5 bg-background"
              value={commodity}
              onChange={e => setCommodity(e.target.value)}
            >
              <option value="gold">Gold</option>
              <option value="copper">Copper</option>
            </select>
          </div>
          <Button onClick={generateDossier} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Zap className="w-4 h-4 mr-1" />}
            Generate Dossier
          </Button>
          {dossier && (
            <Button variant="outline">
              <Download className="w-4 h-4 mr-1" /> Export PDF
            </Button>
          )}
        </CardContent>
      </Card>

      {error && (
        <APIOffline 
          error={error} 
          endpoint="generateGeologicalReport backend function" 
          onRetry={generateDossier}
          hint="Ensure the generateGeologicalReport backend function is deployed and accessible."
        />
      )}

      {dossier && (
        <div className="space-y-5">
          <Card className="border-blue-200 bg-blue-50">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="w-5 h-5" /> Executive Intelligence
                </CardTitle>
                <Badge className={INVESTMENT_GRADE_COLORS[dossier.investment_grade] || ""}>
                  {dossier.investment_grade}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="text-sm space-y-2 leading-relaxed">
              <p className="font-semibold">{dossier.executive_summary}</p>
              <div className="text-xs text-blue-900 space-y-1 mt-3 border-t border-blue-200 pt-3">
                <div><strong>System:</strong> {dossier.system?.system_name}</div>
                <div><strong>Model:</strong> {dossier.system?.deposit_model}</div>
                <div><strong>ACIF Score:</strong> {dossier.acif_score}</div>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="spatial">
            <TabsList>
              <TabsTrigger value="spatial" className="gap-1">
                <MapPin className="w-3.5 h-3.5" /> Spatial
              </TabsTrigger>
              <TabsTrigger value="twin" className="gap-1">
                <BarChart3 className="w-3.5 h-3.5" /> Twin
              </TabsTrigger>
              <TabsTrigger value="targets" className="gap-1">
                <Zap className="w-3.5 h-3.5" /> Targets
              </TabsTrigger>
              <TabsTrigger value="resource" className="gap-1">
                <DollarSign className="w-3.5 h-3.5" /> Resource
              </TabsTrigger>
              <TabsTrigger value="uncertainty" className="gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Risk
              </TabsTrigger>
              <TabsTrigger value="strategy" className="gap-1">
                <Lock className="w-3.5 h-3.5" /> Strategy
              </TabsTrigger>
            </TabsList>

            <TabsContent value="spatial" className="mt-4 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Anomaly Clustering</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-4">{dossier.spatial_intelligence?.summary}</p>
                  <SpatialHeatmapPlaceholder clusters={dossier.spatial_intelligence?.clusters} />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="twin" className="mt-4 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Voxel Model</CardTitle>
                </CardHeader>
                <CardContent>
                  <DigitalTwinVisualization twin={dossier.digital_twin} />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="targets" className="mt-4 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Drilling Targets</CardTitle>
                </CardHeader>
                <CardContent>
                  <RankedTargetsTable targets={dossier.ranked_targets} />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="resource" className="mt-4 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Resource & EPVI</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResourceEstimationChart tonnage={dossier.tonnage_estimate} epvi={dossier.epvi} />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="uncertainty" className="mt-4 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Uncertainty</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="border rounded p-3">
                      <div className="text-xs text-muted-foreground">Spatial</div>
                      <div className="font-bold">±{dossier.uncertainty_quantification?.spatial_uncertainty_km} km</div>
                    </div>
                    <div className="border rounded p-3">
                      <div className="text-xs text-muted-foreground">Depth</div>
                      <div className="font-bold">±{dossier.uncertainty_quantification?.depth_uncertainty_m} m</div>
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-xs mb-2">Sources:</p>
                    <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                      {dossier.uncertainty_quantification?.primary_uncertainty_sources?.map((src, i) => (
                        <li key={i}>{src}</li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="strategy" className="mt-4 space-y-4">
              {["operator", "investor", "sovereign"].map(audience => (
                <Card key={audience}>
                  <CardHeader>
                    <CardTitle className="text-sm capitalize">
                      {audience === "operator" ? "Operator" : audience === "investor" ? "Investor" : "Sovereign"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm leading-relaxed">
                    {dossier.strategies?.[audience]}
                  </CardContent>
                </Card>
              ))}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}