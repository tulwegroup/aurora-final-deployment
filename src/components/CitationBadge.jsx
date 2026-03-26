/**
 * CitationBadge — canonical field citation display
 * Phase AB §AB.8
 *
 * Renders a single CitationRef as a compact, hoverable badge.
 * Shows field_path and stored_value verbatim.
 *
 * CONSTITUTIONAL RULE: stored_value is always displayed verbatim —
 * never formatted, rounded, or transformed for display.
 */
import { useState } from "react";
import { Database } from "lucide-react";

export default function CitationBadge({ citation }) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!citation) return null;

  return (
    <span className="relative inline-block">
      <button
        className="inline-flex items-center gap-1 text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200 rounded px-1.5 py-0.5 hover:bg-blue-100 transition-colors cursor-pointer"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(v => !v)}
        title={`${citation.field_path} = "${citation.stored_value}"`}
      >
        <Database className="w-2.5 h-2.5" />
        {citation.field_path}
      </button>

      {showTooltip && (
        <div className="absolute bottom-full left-0 mb-1 z-50 w-64 bg-white border rounded-lg shadow-lg p-3 text-xs space-y-1">
          <div className="font-medium text-foreground">{citation.field_path}</div>
          <div className="font-mono text-blue-700 bg-blue-50 rounded px-1.5 py-1 break-all">
            {citation.stored_value}
          </div>
          {citation.relevance && (
            <div className="text-muted-foreground">{citation.relevance}</div>
          )}
        </div>
      )}
    </span>
  );
}

export function CitationList({ citations }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {citations.map((c, i) => (
        <CitationBadge key={`${c.field_path}-${i}`} citation={c} />
      ))}
    </div>
  );
}