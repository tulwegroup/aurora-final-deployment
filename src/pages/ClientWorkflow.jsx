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
import { useState } from "react";
import AOIStep from "../components/workflow/AOIStep";
import ScanParamsStep from "../components/workflow/ScanParamsStep";
import ScanResultsView from "../components/workflow/ScanResultsView";
import ExportStep from "../components/workflow/ExportStep";
import { CheckCircle } from "lucide-react";

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
      <div>
        <h1 className="text-2xl font-bold">New Scan Workflow</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Define your area, configure the scan, view canonical outputs, and share securely.
        </p>
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
        {step === 0 && <AOIStep onDone={handleAoiDone} />}
        {step === 1 && <ScanParamsStep aoi={aoi} onDone={handleParamsDone} onBack={() => setStep(0)} />}
        {step === 2 && <ScanResultsView scanId={scanId} aoi={aoi} onExport={handleViewDone} />}
        {step === 3 && <ExportStep scanId={scanId} onRestart={handleRestart} />}
      </div>
    </div>
  );
}