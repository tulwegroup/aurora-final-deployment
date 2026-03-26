"""
Aurora OSI vNext — Geological Report Model
Phase AB §AB.1

Defines the GeologicalReport and all sub-structures.

CONSTITUTIONAL RULES:
  Rule 1: A report is generated AFTER canonical freeze. It never triggers
          reprocessing, rescoring, or tier reassignment.
  Rule 2: Every section must carry a citations list — the exact canonical
          field paths that grounded the interpretive content.
  Rule 3: report_version, prompt_version, grounding_snapshot_hash,
          calibration_version_id, and mineral_system_logic_version are
          ALL MANDATORY. Reports without full audit fields are invalid.
  Rule 4: Forbidden claims are tracked at section level. If the LLM
          output was filtered for a forbidden claim, the section carries
          a redaction_notes field explaining what was removed and why.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReportAudience(str, Enum):
    SOVEREIGN_GOVERNMENT = "sovereign_government"
    OPERATOR_TECHNICAL   = "operator_technical"
    INVESTOR_EXECUTIVE   = "investor_executive"


class ReportStatus(str, Enum):
    DRAFT     = "draft"
    FINAL     = "final"
    REDACTED  = "redacted"    # one or more sections had forbidden claims removed


class SectionType(str, Enum):
    OBSERVED_CANONICAL_OUTPUTS  = "observed_canonical_outputs"
    GEOLOGICAL_INTERPRETATION   = "geological_interpretation"
    UNCERTAINTY_AND_LIMITATIONS = "uncertainty_and_limitations"
    RECOMMENDED_NEXT_STEPS      = "recommended_next_steps"


# Forbidden claim categories — checked during grounding
FORBIDDEN_CLAIM_TYPES = {
    "invented_score":        "Invented score not present in canonical record",
    "tier_reassignment":     "Tier reassignment not matching stored cell.tier",
    "threshold_derivation":  "Threshold derived outside calibration system",
    "deposit_certainty":     "Unsupported deposit certainty claim",
    "resource_statement":    "Unsupported mineral resource quantity statement",
    "probability_inflation": "Inflated probability not matching stored commodity_probs",
}


@dataclass(frozen=True)
class CitationRef:
    """
    A traceable reference from an interpretive claim to a canonical field.

    field_path: dot-notation path to the canonical field
                e.g. "scan.display_acif_score", "cell.tier", "cell.physics_residual"
    stored_value: the verbatim value from that field at report generation time
    relevance: brief note on why this field grounds the claim (1 sentence max)
    """
    field_path:   str
    stored_value: str       # always string — verbatim or formatted canonical value
    relevance:    str


@dataclass(frozen=True)
class ReportSection:
    """
    A single section of a geological report.

    content:         The LLM-generated interpretive text, post-grounding validation.
    citations:       Every canonical field that contributed to this section's content.
    section_type:    One of the 4 mandatory section types.
    redaction_notes: If forbidden claims were found and removed, a description.
                     None if section passed grounding check cleanly.
    """
    section_type:    SectionType
    title:           str
    content:         str
    citations:       tuple[CitationRef, ...]
    redaction_notes: Optional[str] = None

    @property
    def was_redacted(self) -> bool:
        return self.redaction_notes is not None


@dataclass(frozen=True)
class ReportAuditTrail:
    """
    Full audit trail for report generation.
    Every field is mandatory — reports without complete audit trails are invalid.
    """
    report_version:              str    # semantic version of report engine
    prompt_version:              str    # version of the prompt template used
    grounding_snapshot_hash:     str    # SHA-256 of the full grounding input bundle
    calibration_version_id:      str    # from CalibrationScanTrace
    msl_id:                      str    # unique identifier for the MSL entry used
    mineral_system_logic_version: str   # version of the mineral-system logic registry
    generated_at:                str    # ISO 8601 UTC
    generated_by:                str    # user or service ID
    llm_model_hint:              str    # which model class was used (not exposing internals)


@dataclass(frozen=True)
class GeologicalReport:
    """
    A complete geological report generated from frozen canonical data.

    PROOF: report_id and scan_id link this report to exactly one CanonicalScan.
    All sections carry citations. Audit trail is mandatory.
    This record is immutable after creation.
    """
    report_id:   str
    scan_id:     str
    commodity:   str
    audience:    ReportAudience
    status:      ReportStatus
    sections:    tuple[ReportSection, ...]   # always 4 sections in mandatory order
    audit:       ReportAuditTrail
    summary:     str      # ≤ 3 sentences for UI card display

    def section(self, section_type: SectionType) -> Optional[ReportSection]:
        for s in self.sections:
            if s.section_type == section_type:
                return s
        return None

    @property
    def all_citations(self) -> list[CitationRef]:
        """All citations across all sections — for complete field audit."""
        result = []
        for s in self.sections:
            result.extend(s.citations)
        return result

    @property
    def has_redactions(self) -> bool:
        return any(s.was_redacted for s in self.sections)

    def assert_audit_complete(self) -> None:
        """Hard guard: all audit fields must be non-empty."""
        a = self.audit
        missing = [
            f for f, v in {
                "report_version":               a.report_version,
                "prompt_version":               a.prompt_version,
                "grounding_snapshot_hash":      a.grounding_snapshot_hash,
                "calibration_version_id":       a.calibration_version_id,
                "mineral_system_logic_version": a.mineral_system_logic_version,
            }.items() if not v
        ]
        if missing:
            raise ValueError(
                f"Report {self.report_id}: audit trail incomplete. "
                f"Missing: {missing}"
            )


def new_report_id() -> str:
    import uuid
    return f"rpt-{str(uuid.uuid4())}"