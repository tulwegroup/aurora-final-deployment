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
import { useNavigate } from "react-router-dom";
import { aoi as aoiApi, scans as scansApi } from "../lib/auroraApi";
import { base44 } from '@/api/base44Client';
// base44 imported to persist ScanJob execution records (not canonical scans)
import MapDrawTool from "../components/MapDrawTool";
import AOIPreviewPanel from "../components/AOIPreviewPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle, AlertTriangle } from "lucide-react";

const COMMODITY_GROUPS = [
  { group: "Precious Metals",  items: ["gold", "silver", "pgm"] },
  { group: "Gemstones",        items: ["diamonds"] },
  { group: "Base Metals",      items: ["copper", "nickel", "zinc", "lead", "tin", "iron"] },
  { group: "Battery & EV",     items: ["lithium", "cobalt"] },
  { group: "Strategic",        items: ["uranium", "tungsten", "molybdenum", "potash", "manganese", "chromite"] },
  { group: "Bulk Minerals",    items: ["bauxite", "phosphate"] },
  { group: "Hydrocarbons",     items: ["petroleum"] },
];

// Aurora scan tier enum values (BOOTSTRAP/SMART/PREMIUM)
// Display labels show cell resolution in km/m as the user expects
const RESOLUTION_OPTIONS = [
  { value: "BOOTSTRAP", label: "BOOTSTRAP — ~5 km cells (coarse global screening)" },
  { value: "SMART",     label: "SMART — ~1 km cells (regional refinement, recommended)" },
  { value: "PREMIUM",   label: "PREMIUM — ~250 m cells (drill-target scale)" },
];

const STEPS = ["Draw AOI", "Validate", "Preview", "Submit"];

export default function MapScanBuilder() {
  const navigate = useNavigate();
  const [step, setStep]               = useState(0);
  const [geometry, setGeometry]       = useState(null);
  const [validation, setValidation]   = useState(null);
  const [savedAOI, setSavedAOI]       = useState(null);
  const [estimate, setEstimate]       = useState(null);
  const [commodity, setCommodity]     = useState("gold");
  const [resolution, setResolution]   = useState("SMART");
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
      const val = await aoiApi.validate(geometry);
      setValidation(val);

      if (!val.valid) {
        setStep(1);
        setLoading(false);
        return;
      }

      // Step 2: save AOI
      const savedAoi = await aoiApi.save({
        geometry,
        geometry_type: "polygon",
        source_type: "drawn",
      });
      setSavedAOI(savedAoi);

      // Step 3: get workload estimate (best-effort, not blocking)
      try {
        const est = await aoiApi.estimate(savedAoi.aoi_id);
        setEstimate(est);
      } catch {}

      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitScan() {
    if (!geometry) return;
    setLoading(true);
    setError(null);
    try {
      let res;
      // Try AOI-based submission first, fall back to direct polygon scan
      try {
        res = await aoiApi.submitScan(savedAOI.aoi_id, { commodity, resolution });
      } catch {
        res = await scansApi.submitPolygon({
          commodity,
          scan_tier: resolution,          // BOOTSTRAP | SMART | PREMIUM
          environment: 'ONSHORE',         // uppercase enum as Aurora requires
          aoi_polygon: geometry,
        });
      }
      // Persist execution job record — this is a ScanJob (queued state), NOT a canonical scan.
      // It will appear in the "Execution Jobs" section of Scan History only.
      // Once the Aurora pipeline completes it will surface as a canonical scan.
      const scanId = res?.scan_id || res?.scan_job_id || null;
      await base44.entities.ScanJob.create({
        scan_id: scanId,
        status: 'queued',
        commodity,
        resolution,
        geometry,
        aoi_id: savedAOI?.aoi_id || null,
      });
      setSubmitted({ ...res, scan_id: scanId });
      setStep(3);

      // Auto-navigate to live scan viewer after 2 seconds
      setTimeout(() => {
        navigate(`/scan/live/${scanId}`);
      }, 2000);
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
                  <div className="space-y-2">
                    <label className="text-xs text-muted-foreground uppercase tracking-wide">Commodity</label>
                    {COMMODITY_GROUPS.map(({ group, items }) => (
                      <div key={group}>
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-1">{group}</div>
                        <div className="flex flex-wrap gap-1">
                          {items.map(c => (
                            <button key={c} onClick={() => setCommodity(c)}
                              className={`px-2 py-0.5 rounded-full border text-xs capitalize transition-colors ${
                                commodity === c ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"
                              }`}>{c}</button>
                          ))}
                        </div>
                      </div>
                    ))}
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
              <CardContent className="py-4 space-y-3">
                <div className="flex items-center gap-2 text-emerald-700 font-medium">
                  <CheckCircle className="w-5 h-5" /> Scan Queued
                </div>
                <p className="text-sm text-muted-foreground">
                  Your scan has been accepted and is queued for processing. It will appear in Scan History once complete.
                </p>
                <div className="space-y-1 text-xs">
                  {submittedScan.scan_id && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Scan ID</span>
                      <span className="font-mono">{submittedScan.scan_id?.slice(0,8)}…</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <span className="capitalize">{submittedScan.status || 'accepted'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Commodity</span>
                    <span className="capitalize">{commodity}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Resolution</span>
                    <span>{resolution}</span>
                  </div>
                </div>
                <button
                  className="text-xs text-primary underline"
                  onClick={() => navigate('/history')}
                >
                  Go to Scan History →
                </button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}