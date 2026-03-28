/**
 * ReportViewer — Geological Interpretation Report Viewer
 * Phase AB §AB.10
 *
 * Generates and displays audience-specific geological reports
 * grounded on frozen canonical scan data.
 *
 * Flow:
 *   1. Fetch scan summary (canonical data only)
 *   2. Select audience
 *   3. Call generateGeologicalReport backend function
 *   4. Display 4 sections with canonical field citations
 *   5. Show full audit trail
 *
 * CONSTITUTIONAL RULE: this page never displays computed scores —
 * only stored canonical values. No ACIF is recomputed here.
 */
import { useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import ReportSection from "../components/ReportSection";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft, FileText, Shield, AlertTriangle, Download } from "lucide-react";
import APIOffline from "../components/APIOffline";

// Mineral system logic — injected into prompt (approved entries from registry)
// In production this is fetched from the backend registry
const MSL_STUBS = {
  gold: {
    commodity: "gold", version: "1.0.0",
    deposit_models: ["Orogenic gold (USGS model 36a)", "Epithermal low-sulphidation (USGS model 25a)"],
    expected_drivers: ["Hydrothermal alteration zones (SWIR)", "Structural corridors and shear zones", "Gravity lows over granitoids"],
    structural_context: "Gold mineralisation commonly associated with crustal-scale shear zones and brittle-ductile transition zones.",
    key_observables: ["x_spec_7", "x_spec_8", "x_grav_1", "x_mag_2"],
    geophysical_signature: "Residual gravity low over granitoids. Magnetic low over alteration zones.",
    uncertainty_note: "Spectral alteration signatures are not unique to gold. Remote sensing cannot confirm grade, depth, or continuity.",
    known_false_positives: ["Laterite profiles with similar SWIR signatures", "Barren granitoids producing gravity lows"],
  },
  copper: {
    commodity: "copper", version: "1.0.0",
    deposit_models: ["Porphyry copper (USGS model 17)", "IOCG (USGS model 24b)"],
    expected_drivers: ["Alteration haloes around intrusive centres", "Circular gravity anomaly over porphyry systems"],
    structural_context: "Porphyry systems in convergent margin settings above subduction zones.",
    key_observables: ["x_spec_3", "x_spec_7", "x_grav_1", "x_mag_1"],
    geophysical_signature: "Concentric geophysical zonation: central magnetic high, annular magnetic low, peripheral gravity high.",
    uncertainty_note: "Many porphyry-like signatures are barren. Depth and grade cannot be inferred from surface remote sensing.",
    known_false_positives: ["Mafic intrusions producing similar magnetic patterns", "Unrelated iron oxide formation"],
  },
};

const AUDIENCES = [
  { value: "sovereign_government", label: "Sovereign / Government" },
  { value: "operator_technical",   label: "Operator / Technical" },
  { value: "investor_executive",   label: "Investor / Executive" },
];

const STATUS_STYLES = {
  final:    "bg-emerald-100 text-emerald-800",
  redacted: "bg-amber-100 text-amber-800",
  draft:    "bg-slate-100 text-slate-600",
};

// Stub canonical data — production: fetched from /api/v1/scans/{scanId}
function buildStubPayload(scanId, audience, commodity) {
  const msl = MSL_STUBS[commodity] || MSL_STUBS.gold;
  return {
    scan_id:   scanId,
    audience,
    commodity,
    acif_score: 0.7412,
    tier_counts: { TIER_1: 12, TIER_2: 47, TIER_3: 88, BELOW: 153 },
    tier_thresholds: { TIER_1: 0.75, TIER_2: 0.55, TIER_3: 0.35 },
    system_status: "PASS_CONFIRMED",
    veto_explanations: [],
    component_scores: { evidence: 0.7812, causal: 0.6934, physics: 0.8201 },
    calibration_version_id: "cal-v1",
    scan_date: new Date().toISOString().slice(0, 10),
    pipeline_version: "vnext-1.0.0",
    total_cells: 300,
    cells_above_tier1: 12,
    mineral_system_logic: msl,
  };
}

