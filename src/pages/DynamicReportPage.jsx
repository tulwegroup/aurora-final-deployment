/**
 * DynamicReportPage — Full report viewer using modular composition engine
 */
import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Download, FileText } from "lucide-react";
import { composeReport } from "../lib/reportComposer";
import DynamicReportRenderer from "../components/DynamicReportRenderer";
import APIOffline from "../components/APIOffline";

export default function DynamicReportPage() {
  const { scanId } = useParams();
  const [commodity, setCommodity] = useState("gold");
  const [region, setRegion] = useState("Ghana Onshore Basin");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generateReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      // Mock scan data from backend
      const scanData = {
        acif_score: 0.6195,
        tier_counts: { TIER_1: 99, TIER_2: 47, TIER_3: 88, BELOW: 153 },
        spatial_intelligence: {
          clusters: [
            { id: "Cluster A", centroid: { lat: -5.2341, lon: -1.5432 }, cell_count: 8, avg_acif: 0.7812 },
            { id: "Cluster B", centroid: { lat: -5.4521, lon: -1.6123 }, cell_count: 3, avg_acif: 0.6234 },
          ],
        },
        digital_twin: {
          depth_probability_profile: {
            surface_0_250m: 0.85,
            mid_250_500m: 0.72,
            deep_500_1000m: 0.54,
            very_deep_1000_plus: 0.28,
          },
          optimal_drilling_window_m: { min: 50, optimal: 300 },
          window_confidence_score: 0.72,
        },
        tonnage_estimate: {
          p10_tonnes: 150000000,
          p50_tonnes: 75000000,
          p90_tonnes: 30000000,
        },
        epvi: {
          epvi_usd: 2500000000,
          upside_if_acif_85: 3250000000,
          downside_if_acif_55: 1500000000,
        },
        ranked_targets: [
          { rank: 1, target_id: "TGT-1", acif: "0.7812", centroid_lat: -5.2341, centroid_lon: -1.5432, dominant_signal: "SAR + CAI", depth_window_m: "50-300m", drilling_priority: "immediate" },
          { rank: 2, target_id: "TGT-2", acif: "0.6234", centroid_lat: -5.4521, centroid_lon: -1.6123, dominant_signal: "Thermal", depth_window_m: "100-400m", drilling_priority: "phase-2" },
        ],
        uncertainty_quantification: {
          spatial_uncertainty_km: 1.5,
          depth_uncertainty_m: 100,
          primary_uncertainty_sources: [
            "Remote sensing can resolve alteration, not grade or depth",
            "Voxel model depth decay below 1000m is lower confidence",
            "Regional geothermal activity may mask thermal signatures",
          ],
        },
      };

      // Compose dynamic report
      const composed = composeReport(scanData, commodity, region);
      setReport(composed);
    } catch (e) {
      setError(e.message || "Failed to generate report");
    } finally {
      setLoading(false);
    }
  }, [commodity, region, scanId]);

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <FileText className="w-7 h-7" /> Aurora Dynamic Report
        </h1>
        <p className="text-sm text-muted-foreground">
          Modular, data-driven report composition with ground truth validation and digital twin analysis
        </p>
      </div>

      {/* Controls */}
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
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground uppercase">Region</label>
            <input
              type="text"
              className="text-sm border rounded px-2 py-1.5 bg-background"
              value={region}
              onChange={e => setRegion(e.target.value)}
            />
          </div>
          <Button onClick={generateReport} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <FileText className="w-4 h-4 mr-1" />}
            Compose Report
          </Button>
          {report && (
            <Button variant="outline" className="gap-2">
              <Download className="w-4 h-4" /> Export PDF
            </Button>
          )}
        </CardContent>
      </Card>

      {error && (
        <APIOffline error={error} endpoint="report composition" onRetry={generateReport} />
      )}

      {/* Report output */}
      {report && (
        <div className="space-y-6 print:space-y-8">
          {/* Cover page */}
          <div className="bg-gradient-to-br from-slate-900 to-slate-700 text-white p-8 rounded-lg space-y-6">
            <div>
              <p className="text-sm font-mono uppercase tracking-widest text-blue-300">CONFIDENTIAL</p>
              <h1 className="text-4xl font-bold mt-4">Aurora ACIF</h1>
              <p className="text-xl text-slate-300 mt-1">Subsurface Intelligence Report</p>
            </div>

            <div className="border-l-4 border-blue-400 pl-4 space-y-2 text-sm">
              <p><span className="text-slate-400">Commodity:</span> <span className="font-bold uppercase">{report.metadata.commodity}</span></p>
              <p><span className="text-slate-400">Region:</span> <span className="font-bold">{report.metadata.region}</span></p>
              <p><span className="text-slate-400">Generated:</span> <span className="font-mono text-xs">{new Date(report.metadata.generated_at).toLocaleString()}</span></p>
            </div>

            <div className="text-xs text-slate-400">
              Investor / Sovereign Use Only
            </div>
          </div>

          {/* Dynamic sections */}
          <DynamicReportRenderer report={report} />
        </div>
      )}
    </div>
  );
}