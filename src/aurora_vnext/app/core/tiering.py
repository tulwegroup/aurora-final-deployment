"""
Aurora OSI vNext — Tiering Engine
Phase J §J.2 | Phase B §12

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
TIER DEFINITIONS (§12.1)
═══════════════════════════════════════════════════════════════════

  Tier 1 — CONFIRMED:   ACIF_i ≥ τ₁              (highest confidence)
  Tier 2 — HIGH:        τ₂ ≤ ACIF_i < τ₁
  Tier 3 — MODERATE:    τ₃ ≤ ACIF_i < τ₂
  Tier 4 — LOW:         τ₄ ≤ ACIF_i < τ₃
  Tier 5 — BACKGROUND:  ACIF_i < τ₄              (noise floor)

  Thresholds must satisfy: τ₁ > τ₂ > τ₃ > τ₄ > 0.

═══════════════════════════════════════════════════════════════════
THREE THRESHOLD POLICY TYPES (§12.2)
═══════════════════════════════════════════════════════════════════

  FROZEN:      τ values fixed at scan start from version registry.
               Most reproducible — replays use identical thresholds.

  PERCENTILE:  τ values derived from ACIF distribution of THIS scan.
               e.g. τ₁ = 95th percentile, τ₂ = 80th, etc.
               Adapts to each AOI's dynamic range.

  OVERRIDE:    Admin-provided τ values (requires audit record).
               Must be stored with override_reason in ThresholdPolicy.

  The tiering engine accepts any ThresholdSet — policy selection is external.

No imports from core/scoring, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Tier(str, Enum):
    TIER_1_CONFIRMED  = "TIER_1"   # ≥ τ₁
    TIER_2_HIGH       = "TIER_2"   # τ₂ ≤ x < τ₁
    TIER_3_MODERATE   = "TIER_3"   # τ₃ ≤ x < τ₂
    TIER_4_LOW        = "TIER_4"   # τ₄ ≤ x < τ₃
    TIER_5_BACKGROUND = "TIER_5"   # < τ₄


class ThresholdPolicyType(str, Enum):
    FROZEN     = "frozen"
    PERCENTILE = "percentile"
    OVERRIDE   = "override"


@dataclass(frozen=True)
class ThresholdSet:
    """
    A complete set of four tier thresholds for one scan.

    Invariant: τ₁ > τ₂ > τ₃ > τ₄ > 0.
    Validated on construction — any violation raises ValueError.

    Fields:
        tau_1:          Tier 1 lower bound (CONFIRMED)
        tau_2:          Tier 2 lower bound (HIGH)
        tau_3:          Tier 3 lower bound (MODERATE)
        tau_4:          Tier 4 lower bound (LOW); below = BACKGROUND
        policy_type:    FROZEN | PERCENTILE | OVERRIDE
        source_version: Version string of the threshold source
        override_reason: Required when policy_type=OVERRIDE
    """
    tau_1: float
    tau_2: float
    tau_3: float
    tau_4: float
    policy_type: ThresholdPolicyType
    source_version: str
    override_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_thresholds(self.tau_1, self.tau_2, self.tau_3, self.tau_4)
        if self.policy_type == ThresholdPolicyType.OVERRIDE and not self.override_reason:
            raise ValueError("OVERRIDE threshold policy requires override_reason.")


def _validate_thresholds(
    tau_1: float,
    tau_2: float,
    tau_3: float,
    tau_4: float,
) -> None:
    """
    Enforce the constitutional threshold ordering invariant: τ₁ > τ₂ > τ₃ > τ₄ > 0.

    Raises:
        ValueError: If any threshold condition is violated.
    """
    if not (tau_1 > tau_2 > tau_3 > tau_4 > 0.0):
        raise ValueError(
            f"Threshold ordering violated: τ₁={tau_1} > τ₂={tau_2} > "
            f"τ₃={tau_3} > τ₄={tau_4} > 0 must all hold. "
            f"Constitutional rule: τ₁ > τ₂ > τ₃ > τ₄ > 0."
        )
    if tau_1 > 1.0:
        raise ValueError(f"τ₁={tau_1} exceeds 1.0 — ACIF is bounded to [0, 1].")


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
        Tier enum value.
    """
    if not (0.0 <= acif_score <= 1.0):
        raise ValueError(f"ACIF score must be in [0, 1], got {acif_score}")

    if acif_score >= thresholds.tau_1:
        return Tier.TIER_1_CONFIRMED
    if acif_score >= thresholds.tau_2:
        return Tier.TIER_2_HIGH
    if acif_score >= thresholds.tau_3:
        return Tier.TIER_3_MODERATE
    if acif_score >= thresholds.tau_4:
        return Tier.TIER_4_LOW
    return Tier.TIER_5_BACKGROUND


