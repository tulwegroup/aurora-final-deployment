/**
 * PortfolioRankingTable — ranked portfolio table
 * Phase AD §AD.7
 *
 * Displays portfolio entries ranked by portfolio_score with risk tier badges.
 * CONSTITUTIONAL RULE: all values sourced from stored canonical outputs.
 * Portfolio score is labeled as a display metric — not a scientific score.
 */
const RISK_STYLES = {
  low:    "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  high:   "bg-red-100 text-red-700",
};

const STATUS_STYLES = {
  PASS_CONFIRMED:  "text-emerald-600",
  PARTIAL_SIGNAL:  "text-amber-600",
  INCONCLUSIVE:    "text-slate-500",
  REJECTED:        "text-red-600",
};

export default function PortfolioRankingTable({ entries, onSelect, selectedId }) {
  if (!entries || entries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground p-6 border rounded-lg text-center">
        No portfolio entries to display. Assemble entries from completed scans.
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-muted/40 border-b">
            {["#", "Territory", "Commodity", "Country", "Score ▾", "Risk", "Scans", "ACIF Mean", "T1 Cells", "Veto Rate"].map(h => (
              <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                {h}
              </th>
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
              <td className="px-3 py-2 font-mono text-muted-foreground">{e.portfolio_rank || "—"}</td>
              <td className="px-3 py-2 font-medium max-w-[140px] truncate">{e.block_name}</td>
              <td className="px-3 py-2 capitalize">{e.commodity}</td>
              <td className="px-3 py-2">{e.country_code}</td>
              <td className="px-3 py-2 tabular-nums font-bold">
                {e.portfolio_score != null ? `${(e.portfolio_score * 100).toFixed(1)}%` : "—"}
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
      <div className="border-t px-3 py-1.5 text-[10px] text-muted-foreground bg-muted/20">
        Portfolio score = weighted composite of stored ACIF mean, Tier 1 density, veto compliance.
        No ACIF was recomputed. Values sourced from stored canonical records only.
      </div>
    </div>
  );
}