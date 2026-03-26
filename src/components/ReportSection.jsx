/**
 * ReportSection — renders a single report section with citations
 * Phase AB §AB.9
 *
 * Displays: section title, content (markdown-rendered), citation badges,
 * and optional redaction notice.
 *
 * CONSTITUTIONAL RULE: content is rendered verbatim from the report record.
 * CitationBadges display stored_value verbatim — no transformation.
 */
import ReactMarkdown from "react-markdown";
import { CitationList } from "./CitationBadge";
import { AlertTriangle, Eye } from "lucide-react";

const SECTION_ICONS = {
  observed_canonical_outputs:  "📊",
  geological_interpretation:   "🪨",
  uncertainty_and_limitations: "⚠️",
  recommended_next_steps:      "🎯",
};

export default function ReportSection({ section }) {
  if (!section) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-lg">{SECTION_ICONS[section.section_type] || "📄"}</span>
        <h3 className="font-semibold text-base">{section.title}</h3>
        {section.redaction_notes && (
          <span className="ml-auto flex items-center gap-1 text-[10px] bg-amber-50 text-amber-700 border border-amber-200 rounded px-2 py-0.5">
            <AlertTriangle className="w-2.5 h-2.5" /> Redacted
          </span>
        )}
      </div>

      {section.redaction_notes && (
        <div className="flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-amber-800">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <div>
            <span className="font-medium">Redaction notice: </span>
            {section.redaction_notes}
          </div>
        </div>
      )}

      <div className="prose prose-sm max-w-none text-foreground">
        <ReactMarkdown>{section.content}</ReactMarkdown>
      </div>

      {section.citations && section.citations.length > 0 && (
        <div className="border-t pt-2">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-1.5">
            <Eye className="w-3 h-3" />
            Canonical field citations ({section.citations.length})
          </div>
          <CitationList citations={section.citations} />
        </div>
      )}
    </div>
  );
}