export default function ReportViewer() {
  const { scanId } = useParams();
  const effectiveScanId = scanId || "demo-scan";

  const [audience, setAudience]   = useState("operator_technical");
  const [commodity, setCommodity] = useState("gold");
  const [report, setReport]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  const generateReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const payload = buildStubPayload(effectiveScanId, audience, commodity);
      const res = await base44.functions.invoke("generateGeologicalReport", payload);
      setReport(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [effectiveScanId, audience, commodity]);

  function handlePrint() {
    window.print();
  }

  return (
    <div className="p-6 max-w-5xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        {scanId && (
          <Link to={`/history/${scanId}`} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
        )}
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Geological Interpretation Report
          </h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">{effectiveScanId}</p>
        </div>
      </div>

      {/* Generation controls */}
      <Card>
        <CardContent className="py-4 flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Commodity</label>
            <select
              className="text-sm border rounded px-2 py-1.5 bg-background"
              value={commodity}
              onChange={e => setCommodity(e.target.value)}
            >
              {Object.keys(MSL_STUBS).map(c => (
                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Audience</label>
            <div className="flex gap-2 flex-wrap">
              {AUDIENCES.map(a => (
                <button
                  key={a.value}
                  onClick={() => setAudience(a.value)}
                  className={`text-sm px-3 py-1.5 rounded border transition-colors
                    ${audience === a.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-input hover:bg-muted"}`}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={generateReport} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <FileText className="w-4 h-4 mr-1" />}
            Generate Report
          </Button>
          {report && (
            <Button variant="outline" onClick={handlePrint}>
              <Download className="w-4 h-4 mr-1" /> Print / Export
            </Button>
          )}
        </CardContent>
      </Card>

      {error && <APIOffline error={error} endpoint="generateGeologicalReport backend function" onRetry={generateReport} />}

      {/* Report output */}
      {report && (
        <div className="space-y-5">
          {/* Summary card */}
          <Card>
            <CardContent className="py-4 space-y-3">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="space-y-1">
                  <div className="font-semibold">{report.commodity?.toUpperCase()} — {AUDIENCES.find(a => a.value === report.audience)?.label}</div>
                  <div className="text-sm text-muted-foreground">{report.summary}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded font-medium ${STATUS_STYLES[report.status] || ""}`}>
                    {report.status}
                  </span>
                  {report.has_redactions && (
                    <span className="text-xs flex items-center gap-1 text-amber-700">
                      <AlertTriangle className="w-3 h-3" /> Contains redactions
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="sections">
            <TabsList>
              <TabsTrigger value="sections">Report Sections</TabsTrigger>
              <TabsTrigger value="audit">Audit Trail</TabsTrigger>
            </TabsList>

            <TabsContent value="sections" className="mt-4 space-y-4">
              {report.sections?.map(section => (
                <Card key={section.section_type}>
                  <CardContent className="py-5 px-6">
                    <ReportSection section={section} />
                  </CardContent>
                </Card>
              ))}
            </TabsContent>

            <TabsContent value="audit" className="mt-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <Shield className="w-4 h-4" /> Audit Trail
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 text-xs">
                    {[
                      ["Report ID",                   report.report_id],
                      ["Report version",              report.audit?.report_version],
                      ["Prompt version",              report.audit?.prompt_version],
                      ["Grounding snapshot hash",     report.audit?.grounding_snapshot_hash?.slice(0,32) + "…"],
                      ["Calibration version",         report.audit?.calibration_version_id],
                      ["Mineral system logic version",report.audit?.mineral_system_logic_version],
                      ["Generated at",               report.audit?.generated_at?.slice(0,19)],
                      ["Generated by",               report.audit?.generated_by],
                      ["LLM model hint",             report.audit?.llm_model_hint],
                    ].map(([label, value]) => (
                      <div key={label} className="flex justify-between gap-4 py-1 border-b last:border-0">
                        <span className="text-muted-foreground">{label}</span>
                        <span className="font-mono text-right break-all">{value || "—"}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 text-[10px] text-muted-foreground border-t pt-2 space-y-1">
                    <div>grounding_snapshot_hash: SHA-256 of full grounding bundle — any change to input data produces a different hash.</div>
                    <div>No canonical scan was rescored or retiered during report generation.</div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}