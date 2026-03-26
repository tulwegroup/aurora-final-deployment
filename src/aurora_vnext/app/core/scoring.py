"""
Aurora OSI vNext — Canonical ACIF Scoring Engine
Phase J §J.1 | Phase B §2, §11

CONSTITUTIONAL RULE: This is the SOLE location for ACIF computation.
No other module, function, API handler, or storage layer may compute,
re-compute, or approximate ACIF values.

═══════════════════════════════════════════════════════════════════
CANONICAL ACIF FORMULATION (§2.1)
═══════════════════════════════════════════════════════════════════

  ACIF_i^(c) = Ẽ_i^(c) × C_i^(c) × Ψ_i × T_i^(c) × Π^(c)(r_i) × (1 − U_i^(c))

  where:
    Ẽ_i^(c)    = clustering-adjusted evidence score        [0, 1]   core/evidence.py
    C_i^(c)    = causal consistency score                  [0, 1]   core/causal.py
    Ψ_i        = physics consistency score                 [0, 1]   core/physics.py
    T_i^(c)    = temporal coherence score                  [0, 1]   core/temporal.py
    Π^(c)(r_i) = province prior probability                [0, 1]   core/priors.py
    (1-U_i)    = certainty factor (1 - total uncertainty)  [0, 1]   core/uncertainty.py

  ACIF_i ∈ [0, 1] always (multiplicative → naturally bounded).

═══════════════════════════════════════════════════════════════════
HARD VETO PROPAGATION (§2.2)
═══════════════════════════════════════════════════════════════════

  If ANY of the following is true, ACIF_i = 0.0 (unconditional):
    • C_i = 0.0 (causal veto fired)
    • Ψ_i = 0.0 (physics veto fired)
    • T_i = 0.0 (temporal veto fired)
    • Π_i = 0.0 (province impossibility veto fired)

  The multiplicative structure enforces this automatically.
  Explicit veto checks are also performed for audit traceability.

═══════════════════════════════════════════════════════════════════
SCAN-LEVEL AGGREGATES (§11)
═══════════════════════════════════════════════════════════════════

  ACIF_mean^(c) = (1/N) × Σ_i ACIF_i^(c)
  ACIF_max^(c)  = max_i ACIF_i^(c)
  ACIF_weighted = Σ_i [ ACIF_i × w_area_i ] / Σ_i w_area_i
    where w_area_i = cell area weight (equal if uniform grid).

═══════════════════════════════════════════════════════════════════
COMPONENT MISSING VALUE POLICY
═══════════════════════════════════════════════════════════════════

  Missing component scores (None) are NOT silently defaulted to any value.
  The caller must provide all six components or explicitly choose a policy:
    - STRICT:    None component → raises MissingComponentError
    - DEGRADED:  None component → treated as 0.5 (moderate — use with explicit warning)

  Default policy: STRICT. Degraded mode is logged in the component trace.

No imports from core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.models.component_scores import ComponentScoreBundle


class MissingComponentPolicy(str, Enum):
    STRICT   = "strict"    # Raise on any None component
    DEGRADED = "degraded"  # Substitute 0.5 with warning


class MissingComponentError(ValueError):
    """Raised when a required ACIF component is None under STRICT policy."""


# ---------------------------------------------------------------------------
# §2.1 — Per-cell ACIF computation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ACIFCellResult:
    """
    Immutable ACIF result for one cell with full component trace.
    Stored in ScanCell at canonical freeze (Phase L).
    """
    cell_id: str
    commodity: str

    # Six input components (as-used values — may differ from raw if DEGRADED policy)
    e_tilde: float
    c_i: float
    psi_i: float
    t_i: float
    pi_i: float
    certainty: float          # (1 - U_i)

    # Final ACIF score
    acif_score: float          # ∈ [0, 1]

    # Veto audit trail
    causal_veto: bool
    physics_veto: bool
    temporal_veto: bool
    province_veto: bool
    any_veto_fired: bool

    # Degraded-mode warnings (empty under STRICT policy)
    degraded_warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def veto_explanation(self) -> str:
        """Human-readable veto explanation for audit trail."""
        reasons = []
        if self.causal_veto:
            reasons.append("CAUSAL_VETO(C_i=0)")
        if self.physics_veto:
            reasons.append("PHYSICS_VETO(Ψ=0)")
        if self.temporal_veto:
            reasons.append("TEMPORAL_VETO(T_i=0)")
        if self.province_veto:
            reasons.append("PROVINCE_VETO(Π=0)")
        return " | ".join(reasons) if reasons else "NONE"


def compute_acif(
    bundle: ComponentScoreBundle,
    policy: MissingComponentPolicy = MissingComponentPolicy.STRICT,
) -> ACIFCellResult:
    """
    §2.1 — Compute ACIF for one cell from its ComponentScoreBundle.

    CONSTITUTIONAL: This is the ONLY call site for the ACIF formula.

    Args:
        bundle: All six scored components for this cell.
        policy: STRICT (raise on None) or DEGRADED (substitute 0.5).

    Returns:
        ACIFCellResult with full component trace and final score.

    Raises:
        MissingComponentError: If policy=STRICT and any component is None.
    """
    degraded_warnings: list[str] = []

    def _resolve(value: Optional[float], name: str) -> float:
        if value is not None:
            return value
        if policy == MissingComponentPolicy.STRICT:
            raise MissingComponentError(
                f"ACIF component '{name}' is None for cell {bundle.cell_id}. "
                f"All six components are required under STRICT policy."
            )
        degraded_warnings.append(f"{name}=None→0.5(DEGRADED)")
        return 0.5

    e_tilde = _resolve(bundle.evidence.adjusted_evidence_score, "adjusted_evidence_score")
    c_i     = _resolve(bundle.causal.causal_score, "causal_score")
    psi_i   = _resolve(bundle.physics.physics_score, "physics_score")
    t_i     = _resolve(bundle.temporal.temporal_score, "temporal_score")
    pi_i    = _resolve(bundle.province_prior.effective_prior, "province_prior")
    u_i     = _resolve(bundle.uncertainty.total_uncertainty, "total_uncertainty")

    certainty = 1.0 - u_i

    # Explicit veto audit flags (independent of multiplicative result)
    causal_veto   = bundle.causal.veto_flags.any_veto_fired
    physics_veto  = bundle.physics.physics_veto_fired
    temporal_veto = bundle.temporal.temporal_veto_fired
    province_veto = bundle.province_prior.province_veto_fired

    any_veto = causal_veto or physics_veto or temporal_veto or province_veto

    # §2.1: ACIF formula — multiplicative structure enforces hard vetoes automatically
    raw_acif = e_tilde * c_i * psi_i * t_i * pi_i * certainty

    # Clamp to [0, 1] and enforce explicit veto
    acif = 0.0 if any_veto else max(0.0, min(1.0, raw_acif))

    return ACIFCellResult(
        cell_id=bundle.cell_id,
        commodity=bundle.commodity,
        e_tilde=e_tilde,
        c_i=c_i,
        psi_i=psi_i,
        t_i=t_i,
        pi_i=pi_i,
        certainty=certainty,
        acif_score=acif,
        causal_veto=causal_veto,
        physics_veto=physics_veto,
        temporal_veto=temporal_veto,
        province_veto=province_veto,
        any_veto_fired=any_veto,
        degraded_warnings=tuple(degraded_warnings),
    )


# ---------------------------------------------------------------------------
# §11 — Scan-level ACIF aggregates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanACIFAggregates:
    """
    Scan-level ACIF aggregate statistics.
    Stored in CanonicalScan at freeze (Phase L).
    """
    commodity: str
    n_cells: int
    n_vetoed_cells: int

    acif_mean: float
    acif_max: float
    acif_weighted: float       # Area-weighted mean

    acif_p25: float            # 25th percentile
    acif_p50: float            # Median
    acif_p75: float            # 75th percentile
    acif_p90: float            # 90th percentile


def compute_scan_aggregates(
    cell_results: list[ACIFCellResult],
    cell_area_weights: Optional[list[float]] = None,
) -> ScanACIFAggregates:
    """
    §11 — Compute scan-level ACIF statistics from all cell results.

    Args:
        cell_results:       All ACIFCellResult objects for this scan.
        cell_area_weights:  Optional per-cell area weights. If None, uniform weights.

    Returns:
        ScanACIFAggregates with mean, max, weighted mean, and percentiles.

    Raises:
        ValueError: If cell_results is empty.
    """
    if not cell_results:
        raise ValueError("Cannot compute scan aggregates from empty cell list.")

    n = len(cell_results)
    scores = [r.acif_score for r in cell_results]
    n_vetoed = sum(1 for r in cell_results if r.any_veto_fired)

    # Weighted mean
    if cell_area_weights:
        if len(cell_area_weights) != n:
            raise ValueError("cell_area_weights length must match cell_results length.")
        total_w = sum(cell_area_weights)
        if total_w <= 0:
            raise ValueError("cell_area_weights must sum to a positive value.")
        weighted = sum(s * w for s, w in zip(scores, cell_area_weights)) / total_w
    else:
        weighted = sum(scores) / n

    # Percentiles (nearest-rank method)
    sorted_scores = sorted(scores)

    def _percentile(p: float) -> float:
        idx = max(0, min(n - 1, int(math.ceil(p / 100 * n)) - 1))
        return sorted_scores[idx]

    commodity = cell_results[0].commodity if cell_results else "unknown"

    return ScanACIFAggregates(
        commodity=commodity,
        n_cells=n,
        n_vetoed_cells=n_vetoed,
        acif_mean=sum(scores) / n,
        acif_max=max(scores),
        acif_weighted=weighted,
        acif_p25=_percentile(25),
        acif_p50=_percentile(50),
        acif_p75=_percentile(75),
        acif_p90=_percentile(90),
    )