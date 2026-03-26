/**
 * TerritoryCard — portfolio territory detail card
 * Phase AD §AD.6
 *
 * Displays territory metadata, portfolio score, risk tier, and scan contributions.
 *
 * CONSTITUTIONAL RULE: all values displayed verbatim from stored canonical outputs.
 * portfolio_score is labeled clearly as a composite display metric.
 * No resource classification language is used.
 */
const RISK_STYLES = {
  low:    "bg-emerald-100 text-emerald-800 border-emerald-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  high:   "bg-red-100 text-red-800 border-red-300",
};

const SCORE_COLOR = (score) => {
  if (score >= 0.7) return "text-emerald-700";
  if (score >= 0.4) return "text-amber-700";
  return "text-red-600";
};

function Stat({ label, value, mono = false }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex justify-between py-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xs font-medium ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

export default function TerritoryCard({ entry, selected = false, onClick, detailed = false }) {
  if (!entry) return null;

  const score = entry.portfolio_score ?? 0;
  const pct   = Math.round(score * 100);

  return (
    <div
      onClick={onClick}
      className={`border rounded-lg p-4 space-y-3 transition-colors
        ${onClick ? "cursor-pointer hover:bg-muted/20" : ""}
        ${selected ? "border-primary bg-primary/5" : ""}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-sm">{entry.block_name}</div>
          <div className="text-xs text-muted-foreground">
            {entry.country_code} · {entry.territory_type} · {entry.commodity}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {entry.portfolio_rank && (
            <span className="text-xs bg-slate-100 text-slate-700 rounded px-1.5 py-0.5 font-mono">
              #{entry.portfolio_rank}
            </span>
          )}
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded border ${RISK_STYLES[entry.risk_tier] || ""}`}>
            {entry.risk_tier} risk
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Portfolio Score</span>
          <span className={`text-sm font-bold tabular-nums ${SCORE_COLOR(score)}`}>{pct}%</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="text-[9px] text-muted-foreground">
          Composite of stored: ACIF mean × 0.5 + Tier 1 density × 0.3 + (1−veto rate) × 0.2
        </div>
      </div>

      {/* Key stats */}
      <div className="border-t pt-2 space-y-0.5">
        <Stat label="Scans"         value={entry.scan_count} />
        <Stat label="ACIF mean"     value={entry.raw_acif_mean?.toFixed(4)} mono />
        <Stat label="Tier 1 cells"  value={entry.tier1_total} />
        <Stat label="Total cells"   value={entry.total_cells} />
        <Stat label="Veto rate"     value={entry.veto_rate != null ? `${(entry.veto_rate * 100).toFixed(1)}%` : null} />
        {entry.gt_confidence != null && (
          <Stat label="GT confidence" value={`${(entry.gt_confidence * 100).toFixed(0)}%`} />
        )}
      </div>

      {/* Risk notes (detailed mode) */}
      {detailed && entry.risk_notes?.length > 0 && (
        <div className="border-t pt-2 space-y-1">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">Risk Notes</div>
          {entry.risk_notes.map((note, i) => (
            <div key={i} className="text-xs text-muted-foreground">• {note}</div>
          ))}
        </div>
      )}

      {/* Scan contributions (detailed mode) */}
      {detailed && entry.contributions?.length > 0 && (
        <div className="border-t pt-2 space-y-1">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide">Scan Contributions</div>
          {entry.contributions.map(c => (
            <div key={c.scan_id} className="text-[10px] font-mono text-muted-foreground flex justify-between">
              <span>{c.scan_id.slice(0, 8)}…</span>
              <span>{c.system_status}</span>
              <span>T1: {c.tier_1_count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}