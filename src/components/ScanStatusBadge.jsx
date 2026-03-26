/**
 * ScanStatusBadge + TierBadge + SystemStatusBadge
 * Phase P — pure display components
 * CONSTITUTIONAL RULE: badge labels sourced from API enum values only.
 * No tier threshold arithmetic. No score comparison.
 */

const STATUS_STYLES = {
  PENDING:    "bg-yellow-100 text-yellow-800 border-yellow-300",
  RUNNING:    "bg-blue-100 text-blue-800 border-blue-300",
  COMPLETED:  "bg-green-100 text-green-800 border-green-300",
  FAILED:     "bg-red-100 text-red-800 border-red-300",
  REPROCESSING: "bg-purple-100 text-purple-800 border-purple-300",
};

const TIER_STYLES = {
  TIER_1: "bg-emerald-100 text-emerald-800 border-emerald-300",
  TIER_2: "bg-amber-100 text-amber-800 border-amber-300",
  TIER_3: "bg-red-100 text-red-800 border-red-300",
  BELOW:  "bg-slate-100 text-slate-600 border-slate-300",
};

const SYSTEM_STATUS_STYLES = {
  PASS_CONFIRMED:     "bg-emerald-100 text-emerald-800",
  PARTIAL_SIGNAL:     "bg-amber-100 text-amber-800",
  INCONCLUSIVE:       "bg-slate-100 text-slate-700",
  REJECTED:           "bg-red-100 text-red-800",
  OVERRIDE_CONFIRMED: "bg-purple-100 text-purple-800",
};

function Badge({ label, className }) {
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${className}`}>
      {label}
    </span>
  );
}

export function ScanStatusBadge({ status }) {
  if (!status) return null;
  return <Badge label={status} className={STATUS_STYLES[status] || "bg-slate-100 text-slate-700 border-slate-300"} />;
}

export function TierBadge({ tier }) {
  if (!tier) return null;
  return <Badge label={tier.replace("_", " ")} className={TIER_STYLES[tier] || "bg-slate-100 text-slate-700 border-slate-300"} />;
}

export function SystemStatusBadge({ status }) {
  if (!status) return null;
  const label = status.replace(/_/g, " ");
  return <Badge label={label} className={SYSTEM_STATUS_STYLES[status] || "bg-slate-100 text-slate-700"} />;
}