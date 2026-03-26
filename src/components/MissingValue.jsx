/**
 * MissingValue — explicit missing-data UI
 * Phase P §P.6 CONSTITUTIONAL RULE:
 * When a canonical field is null/undefined, render THIS component.
 * Never substitute a fallback number, estimated value, or default threshold.
 */
export default function MissingValue({ label = null, inline = false }) {
  if (inline) {
    return (
      <span className="text-muted-foreground text-sm italic" title={label || "No data available"}>
        —
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded"
      title={label || "No data available from canonical record"}
    >
      <span className="opacity-60">⊘</span>
      {label || "No data"}
    </span>
  );
}

/** Convenience: render value or MissingValue inline */
export function ValueOrMissing({ value, format, label }) {
  if (value === null || value === undefined) {
    return <MissingValue inline label={label} />;
  }
  const display = format ? format(value) : String(value);
  return <span>{display}</span>;
}