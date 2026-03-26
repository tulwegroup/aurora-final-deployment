"""
Aurora OSI vNext — Report Grounding Service
Phase AB §AB.3

Assembles the grounding bundle for the report engine.

Responsibilities:
  1. Assemble GroundingBundle from CanonicalScan + ScanCell[] + CalibrationScanTrace
     + version_registry + MineralSystemEntry + optional ground-truth context.
  2. Hash the full bundle (grounding_snapshot_hash) for audit immutability.
  3. Validate the LLM output for forbidden claims before section construction.

GROUNDING RULES — what the LLM receives:
  PERMITTED:
    - canonical scores and component scores (verbatim stored values)
    - stored tier counts and tier thresholds (verbatim)
    - veto explanations (verbatim stored strings)
    - approved mineral-system logic (from registry)
    - ground-truth provenance context (approved records only)

  FORBIDDEN (never injected into prompt, and checked in output):
    - raw feature tensor values (x_spec_*, x_grav_*, etc.)
    - model weights, lambda values, calibration math internals
    - any instruction to produce a new score or threshold
    - any instruction to classify the deposit as proven/probable resource

CONSTITUTIONAL RULE: This module never calls any function from core/*.
All values passed are pre-assembled strings and floats from stored records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from app.services.mineral_system_logic import MineralSystemEntry
from app.models.report_model import FORBIDDEN_CLAIM_TYPES


@dataclass
class GroundingBundle:
    """
    The complete grounding context for one report generation.

    All fields are pre-formatted strings or simple dicts — no live API calls,
    no scoring functions. Assembled once, hashed once.
    """
    scan_id:                    str
    commodity:                  str
    acif_score:                 Optional[str]    # verbatim formatted string e.g. "0.7432"
    tier_counts:                dict             # {"TIER_1": n, "TIER_2": n, ...}
    tier_thresholds:            dict             # stored thresholds verbatim
    system_status:              str              # e.g. "PASS_CONFIRMED"
    veto_summary:               list[str]        # veto explanation strings verbatim
    component_scores:           dict             # {component_name: score_str}
    calibration_version_id:     str
    mineral_system_logic:       MineralSystemEntry
    ground_truth_context:       Optional[list[dict]]  # approved GT records summary only
    scan_date:                  str
    pipeline_version:           str
    total_cells:                int
    cells_above_tier1:          int

    def to_serialisable(self) -> dict:
        """Produce a JSON-serialisable dict for hashing."""
        msl = self.mineral_system_logic
        return {
            "scan_id":              self.scan_id,
            "commodity":            self.commodity,
            "acif_score":           self.acif_score,
            "tier_counts":          self.tier_counts,
            "tier_thresholds":      self.tier_thresholds,
            "system_status":        self.system_status,
            "veto_summary":         self.veto_summary,
            "component_scores":     self.component_scores,
            "calibration_version":  self.calibration_version_id,
            "mineral_system_logic": {
                "commodity":             msl.commodity,
                "version":               msl.version,
                "deposit_models":        list(msl.deposit_models),
                "expected_drivers":      list(msl.expected_drivers),
                "key_observables":       list(msl.key_observables),
                "geophysical_signature": msl.geophysical_signature,
                "uncertainty_note":      msl.uncertainty_note,
                "known_false_positives": list(msl.known_false_positives),
            },
            "ground_truth_context": self.ground_truth_context,
            "scan_date":            self.scan_date,
            "pipeline_version":     self.pipeline_version,
            "total_cells":          self.total_cells,
            "cells_above_tier1":    self.cells_above_tier1,
        }

    def snapshot_hash(self) -> str:
        """
        SHA-256 of the canonical JSON-serialised grounding bundle.
        Deterministic: sort_keys=True. Any change to grounding inputs → different hash.
        """
        payload = json.dumps(self.to_serialisable(), sort_keys=True,
                             default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Forbidden claim detector
# ---------------------------------------------------------------------------

# Patterns that suggest LLM invented claims not grounded in canonical fields
_FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    # (pattern, forbidden_claim_type)
    ("probability of ",     "invented_score"),
    ("certainty of ",       "invented_score"),
    ("score of ",           "invented_score"),
    ("i estimate ",         "invented_score"),
    ("we estimate ",        "invented_score"),
    ("reclassify ",         "tier_reassignment"),
    ("reclassified as ",    "tier_reassignment"),
    ("should be tier",      "tier_reassignment"),
    ("move to tier",        "tier_reassignment"),
    ("threshold of ",       "threshold_derivation"),
    ("new threshold",       "threshold_derivation"),
    ("cut-off of ",         "threshold_derivation"),
    ("proven deposit",      "deposit_certainty"),
    ("confirmed deposit",   "deposit_certainty"),
    ("definite deposit",    "deposit_certainty"),
    ("resource of ",        "resource_statement"),
    ("tonnes of ",          "resource_statement"),
    ("mt of ",              "resource_statement"),
    ("million ounces",      "resource_statement"),
    ("moz ",                "resource_statement"),
    ("grade of ",           "resource_statement"),
    ("inflated probability","probability_inflation"),
]


class ForbiddenClaimError(ValueError):
    """Raised when a forbidden claim is detected in LLM output."""


@dataclass
class GroundingCheckResult:
    passed:              bool
    detected_violations: list[dict]    # [{"type": ..., "description": ..., "matched_phrase": ...}]
    clean_text:          str           # text with violations replaced by [REDACTED: reason]
    redaction_notes:     Optional[str]


def check_for_forbidden_claims(text: str) -> GroundingCheckResult:
    """
    Scan LLM output for forbidden claim patterns.
    Returns a GroundingCheckResult — never raises.
    Violations are redacted in clean_text.
    """
    violations: list[dict] = []
    clean = text

    lower = text.lower()
    for pattern, claim_type in _FORBIDDEN_PATTERNS:
        if pattern in lower:
            # Find the sentence containing the pattern
            start = lower.find(pattern)
            sentence_start = max(0, lower.rfind(".", 0, start) + 1)
            sentence_end   = lower.find(".", start)
            sentence_end   = len(text) if sentence_end == -1 else sentence_end + 1
            matched_sentence = text[sentence_start:sentence_end].strip()

            violations.append({
                "type":           claim_type,
                "description":    FORBIDDEN_CLAIM_TYPES.get(claim_type, "Forbidden claim"),
                "matched_phrase": pattern,
                "context":        matched_sentence[:200],
            })

    if violations:
        # Redact — replace each violating sentence
        for v in violations:
            reason = v["description"]
            clean = clean.replace(
                v["context"],
                f"[REDACTED: {reason}]",
            )
        redaction_notes = (
            f"{len(violations)} forbidden claim(s) detected and redacted: "
            + ", ".join(sorted({v['type'] for v in violations}))
        )
        return GroundingCheckResult(
            passed=False, detected_violations=violations,
            clean_text=clean, redaction_notes=redaction_notes,
        )

    return GroundingCheckResult(
        passed=True, detected_violations=[],
        clean_text=text, redaction_notes=None,
    )


def assemble_grounding_bundle(
    scan_id:              str,
    commodity:            str,
    acif_score:           Optional[float],
    tier_counts:          dict,
    tier_thresholds:      dict,
    system_status:        str,
    veto_explanations:    list[str],
    component_scores:     dict,
    calibration_version:  str,
    scan_date:            str,
    pipeline_version:     str,
    total_cells:          int,
    cells_above_tier1:    int,
    mineral_system_entry: MineralSystemEntry,
    ground_truth_context: Optional[list[dict]] = None,
) -> GroundingBundle:
    """
    Assemble the grounding bundle from pre-fetched canonical data.
    All values must be fetched from storage before calling this function —
    no storage access occurs here.
    """
    return GroundingBundle(
        scan_id              = scan_id,
        commodity            = commodity,
        acif_score           = f"{acif_score:.6f}" if acif_score is not None else None,
        tier_counts          = tier_counts,
        tier_thresholds      = tier_thresholds,
        system_status        = system_status,
        veto_summary         = veto_explanations,
        component_scores     = {k: f"{v:.6f}" if isinstance(v, float) else str(v)
                                 for k, v in component_scores.items()},
        calibration_version_id  = calibration_version,
        mineral_system_logic    = mineral_system_entry,
        ground_truth_context    = ground_truth_context,
        scan_date               = scan_date,
        pipeline_version        = pipeline_version,
        total_cells             = total_cells,
        cells_above_tier1       = cells_above_tier1,
    )