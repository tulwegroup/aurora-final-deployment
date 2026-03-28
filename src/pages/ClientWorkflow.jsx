/**
 * ClientWorkflow — End-to-End Client AOI → Scan → View → Export
 * Phase AI §AI.1
 *
 * CONSTITUTIONAL RULES:
 *   - Zero scientific computation in this file or any child component.
 *   - All visuals read verbatim from canonical stored outputs.
 *   - No ACIF formula, no tier derivation, no calibration logic.
 *   - All data displayed is sourced from backend API responses.
 */
import { useState, useEffect } from "react";
import AOIStep from "../components/workflow/AOIStep";
import ScanParamsStep from "../components/workflow/ScanParamsStep";
import ScanResultsView from "../components/workflow/ScanResultsView";
import ExportStep from "../components/workflow/ExportStep";
import { CheckCircle, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GHANA_AOI, DEMO_SCAN_ID } from "../lib/demoData";

const STEPS = [

  { id: "aoi",     label: "Define AOI" },
  { id: "params",  label: "Scan Parameters" },
  { id: "results", label: "View Outputs" },
  { id: "export",  label: "Export / Share" },
];

export default function ClientWorkflow() {
  const [step, setStep]         = useState(0);
  const [aoi, setAoi]           = useState(null);
  const [scanParams, setScanParams] = useState(null);
  const [scanId, setScanId]     = useState(null);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "ghana-gold") activateDemo();
  }, []);

  function activateDemo() {
    setDemoMode(true);
    setAoi(GHANA_AOI);
    setScanId(DEMO_SCAN_ID);
    setStep(1);
  }

  function handleAoiDone(aoiData) {

    setAoi(aoiData);
    setStep(1);
  }

  function handleParamsDone(params, newScanId) {
    setScanParams(params);
    setScanId(newScanId);
    setStep(2);
  }

  function handleViewDone() {
    setStep(3);
  }

  function handleRestart() {
    setAoi(null); setScanParams(null); setScanId(null); setStep(0);
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">New Scan Workflow</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Define your area, configure the scan, view canonical outputs, and share securely.
          </p>
        </div>
        {!demoMode && step === 0 && (
          <Button variant="outline" size="sm" onClick={activateDemo} className="shrink-0 gap-2 border-amber-400 text-amber-700 hover:bg-amber-50">
            <FlaskConical className="w-4 h-4" /> Ghana Gold Demo
          </Button>
        )}
        {demoMode && (
          <span className="text-xs bg-amber-100 text-amber-800 border border-amber-300 px-2.5 py-1 rounded-full font-medium">
            🇬🇭 Demo Mode — Ashanti Belt, Ghana
          </span>
        )}
      </div>

      {/* Step indicator */}

      <nav className="flex items-center gap-0">
        {STEPS.map((s, i) => {
          const done    = i < step;
          const active  = i === step;
          return (
            <div key={s.id} className="flex items-center flex-1 last:flex-none">
              <button
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? "bg-primary text-primary-foreground" :
                  done   ? "text-emerald-600 cursor-pointer hover:bg-muted" :
                           "text-muted-foreground cursor-not-allowed"
                }`}
                disabled={!done && !active}
                onClick={() => done && setStep(i)}
              >
                {done
                  ? <CheckCircle className="w-4 h-4 shrink-0" />
                  : <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
                      active ? "border-primary-foreground text-primary-foreground" : "border-muted-foreground"
                    }`}>{i + 1}</span>
                }
                {s.label}
              </button>
              {i < STEPS.length - 1 && (
                <div className={`h-px flex-1 mx-2 ${done ? "bg-emerald-300" : "bg-border"}`} />
              )}
            </div>
          );
        })}
      </nav>

      {/* Step content */}
      <div className="min-h-[500px]">
        {step === 0 && <AOIStep onDone={handleAoiDone} demoMode={demoMode} />}
        {step === 1 && <ScanParamsStep aoi={aoi} onDone={handleParamsDone} onBack={() => setStep(0)} demoMode={demoMode} />}
        {step === 2 && <ScanResultsView scanId={scanId} aoi={aoi} onExport={handleViewDone} demoMode={demoMode} />}
        {step === 3 && <ExportStep scanId={scanId} onRestart={handleRestart} demoMode={demoMode} />}
      </div>
    </div>
  );
}