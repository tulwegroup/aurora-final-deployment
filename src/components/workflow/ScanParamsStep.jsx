/**
 * ScanParamsStep — Step 2: Configure and Submit Scan
 * Phase AI §AI.3
 *
 * No scientific computation — parameters are infrastructure choices only.
 * Cost estimate is advisory and sourced from scan_cost_model (infrastructure).
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ChevronLeft, ChevronRight, Info } from "lucide-react";
import { base44 } from "@/api/base44Client";

const COMMODITIES  = ["gold", "copper", "nickel", "lithium", "petroleum"];
const RESOLUTIONS  = [
  { value: "low",      label: "Low (2 km cells)",     note: "Fast, regional overview" },
  { value: "standard", label: "Standard (500 m cells)", note: "Recommended for most AOIs" },
  { value: "high",     label: "High (250 m cells)",   note: "Detailed, higher cost" },
];

export default function ScanParamsStep({ aoi, onDone, onBack }) {
  const [commodity,   setCommodity]   = useState("gold");
  const [resolution,  setResolution]  = useState("standard");
  const [submitting,  setSubmitting]  = useState(false);
  const [costEst,     setCostEst]     = useState(null);
  const [error,       setError]       = useState(null);

  async function fetchCost(res) {
    try {
      const r = await base44.functions.invoke("estimateScanCost", {
        area_km2: aoi.area_km2, resolution: res,
      });
      setCostEst(r.data);
    } catch {}
  }

  function handleResolutionChange(v) {
    setResolution(v);
    fetchCost(v);
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await base44.functions.invoke("submitScan", {
        aoi_id: aoi.aoi_id, commodity, resolution,
      });
      onDone({ commodity, resolution }, res.data.scan_id);
    } catch (e) {
      setError(e.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">Commodity</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {COMMODITIES.map(c => (
              <button key={c}
                onClick={() => setCommodity(c)}
                className={`px-3 py-1.5 rounded-full border text-sm capitalize transition-colors ${
                  commodity === c ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"
                }`}
              >{c}</button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">Resolution</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {RESOLUTIONS.map(r => (
              <button key={r.value}
                onClick={() => handleResolutionChange(r.value)}
                className={`w-full flex items-start gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                  resolution === r.value ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
                }`}
              >
                <div className={`w-4 h-4 mt-0.5 rounded-full border-2 shrink-0 ${
                  resolution === r.value ? "border-primary bg-primary" : "border-muted-foreground"
                }`} />
                <div>
                  <div className="text-sm font-medium">{r.label}</div>
                  <div className="text-xs text-muted-foreground">{r.note}</div>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex gap-3">
          <Button variant="outline" onClick={onBack}><ChevronLeft className="w-4 h-4 mr-1" />Back</Button>
          <Button className="flex-1" disabled={submitting} onClick={handleSubmit}>
            {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Submitting…</> : <>Submit Scan <ChevronRight className="w-4 h-4 ml-1" /></>}
          </Button>
        </div>
      </div>

      {/* AOI summary + cost estimate */}
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base">AOI Summary</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[
              ["AOI ID",   aoi?.aoi_id?.slice(0, 16) + "…"],
              ["Area",     `${aoi?.area_km2?.toFixed(1)} km²`],
              ["Environment", aoi?.environment_type || "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-mono text-xs">{v}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {costEst && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Info className="w-4 h-4 text-blue-500" /> Cost Estimate (advisory)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {[
                ["Estimated cells", costEst.estimated_cells?.toLocaleString()],
                ["Cost per km²",    `$${costEst.cost_per_km2_usd?.toFixed(4)}`],
                ["Estimated cost",  `$${costEst.estimated_cost_usd?.toFixed(2)}`],
                ["Cost tier",       costEst.cost_tier],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-medium capitalize">{v}</span>
                </div>
              ))}
              <p className="text-xs text-muted-foreground pt-1 border-t">
                Cost model v{costEst.cost_model_version} · Advisory only · Does not affect scan outputs.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}