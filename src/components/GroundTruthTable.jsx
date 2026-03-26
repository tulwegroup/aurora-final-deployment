/**
 * GroundTruthTable — tabular list of ground-truth records
 * Phase Z §Z.4
 *
 * Displays record_id, type, commodity, country, source, confidence composite, status.
 * No scientific output (ACIF, tier) is displayed — infrastructure metadata only.
 */
const STATUS_STYLES = {
  pending:   "bg-yellow-100 text-yellow-800",
  approved:  "bg-emerald-100 text-emerald-800",
  rejected:  "bg-red-100 text-red-800",
  superseded:"bg-slate-100 text-slate-600",
};

const TYPE_LABELS = {
  deposit_occurrence:     "Deposit",
  drill_intersection:     "Drill",
  geochemical_anomaly:    "Geochem",
  geophysical_validation: "Geophys",
  production_history:     "Production",
  basin_validation:       "Basin",
};

export default function GroundTruthTable({ records, selectedId, onSelect }) {
  if (!records || records.length === 0) {
    return (
      <div className="text-sm text-muted-foreground p-4 border rounded-lg text-center">
        No records in this category.
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-muted/40 border-b">
            {["ID","Type","Commodity","Country","Source","Confidence","Status"].map(h => (
              <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map(r => (
            <tr
              key={r.record_id}
              onClick={() => onSelect(r)}
              className={`border-b cursor-pointer transition-colors
                ${selectedId === r.record_id ? "bg-primary/10" : "hover:bg-muted/20"}`}
            >
              <td className="px-3 py-2 font-mono text-muted-foreground">{r.record_id?.slice(0,8)}…</td>
              <td className="px-3 py-2">
                <span className="bg-blue-50 text-blue-700 text-[10px] px-1.5 py-0.5 rounded">
                  {TYPE_LABELS[r.geological_data_type] || r.geological_data_type}
                </span>
              </td>
              <td className="px-3 py-2">{r.commodity}</td>
              <td className="px-3 py-2">{r.country}</td>
              <td className="px-3 py-2 max-w-[120px] truncate" title={r.source_name}>{r.source_name}</td>
              <td className="px-3 py-2 tabular-nums">
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  r.confidence_composite >= 0.7 ? "bg-emerald-50 text-emerald-700"
                  : r.confidence_composite >= 0.4 ? "bg-amber-50 text-amber-700"
                  : "bg-red-50 text-red-700"
                }`}>
                  {(r.confidence_composite * 100).toFixed(0)}%
                </span>
              </td>
              <td className="px-3 py-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_STYLES[r.status] || ""}`}>
                  {r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}