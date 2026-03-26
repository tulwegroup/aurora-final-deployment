/**
 * ScoreGrid — display canonical component scores from a CanonicalScan record
 * Phase P §P.5
 *
 * CONSTITUTIONAL RULES:
 *  - All values sourced from API response fields. No arithmetic performed.
 *  - Null fields render MissingValue — never substituted with 0 or fallback.
 *  - Score bar width = (value * 100)% — purely visual, no threshold comparison.
 *  - Field names match CanonicalScan canonical vocabulary exactly.
 */
import MissingValue from "./MissingValue";

const SCORES = [
  { key: "mean_evidence_score",  label: "Evidence (Ẽ)" },
  { key: "mean_causal_score",    label: "Causal (C)" },
  { key: "mean_physics_score",   label: "Physics (Ψ)" },
  { key: "mean_temporal_score",  label: "Temporal (T)" },
  { key: "mean_province_prior",  label: "Province Prior (Π)" },
  { key: "mean_uncertainty",     label: "Uncertainty (U)" },
];

function ScoreBar({ value }) {
  if (value === null || value === undefined) return <MissingValue inline />;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm tabular-nums w-10 text-right">{pct}%</span>
    </div>
  );
}

export default function ScoreGrid({ scan }) {
  return (
    <div className="grid gap-3">
      {SCORES.map(({ key, label }) => (
        <div key={key} className="grid grid-cols-[160px_1fr] items-center gap-3">
          <span className="text-sm text-muted-foreground">{label}</span>
          <ScoreBar value={scan?.[key]} />
        </div>
      ))}
    </div>
  );
}