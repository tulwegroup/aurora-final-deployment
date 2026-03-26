/**
 * TierDistribution — display tier_counts from canonical scan record
 * Phase P §P.5
 *
 * CONSTITUTIONAL RULES:
 *  - tier_counts sourced exclusively from CanonicalScan.tier_counts API field.
 *  - Percentages computed as (count / total_cells) — display only, not scoring.
 *  - tier_thresholds_used displayed verbatim from API — never hardcoded.
 *  - Null tier_counts renders MissingValue.
 */
import MissingValue from "./MissingValue";

const TIER_COLORS = {
  tier_1: "bg-emerald-500",
  tier_2: "bg-amber-500",
  tier_3: "bg-red-400",
  below:  "bg-slate-300",
};

const TIER_LABELS = {
  tier_1: "Tier 1",
  tier_2: "Tier 2",
  tier_3: "Tier 3",
  below:  "Below",
};

export default function TierDistribution({ tierCounts, totalCells, tierThresholds }) {
  if (!tierCounts) return <MissingValue label="Tier distribution unavailable" />;

  const rows = [
    { key: "tier_1", count: tierCounts.tier_1 },
    { key: "tier_2", count: tierCounts.tier_2 },
    { key: "tier_3", count: tierCounts.tier_3 },
    { key: "below",  count: tierCounts.below  },
  ];

  const total = totalCells || 1;

  return (
    <div className="space-y-3">
      {/* Stacked bar — widths are count/total, no threshold arithmetic */}
      <div className="flex h-4 rounded-full overflow-hidden gap-px">
        {rows.map(({ key, count }) => {
          if (!count) return null;
          const widthPct = (count / total) * 100;
          return (
            <div
              key={key}
              className={`${TIER_COLORS[key]} transition-all`}
              style={{ width: `${widthPct}%` }}
              title={`${TIER_LABELS[key]}: ${count} cells`}
            />
          );
        })}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-1 text-xs">
        {rows.map(({ key, count }) => (
          <div key={key} className="flex items-center gap-1.5">
            <div className={`w-2.5 h-2.5 rounded-sm ${TIER_COLORS[key]}`} />
            <span className="text-muted-foreground">{TIER_LABELS[key]}</span>
            <span className="ml-auto font-medium tabular-nums">
              {count ?? "—"}
            </span>
          </div>
        ))}
      </div>

      {/* Thresholds — verbatim from API tier_thresholds_used, never recomputed */}
      {tierThresholds && (
        <div className="text-xs text-muted-foreground border-t pt-2 mt-1">
          <span className="font-medium">Thresholds (frozen at scan completion): </span>
          T1 ≥ {tierThresholds.t1 ?? "—"} · T2 ≥ {tierThresholds.t2 ?? "—"} · T3 ≥ {tierThresholds.t3 ?? "—"}
        </div>
      )}
    </div>
  );
}