/**
 * PortfolioRankingTable — ranked portfolio table
 * Phase AD §AD.7 (Corrected)
 *
 * CORRECTIONS APPLIED:
 *   - portfolio_score → exploration_priority_index
 *   - weight_config_version shown in footer
 *   - Column header updated to "EPI ▾" (Exploration Priority Index)
 *
 * CONSTITUTIONAL RULE: all values from stored canonical outputs.
 * EPI is explicitly labeled as a non-physical aggregation metric.
 */
const RISK_STYLES = {
  low:    "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  high:   "bg-red-100 text-red-700",
};

export default function PortfolioRankingTable({ entries, onSelect, selectedId }) {
  if (!entries || entries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground p-6 border rounded-lg text-center">
        No portfolio entries to display.
      </div>
    );
  }

  // Weight config from first entry (all should match within a snapshot)
  const weightVer = entries[0]?.weight_config_version;

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-muted/40 border-b">
            {["#", "Territory", "Commodity", "Country", "EPI ▾", "Risk", "Scans", "ACIF Mean", "T1 Cells", "Veto Rate"].map(h => (
              <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map(e => (
            <tr
              key={e.entry_id}
              onClick={() => onSelect?.(e)}
              className={`border-b cursor-pointer transition-colors
                ${selectedId === e.entry_id ? "bg-primary/10" : "hover:bg-muted/20"}`}
            >
              <td className="px-3 py-2 font-mono text-muted-foreground">
                {e.exploration_priority_rank || "—"}
              </td>
              <td className="px-3 py-2 font-medium max-w-[140px] truncate">{e.block_name}</td>
              <td className="px-3 py-2 capitalize">{e.commodity}</td>
              <td className="px-3 py-2">{e.country_code}</td>
              <td className="px-3 py-2 tabular-nums font-bold">
                {e.exploration_priority_index != null
                  ? `${(e.exploration_priority_index * 100).toFixed(1)}%`
                  : "—"}
              </td>
              <td className="px-3 py-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${RISK_STYLES[e.risk_tier] || ""}`}>
                  {e.risk_tier}
                </span>
              </td>
              <td className="px-3 py-2 tabular-nums">{e.scan_count}</td>
              <td className="px-3 py-2 tabular-nums font-mono">
                {e.raw_acif_mean?.toFixed(4) ?? "—"}
              </td>
              <td className="px-3 py-2 tabular-nums">{e.tier1_total ?? "—"}</td>
              <td className="px-3 py-2 tabular-nums">
                {e.veto_rate != null ? `${(e.veto_rate * 100).toFixed(1)}%` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t px-3 py-1.5 text-[10px] text-muted-foreground bg-muted/20 flex items-center justify-between">
        <span>
          EPI = Exploration Priority Index — non-physical aggregation metric.
          Not a geological score or ACIF value. Inputs: stored acif_mean, tier1_density, veto compliance.
        </span>
        {weightVer && <span className="font-mono ml-2">config: {weightVer}</span>}
      </div>
    </div>
  );
}