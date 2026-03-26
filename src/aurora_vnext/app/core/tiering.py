"""
Aurora OSI vNext — Tiering Engine
Phase J v1.1 §J.2 | Phase B §12

CONSTITUTIONAL RULES:
  1. This is the SOLE location for tier assignment logic.
  2. NO threshold values are hard-coded in this file.
  3. Tiering is a PURE FUNCTION of (acif_score, ThresholdSet).
  4. The tiering engine does NOT decide which ThresholdSet is active —
     that policy decision is made by the scan pipeline (Phase L).
  5. Thresholds frozen at scan completion are stored in:
     canonical_scans.tier_thresholds_used (ThresholdPolicy model).
  6. GeoJSON colouring reads tier_thresholds_used — never recomputes.

═══════════════════════════════════════════════════════════════════
APPROVED TIER VOCABULARY (§12.1) — CONSTITUTIONAL
═══════════════════════════════════════════════════════════════════

  TIER_1:  ACIF_i ≥ t1              (highest confidence)
  TIER_2:  t2 ≤ ACIF_i < t1
  TIER_3:  t3 ≤ ACIF_i < t2
  BELOW:   ACIF_i < t3              (below detection threshold)

  Thresholds must satisfy: t1 > t2 > t3 > 0.

  CONSTITUTIONAL INVARIANT: No other tier names, tier numbers, or
  threshold symbols (τ₄, TIER_4, TIER_5, subtiers) may be introduced
  without a formal constitutional amendment.

═══════════════════════════════════════════════════════════════════
THREE THRESHOLD POLICY TYPES (§12.2)
═══════════════════════════════════════════════════════════════════

  FROZEN:      t values fixed at scan start from version registry.
               Most reproducible — replays use identical thresholds.

  PERCENTILE:  t values derived from ACIF distribution of THIS scan.
               Adapts to each AOI's dynamic range.

  OVERRIDE:    Admin-provided t values (requires audit record).
               Must be stored with override_reason in ThresholdPolicy.

  The tiering engine accepts any ThresholdSet — policy selection is external.

No imports from core/scoring, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Tier(str, Enum):
    TIER_1 = "TIER_1"   # ≥ t1
    TIER_2 = "TIER_2"   # t2 ≤ x < t1
    TIER_3 = "TIER_3"   # t3 ≤ x < t2
    BELOW  = "BELOW"    # < t3


class ThresholdPolicyType(str, Enum):
    FROZEN     = "frozen"
    PERCENTILE = "percentile"
    OVERRIDE   = "override"


@dataclass(frozen=True)
class ThresholdSet:
    """
    A complete set of three tier thresholds for one scan.

    Constitutional invariant: t1 > t2 > t3 > 0.
    Validated on construction — any violation raises ValueError.

    Fields:
        t1:             Tier 1 lower bound (highest confidence)
        t2:             Tier 2 lower bound
        t3:             Tier 3 lower bound; below = BELOW
        policy_type:    FROZEN | PERCENTILE | OVERRIDE
        source_version: Version string of the threshold source
        override_reason: Required when policy_type=OVERRIDE
    """
    t1: float
    t2: float
    t3: float
    policy_type: ThresholdPolicyType
    source_version: str
    override_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_thresholds(self.t1, self.t2, self.t3)
        if self.policy_type == ThresholdPolicyType.OVERRIDE and not self.override_reason:
            raise ValueError("OVERRIDE threshold policy requires override_reason.")


def _validate_thresholds(t1: float, t2: float, t3: float) -> None:
    """
    Enforce the constitutional threshold ordering invariant: t1 > t2 > t3 > 0.

    Raises:
        ValueError: If any threshold condition is violated.
    """
    if not (t1 > t2 > t3 > 0.0):
        raise ValueError(
            f"Threshold ordering violated: t1={t1} > t2={t2} > t3={t3} > 0 must all hold. "
            f"Constitutional rule: t1 > t2 > t3 > 0."
        )
    if t1 > 1.0:
        raise ValueError(f"t1={t1} exceeds 1.0 — ACIF is bounded to [0, 1].")


# ---------------------------------------------------------------------------
# §12.1 — Per-cell tier assignment (pure function)
# ---------------------------------------------------------------------------

def assign_tier(acif_score: float, thresholds: ThresholdSet) -> Tier:
    """
    §12.1 — Assign a single tier to one ACIF score.

    Pure function — no side effects, no state.
    The same (acif_score, thresholds) always produces the same Tier.

    Args:
        acif_score:  ACIF_i ∈ [0, 1]
        thresholds:  ThresholdSet with validated ordering

    Returns:
        Tier enum value: TIER_1 | TIER_2 | TIER_3 | BELOW
    """
    if not (0.0 <= acif_score <= 1.0):
        raise ValueError(f"ACIF score must be in [0, 1], got {acif_score}")

    if acif_score >= thresholds.t1:
        return Tier.TIER_1
    if acif_score >= thresholds.t2:
        return Tier.TIER_2
    if acif_score >= thresholds.t3:
        return Tier.TIER_3
    return Tier.BELOW


# ---------------------------------------------------------------------------
# §12.3 — Percentile-derived threshold computation
# ---------------------------------------------------------------------------

def compute_percentile_thresholds(
    acif_scores: list[float],
    p1: float = 90.0,
    p2: float = 70.0,
    p3: float = 40.0,
    source_version: str = "percentile",
) -> ThresholdSet:
    """
    §12.3 — Derive tier thresholds from the ACIF score distribution.

    Percentiles p1 > p2 > p3 are computed from the scan's ACIF distribution.
    After percentile computation, the ordering invariant is enforced.
    If percentiles are degenerate (e.g., too many zero scores), a small
    epsilon is added to satisfy strict ordering.

    Args:
        acif_scores:    All ACIF cell scores for this scan.
        p1, p2, p3:     Percentile values (must satisfy p1 > p2 > p3).
        source_version: Tag for ThresholdSet.source_version.

    Returns:
        ThresholdSet derived from this scan's distribution.

    Raises:
        ValueError: If fewer than 3 scores are provided.
    """
    if len(acif_scores) < 3:
        raise ValueError("At least 3 ACIF scores required for percentile thresholds.")
    if not (p1 > p2 > p3 >= 0):
        raise ValueError(f"Percentile ordering violated: {p1} > {p2} > {p3} required.")

    n = len(acif_scores)
    sorted_scores = sorted(acif_scores)

    def _pct(p: float) -> float:
        idx = max(0, min(n - 1, int(round(p / 100.0 * n)) - 1))
        return sorted_scores[idx]

    t1 = _pct(p1)
    t2 = _pct(p2)
    t3 = _pct(p3)

    # Repair degenerate ordering with tiny separations (ε = 1e-6)
    eps = 1e-6
    t3 = max(eps, t3)
    t2 = max(t3 + eps, t2)
    t1 = max(t2 + eps, t1)
    t1 = min(1.0, t1)

    return ThresholdSet(
        t1=t1, t2=t2, t3=t3,
        policy_type=ThresholdPolicyType.PERCENTILE,
        source_version=source_version,
    )


# ---------------------------------------------------------------------------
# Batch tier assignment + distribution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierCounts:
    """Distribution of tiers across all cells in a scan. Approved canonical model."""
    tier_1: int = 0
    tier_2: int = 0
    tier_3: int = 0
    below: int  = 0
    total: int  = 0

    def as_fractions(self) -> dict[str, float]:
        if self.total == 0:
            return {t.value: 0.0 for t in Tier}
        return {
            Tier.TIER_1.value: self.tier_1 / self.total,
            Tier.TIER_2.value: self.tier_2 / self.total,
            Tier.TIER_3.value: self.tier_3 / self.total,
            Tier.BELOW.value:  self.below  / self.total,
        }


def assign_tiers_batch(
    acif_scores: list[float],
    thresholds: ThresholdSet,
) -> tuple[list[Tier], TierCounts]:
    """
    Assign tiers to all cells in one scan and return distribution counts.

    Returns:
        (tier_list, TierCounts)
    """
    tier_list = [assign_tier(s, thresholds) for s in acif_scores]
    counts = {t: 0 for t in Tier}
    for t in tier_list:
        counts[t] += 1

    return tier_list, TierCounts(
        tier_1=counts[Tier.TIER_1],
        tier_2=counts[Tier.TIER_2],
        tier_3=counts[Tier.TIER_3],
        below=counts[Tier.BELOW],
        total=len(tier_list),
    )