# ---------------------------------------------------------------------------
# §12.3 — Percentile-derived threshold computation
# ---------------------------------------------------------------------------

def compute_percentile_thresholds(
    acif_scores: list[float],
    p1: float = 95.0,
    p2: float = 80.0,
    p3: float = 60.0,
    p4: float = 40.0,
    source_version: str = "percentile",
) -> ThresholdSet:
    """
    §12.3 — Derive tier thresholds from the ACIF score distribution.

    Percentiles p1 > p2 > p3 > p4 are computed from the scan's ACIF distribution.
    Ensures thresholds adapt to the AOI's dynamic range.

    After percentile computation, the ordering invariant is enforced.
    If percentiles are degenerate (e.g., too many zero scores), a small
    epsilon is added to satisfy strict ordering.

    Args:
        acif_scores:    All ACIF cell scores for this scan.
        p1..p4:         Percentile values (must satisfy p1 > p2 > p3 > p4).
        source_version: Tag for ThresholdSet.source_version.

    Returns:
        ThresholdSet derived from this scan's distribution.

    Raises:
        ValueError: If fewer than 4 scores are provided.
    """
    if len(acif_scores) < 4:
        raise ValueError("At least 4 ACIF scores required for percentile thresholds.")
    if not (p1 > p2 > p3 > p4 >= 0):
        raise ValueError(f"Percentile ordering violated: {p1} > {p2} > {p3} > {p4} required.")

    n = len(acif_scores)
    sorted_scores = sorted(acif_scores)

    def _pct(p: float) -> float:
        idx = max(0, min(n - 1, int(round(p / 100.0 * n)) - 1))
        return sorted_scores[idx]

    tau_1 = _pct(p1)
    tau_2 = _pct(p2)
    tau_3 = _pct(p3)
    tau_4 = _pct(p4)

    # Repair degenerate ordering with tiny separations (ε = 1e-6)
    eps = 1e-6
    tau_4 = max(eps, tau_4)
    tau_3 = max(tau_4 + eps, tau_3)
    tau_2 = max(tau_3 + eps, tau_2)
    tau_1 = max(tau_2 + eps, tau_1)
    tau_1 = min(1.0, tau_1)

    return ThresholdSet(
        tau_1=tau_1,
        tau_2=tau_2,
        tau_3=tau_3,
        tau_4=tau_4,
        policy_type=ThresholdPolicyType.PERCENTILE,
        source_version=source_version,
    )


# ---------------------------------------------------------------------------
# Batch tier assignment + distribution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierCounts:
    """Distribution of tiers across all cells in a scan."""
    tier_1: int = 0
    tier_2: int = 0
    tier_3: int = 0
    tier_4: int = 0
    tier_5: int = 0
    total: int = 0

    def as_fractions(self) -> dict[str, float]:
        if self.total == 0:
            return {t.value: 0.0 for t in Tier}
        return {
            Tier.TIER_1_CONFIRMED.value:  self.tier_1 / self.total,
            Tier.TIER_2_HIGH.value:       self.tier_2 / self.total,
            Tier.TIER_3_MODERATE.value:   self.tier_3 / self.total,
            Tier.TIER_4_LOW.value:        self.tier_4 / self.total,
            Tier.TIER_5_BACKGROUND.value: self.tier_5 / self.total,
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
        tier_1=counts[Tier.TIER_1_CONFIRMED],
        tier_2=counts[Tier.TIER_2_HIGH],
        tier_3=counts[Tier.TIER_3_MODERATE],
        tier_4=counts[Tier.TIER_4_LOW],
        tier_5=counts[Tier.TIER_5_BACKGROUND],
        total=len(tier_list),
    )