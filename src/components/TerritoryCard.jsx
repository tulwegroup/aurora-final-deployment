/**
 * TerritoryCard — portfolio territory detail card
 * Phase AD §AD.6 (Corrected)
 *
 * CORRECTIONS APPLIED:
 *   - portfolio_score → exploration_priority_index
 *   - weight_config_version shown in detailed view
 *   - Metric label displayed to enforce non-physical classification
 *
 * CONSTITUTIONAL RULE: all values displayed verbatim from stored canonical outputs.
 * exploration_priority_index is labeled as a non-physical aggregation metric.
 */
const RISK_STYLES = {
  low:    "bg-emerald-100 text-emerald-800 border-emerald-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  high:   "bg-red-100 text-red-800 border-red-300",
};

const INDEX_COLOR = (idx) => {
  if (idx >= 0.7) return "text-emerald-700";
  if (idx >= 0.4) return "text-amber-700";
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

  const idx = entry.exploration_priority_index ?? 0;
  const pct = Math.round(idx * 100);

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
          {entry.exploration_priority_rank && (
            <span className="text-xs bg-slate-100 text-slate-700 rounded px-1.5 py-0.5 font-mono">
              #{entry.exploration_priority_rank}
            </span>
          )}
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded border ${RISK_STYLES[entry.risk_tier] || ""}`}>
            {entry.risk_tier} risk
          </span>
        </div>
      </div>

      {/* Index bar */}
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Exploration Priority Index</span>
          <span className={`text-sm font-bold tabular-nums ${INDEX_COLOR(idx)}`}>{pct}%</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="text-[9px] text-muted-foreground italic">
          Non-physical aggregation metric — not a geological score or ACIF value
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

      {/* Detailed: weight config + risk notes + contributions */}
      {detailed && (
        <>
          <div className="border-t pt-2 space-y-0.5">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide">Weight Config</div>
            <div className="text-[10px] font-mono text-muted-foreground">{entry.weight_config_version}</div>
            {entry.weights_used && (
              <div className="text-[10px] text-muted-foreground">
                acif={entry.weights_used.w_acif_mean} · tier1={entry.weights_used.w_tier1_density} · veto={entry.weights_used.w_veto_compliance}
              </div>
            )}
          </div>

          {entry.risk_notes?.length > 0 && (
            <div className="border-t pt-2 space-y-1">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wide">Risk Notes</div>
              {entry.risk_notes.map((note, i) => (
                <div key={i} className="text-xs text-muted-foreground">• {note}</div>
              ))}
            </div>
          )}

          {entry.contributions?.length > 0 && (
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
        </>
      )}
    </div>
  );
}