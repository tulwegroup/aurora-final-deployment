"""
Aurora OSI vNext — Report Engine
Phase AB §AB.5

Orchestrates geological report generation from frozen canonical data.

Flow:
  1. Receive scan_id + audience from caller
  2. Fetch CanonicalScan + ScanCell[] + CalibrationScanTrace from storage
  3. Look up MineralSystemEntry from registry
  4. Assemble GroundingBundle (grounding_snapshot_hash computed here)
  5. For each of 4 mandatory sections:
     a. Build section prompt via report_templates
     b. Call LLM via integration
     c. Check output for forbidden claims via report_grounding
     d. Build ReportSection with citations
  6. Assemble GeologicalReport with full audit trail
  7. Call assert_audit_complete() — hard guard

CONSTITUTIONAL RULES:
  Rule 1: Fetches are read-only from storage. No write to CanonicalScan.
  Rule 2: LLM is called with a grounding prompt ONLY — it receives canonical
          field values and approved mineral-system logic.
  Rule 3: LLM output is passed through check_for_forbidden_claims() before
          any section is constructed.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.report_model import (
    GeologicalReport, ReportSection, ReportAuditTrail,
    ReportAudience, ReportStatus, SectionType, CitationRef,
    new_report_id,
)
from app.services.report_grounding import (
    assemble_grounding_bundle, check_for_forbidden_claims, GroundingBundle,
)
from app.services.report_templates import (
    build_section_prompt, format_bundle_vars, TEMPLATE_VERSION,
)
from app.services.mineral_system_logic import get_entry, registry_version
from app.config.observability import get_logger

logger = get_logger(__name__)

REPORT_ENGINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Storage adapter protocol (replaced by real adapter in production)
# ---------------------------------------------------------------------------

class ReportStorageAdapter:
    """Protocol for reading canonical scan data. Production: injected from storage layer."""

    def fetch_canonical_scan(self, scan_id: str) -> Optional[dict]:
        """Return canonical scan summary dict or None."""
        raise NotImplementedError

    def fetch_scan_cells(self, scan_id: str, limit: int = 1000) -> list[dict]:
        """Return list of ScanCell dicts."""
        raise NotImplementedError

    def fetch_calibration_trace(self, scan_id: str) -> Optional[dict]:
        """Return CalibrationScanTrace dict or None."""
        raise NotImplementedError

    def fetch_approved_gt_context(self, scan_id: str, commodity: str) -> list[dict]:
        """Return list of approved ground-truth record summaries for this commodity."""
        return []

    def save_report(self, report: GeologicalReport) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# LLM caller (uses Aurora integration in production; stub-able for tests)
# ---------------------------------------------------------------------------

class LLMCaller:
    """
    Calls the LLM with a grounded prompt.
    In production this invokes base44.integrations.Core.InvokeLLM.
    In tests replaced with a stub.
    """
    async def call(self, prompt: str, audience: ReportAudience) -> str:
        raise NotImplementedError


class StubLLMCaller(LLMCaller):
    """
    Test stub — returns a minimal grounded response with canonical field citations.
    Used in unit tests and CI to avoid live LLM calls.
    """
    async def call(self, prompt: str, audience: ReportAudience) -> str:
        return (
            "Based on the canonical scan data provided, the following observations are noted. "
            "[FIELD: scan.display_acif_score = \"stored_value\"] "
            "The system status is as recorded in the canonical record. "
            "[FIELD: scan.system_status = \"stored_value\"] "
            "Interpretation is grounded solely in the approved mineral system logic. "
            "No resource statement is made. No tier reclassification is performed."
        )


# ---------------------------------------------------------------------------
# Citation extractor
# ---------------------------------------------------------------------------

def extract_citations(
    text: str, bundle: GroundingBundle
) -> tuple[CitationRef, ...]:
    """
    Extract [FIELD: field.path = "value"] citations from LLM output.
    Falls back to auto-citing the top canonical fields from the grounding bundle.
    """
    import re
    citations: list[CitationRef] = []

    # Pattern: [FIELD: field.path = "value"] or [FIELD: field.path = value]
    pattern = re.compile(r'\[FIELD:\s*([^\]=]+?)\s*=\s*"?([^"\]]+)"?\]')
    for match in pattern.finditer(text):
        field_path  = match.group(1).strip()
        stored_val  = match.group(2).strip()
        citations.append(CitationRef(
            field_path   = field_path,
            stored_value = stored_val,
            relevance    = "Cited by report engine from LLM output",
        ))

    # Always auto-cite the top-level canonical fields
    if bundle.acif_score:
        citations.append(CitationRef(
            field_path   = "scan.display_acif_score",
            stored_value = bundle.acif_score,
            relevance    = "Primary ACIF score — grounding anchor for all interpretation",
        ))
    if bundle.system_status:
        citations.append(CitationRef(
            field_path   = "scan.system_status",
            stored_value = bundle.system_status,
            relevance    = "Stored system status from canonical freeze",
        ))
    for tier, count in bundle.tier_counts.items():
        citations.append(CitationRef(
            field_path   = f"scan.tier_counts.{tier}",
            stored_value = str(count),
            relevance    = f"Stored tier count for {tier}",
        ))

    # Deduplicate by field_path
    seen: set[str] = set()
    deduped: list[CitationRef] = []
    for c in citations:
        if c.field_path not in seen:
            seen.add(c.field_path)
            deduped.append(c)

    return tuple(deduped)


# ---------------------------------------------------------------------------
# Report Engine
# ---------------------------------------------------------------------------

class ReportEngine:
    """
    Orchestrates geological report generation.

    Usage:
        engine = ReportEngine(storage_adapter, llm_caller)
        report = await engine.generate(scan_id, audience)
    """

    def __init__(self, storage: ReportStorageAdapter, llm: LLMCaller):
        self._storage = storage
        self._llm     = llm

    async def generate(
        self,
        scan_id:    str,
        audience:   ReportAudience,
        actor_id:   str = "system",
    ) -> GeologicalReport:
        """
        Generate a GeologicalReport for the given scan_id and audience.
        Raises ValueError if canonical data is missing or audit trail is incomplete.
        """
        from datetime import datetime

        # ── 1. Fetch canonical data ──
        scan = self._storage.fetch_canonical_scan(scan_id)
        if not scan:
            raise ValueError(f"Canonical scan not found: {scan_id}")

        commodity = scan.get("commodity", "unknown")
        cal_trace = self._storage.fetch_calibration_trace(scan_id)
        cal_version = (cal_trace or {}).get("calibration_version_id", "unknown")

        gt_context = self._storage.fetch_approved_gt_context(scan_id, commodity)

        # ── 2. Look up mineral system logic ──
        msl = get_entry(commodity)
        if not msl:
            raise ValueError(
                f"No approved mineral system logic for commodity {commodity!r}. "
                f"Available: {get_entry.__module__}.list_commodities()"
            )

        # ── 3. Assemble grounding bundle ──
        bundle = assemble_grounding_bundle(
            scan_id              = scan_id,
            commodity            = commodity,
            acif_score           = scan.get("display_acif_score"),
            tier_counts          = scan.get("tier_counts", {}),
            tier_thresholds      = scan.get("tier_thresholds", {}),
            system_status        = scan.get("system_status", "UNKNOWN"),
            veto_explanations    = scan.get("veto_explanations", []),
            component_scores     = scan.get("component_scores", {}),
            calibration_version  = cal_version,
            scan_date            = scan.get("completed_at", "unknown"),
            pipeline_version     = scan.get("pipeline_version", "unknown"),
            total_cells          = scan.get("total_cells", 0),
            cells_above_tier1    = scan.get("tier_counts", {}).get("TIER_1", 0),
            mineral_system_entry = msl,
            ground_truth_context = gt_context or None,
        )
        grounding_hash = bundle.snapshot_hash()
        bundle_vars    = format_bundle_vars(bundle)

        logger.info("report_generation_started", extra={
            "scan_id": scan_id, "audience": audience.value,
            "grounding_hash": grounding_hash, "commodity": commodity,
        })

        # ── 4. Generate each section ──
        sections: list[ReportSection] = []
        section_order = [
            SectionType.OBSERVED_CANONICAL_OUTPUTS,
            SectionType.GEOLOGICAL_INTERPRETATION,
            SectionType.UNCERTAINTY_AND_LIMITATIONS,
            SectionType.RECOMMENDED_NEXT_STEPS,
        ]
        section_titles = {
            SectionType.OBSERVED_CANONICAL_OUTPUTS:  "1. Observed Canonical Outputs",
            SectionType.GEOLOGICAL_INTERPRETATION:   "2. Geological Interpretation",
            SectionType.UNCERTAINTY_AND_LIMITATIONS: "3. Uncertainty and Limitations",
            SectionType.RECOMMENDED_NEXT_STEPS:      "4. Recommended Next Steps",
        }

        has_any_redaction = False

        for section_type in section_order:
            prompt = build_section_prompt(section_type, audience, bundle_vars)
            raw_output = await self._llm.call(prompt, audience)

            # ── 5. Grounding check ──
            check = check_for_forbidden_claims(raw_output)
            if not check.passed:
                has_any_redaction = True
                logger.info("report_section_redacted", extra={
                    "scan_id": scan_id, "section": section_type.value,
                    "violations": len(check.detected_violations),
                })

            citations = extract_citations(check.clean_text, bundle)

            sections.append(ReportSection(
                section_type    = section_type,
                title           = section_titles[section_type],
                content         = check.clean_text,
                citations       = citations,
                redaction_notes = check.redaction_notes,
            ))

        # ── 6. Build summary ──
        tier1 = bundle.tier_counts.get("TIER_1", 0)
        total = bundle.total_cells or 1
        pct   = round((tier1 / total) * 100, 1) if total > 0 else 0.0
        summary = (
            f"Aurora scan for {commodity} ({scan_id[:8]}…) completed with system status "
            f"{bundle.system_status}. "
            f"ACIF score: {bundle.acif_score or '—'}. "
            f"{tier1} Tier 1 cells ({pct}% of total). "
            f"Interpretation grounded on {msl.deposit_models[0]}."
        )

        # ── 7. Assemble report ──
        audit = ReportAuditTrail(
            report_version              = REPORT_ENGINE_VERSION,
            prompt_version              = TEMPLATE_VERSION,
            grounding_snapshot_hash     = grounding_hash,
            calibration_version_id      = cal_version,
            mineral_system_logic_version= registry_version(),
            generated_at                = datetime.utcnow().isoformat(),
            generated_by                = actor_id,
            llm_model_hint              = "aurora-interpretation-v1",
        )

        report = GeologicalReport(
            report_id = new_report_id(),
            scan_id   = scan_id,
            commodity = commodity,
            audience  = audience,
            status    = ReportStatus.REDACTED if has_any_redaction else ReportStatus.FINAL,
            sections  = tuple(sections),
            audit     = audit,
            summary   = summary,
        )

        # Hard guard — will raise if any audit field is empty
        report.assert_audit_complete()

        self._storage.save_report(report)
        logger.info("report_generated", extra={
            "report_id": report.report_id, "scan_id": scan_id,
            "status": report.status.value, "redacted": has_any_redaction,
        })

        return report