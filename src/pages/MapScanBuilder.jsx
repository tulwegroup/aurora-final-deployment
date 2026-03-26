/**
 * MapScanBuilder — AOI-first scan initiation surface
 * Phase AA §AA.9
 *
 * Full workflow:
 *   1. Draw / upload AOI geometry on Google Maps
 *   2. Validate geometry (API call)
 *   3. Save immutable ScanAOI (returns aoi_id + geometry_hash)
 *   4. Preview: area, cell count, cost tier, environment
 *   5. Choose commodity + resolution
 *   6. Submit scan (scan_id + geometry_hash returned)
 *
 * CONSTITUTIONAL RULES:
 *   - No scientific computation in this page.
 *   - Geometry never modified after save.
 *   - aoi_id + geometry_hash carried through to scan reference.
 */
import { useState, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import MapDrawTool from "../components/MapDrawTool";
import AOIPreviewPanel from "../components/AOIPreviewPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle, AlertTriangle } from "lucide-react";

const COMMODITIES = [
  "gold", "copper", "iron", "nickel", "lithium",
  "cobalt", "uranium", "diamonds", "pgm", "zinc",
];

const RESOLUTION_OPTIONS = [
  { value: "fine",   label: "Fine (~1 km²/cell)" },
  { value: "medium", label: "Medium (~5 km²/cell)" },
  { value: "coarse", label: "Coarse (~25 km²/cell)" },
  { value: "survey", label: "Survey (~100 km²/cell)" },
];

const STEPS = ["Draw AOI", "Validate", "Preview", "Submit"];

export default function MapScanBuilder() {
  const [step, setStep]               = useState(0);
  const [geometry, setGeometry]       = useState(null);
  const [validation, setValidation]   = useState(null);
  const [savedAOI, setSavedAOI]       = useState(null);
  const [estimate, setEstimate]       = useState(null);
  const [commodity, setCommodity]     = useState("gold");
  const [resolution, setResolution]   = useState("medium");
  const [submittedScan, setSubmitted] = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);

  const handleGeometryReady = useCallback((geo) => {
    setGeometry(geo);
    setValidation(null);
    setSavedAOI(null);
    setEstimate(null);
    setSubmitted(null);
    setError(null);
    setStep(1);
  }, []);

  async function validateAndSave() {
    if (!geometry) return;
    setLoading(true);
    setError(null);
    try {
      // Step 1: validate
      const valRes = await base44.functions.invoke("aoiValidate", { geometry });
      const val = valRes.data;
      setValidation(val);

      if (!val.valid) {
        setStep(1);
        setLoading(false);
        return;
      }

      // Step 2: save AOI
      const saveRes = await base44.functions.invoke("aoiSave", {
        geometry,
        geometry_type: "polygon",
        source_type: "drawn",
      });
      const aoi = saveRes.data;
      setSavedAOI(aoi);

      // Step 3: get workload estimate
      const estRes = await base44.functions.invoke("aoiEstimate", { aoi_id: aoi.aoi_id });
      setEstimate(estRes.data);

      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitScan() {
    if (!savedAOI) return;
    setLoading(true);
    setError(null);
    try {
      const res = await base44.functions.invoke("aoiSubmitScan", {
        aoi_id: savedAOI.aoi_id,
        commodity,
        resolution,
      });
      setSubmitted(res.data);
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-7xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Map Scan Builder</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Draw or upload an area of interest to initiate a new Aurora scan.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold border-2
              ${i < step ? "bg-primary text-primary-foreground border-primary"
                : i === step ? "border-primary text-primary"
                : "border-muted text-muted-foreground"}`}>
              {i < step ? <CheckCircle className="w-4 h-4" /> : i + 1}
            </div>
            <span className={`text-sm ${i === step ? "font-semibold" : "text-muted-foreground"}`}>
              {label}
            </span>
            {i < STEPS.length - 1 && <div className="w-8 h-0.5 bg-muted" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm border border-destructive/30 bg-destructive/5 rounded-lg px-4 py-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Map */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">
                {step === 0 ? "Draw your Area of Interest" : "AOI Selected"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MapDrawTool onGeometryReady={handleGeometryReady} savedAOI={savedAOI} />
            </CardContent>
          </Card>
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Step 0: instructions */}
          {step === 0 && (
            <Card>
              <CardContent className="py-4 text-sm space-y-2 text-muted-foreground">
                <p className="font-medium text-foreground">How to start</p>
                <p>Use the tools above the map to:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Draw a polygon</li>
                  <li>Draw a rectangle</li>
                  <li>Upload a KML/GeoJSON file</li>
                </ul>
                <p className="text-xs mt-2">
                  Once drawn, your AOI will be validated, cryptographically hashed,
                  and stored as an immutable record before scan submission.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Step 1: validate */}
          {step >= 1 && geometry && !savedAOI && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Validate AOI</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {validation && !validation.valid && (
                  <div className="space-y-1">
                    {validation.errors.map((e, i) => (
                      <div key={i} className="text-xs text-destructive flex items-start gap-1">
                        <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{e}
                      </div>
                    ))}
                  </div>
                )}
                {validation?.valid && (
                  <div className="text-xs text-emerald-700 bg-emerald-50 rounded px-2 py-1">
                    Geometry valid — saving AOI…
                  </div>
                )}
                <Button className="w-full" disabled={loading} onClick={validateAndSave}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                  Validate & Save AOI
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Step 2: preview + parameters */}
          {step >= 2 && savedAOI && (
            <>
              <AOIPreviewPanel aoi={savedAOI} estimate={estimate} />

              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Scan Parameters</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground uppercase tracking-wide">Commodity</label>
                    <select
                      className="w-full text-sm border rounded px-2 py-1.5 bg-background"
                      value={commodity}
                      onChange={e => setCommodity(e.target.value)}
                    >
                      {COMMODITIES.map(c => (
                        <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground uppercase tracking-wide">Resolution</label>
                    <div className="space-y-1">
                      {RESOLUTION_OPTIONS.map(opt => (
                        <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer">
                          <input
                            type="radio" name="resolution" value={opt.value}
                            checked={resolution === opt.value}
                            onChange={() => setResolution(opt.value)}
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </div>

                  <Button className="w-full" disabled={loading} onClick={submitScan}>
                    {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                    Submit Scan
                  </Button>
                </CardContent>
              </Card>
            </>
          )}

          {/* Step 3: submitted */}
          {step === 3 && submittedScan && (
            <Card>
              <CardContent className="py-4 space-y-2">
                <div className="flex items-center gap-2 text-emerald-700 font-medium">
                  <CheckCircle className="w-5 h-5" /> Scan Queued
                </div>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Scan ID</span>
                    <span className="font-mono">{submittedScan.scan_id?.slice(0,8)}…</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">AOI ID</span>
                    <span className="font-mono">{submittedScan.aoi_id?.slice(0,8)}…</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Geometry Hash</span>
                    <span className="font-mono text-[10px]">{submittedScan.geometry_hash?.slice(0,16)}…</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Commodity</span>
                    <span>{submittedScan.commodity}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Resolution</span>
                    <span>{submittedScan.resolution}</span>
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground mt-2">
                  The scan references aoi_id + geometry_hash for full reproducibility.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}