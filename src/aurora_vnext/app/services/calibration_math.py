"""
Aurora OSI vNext — Calibration Mathematics
Phase AC §AC.2

Implements all calibration update formulas with full provenance weighting.

Three update pathways:
  1. Bayesian province prior update
  2. Residual quantile threshold calibration (physics, gravity, temporal)
  3. Uncertainty recalibration factor k_u

MATHEMATICAL SPECIFICATION:

  Provenance weight (geometric mean):
    w_gt = (w_s · w_a · w_t · w_g)^(1/4)
    Geometric mean ensures one weak dimension cannot be masked by
    strong performance in others.

  Province prior Bayesian update (Beta-Binomial):
    Π_post(c,r) = (α₀ + Σw_gt⁺) / (α₀ + β₀ + Σw_gt)
    Interpretable: α₀ pseudocounts protect against sparse data.

  Physics/gravity veto threshold (empirical quantile):
    τ(c) = Q_0.95(R | confirmed positive GT records for commodity c)
    Derived from residual distributions of confirmed positives only.
    Never set from arbitrary heuristics.

  Uncertainty recalibration:
    U' = 1 - (1 - U)^k_u    k_u ≥ 1.0 only
    k_u derived from measured overconfidence gap in GT validation set.

CONSTITUTIONAL RULES:
  Rule 1: No function in this module calls core/scoring, core/tiering,
          core/gates, core/evidence, core/causal, core/physics,
          core/temporal, core/priors, or core/uncertainty.
  Rule 2: All functions receive pre-validated GT records and weights.
          No storage access occurs here.
  Rule 3: Every output is a configuration parameter — not a scan output.
  Rule 4: k_u < 1.0 raises ValueError unconditionally.
  Rule 5: Thresholds from fewer than 3 confirmed records raise ValueError.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Optional

from app.models.calibration_math_model import (
    ProvenanceWeight,
    BayesianPriorUpdate,
    ResidualQuantileThreshold,
    UncertaintyRecalibration,
)


# ---------------------------------------------------------------------------
# 1. Provenance weighting
# ---------------------------------------------------------------------------

def compute_provenance_weight(
    record_id:                   str,
    source_confidence:           float,
    spatial_accuracy:            float,
    temporal_relevance:          float,
    geological_context_strength: float,
) -> ProvenanceWeight:
    """
    Compute the geometric mean composite weight for one GT record.

    w_gt = (w_s · w_a · w_t · w_g)^(1/4)

    All inputs must be in [0, 1]. Geometric mean raises to 0 if any
    dimension is 0 — deliberately, to surface zero-confidence dimensions.

    PROOF: result is ProvenanceWeight — configuration metadata, not an ACIF value.
    """
    for name, val in [
        ("source_confidence",           source_confidence),
        ("spatial_accuracy",            spatial_accuracy),
        ("temporal_relevance",          temporal_relevance),
        ("geological_context_strength", geological_context_strength),
    ]:
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"{name} must be in [0, 1], got {val}")

    product = (
        source_confidence *
        spatial_accuracy *
        temporal_relevance *
        geological_context_strength
    )
    composite = product ** 0.25   # geometric mean

    return ProvenanceWeight(
        record_id                   = record_id,
        source_confidence           = source_confidence,
        spatial_accuracy            = spatial_accuracy,
        temporal_relevance          = temporal_relevance,
        geological_context_strength = geological_context_strength,
        composite                   = round(composite, 8),
    )


# ---------------------------------------------------------------------------
# 2. Bayesian province prior update
# ---------------------------------------------------------------------------

def bayesian_prior_update(
    commodity:     str,
    province_id:   str,
    alpha_0:       float,
    beta_0:        float,
    positive_weights: list[ProvenanceWeight],   # confirmed positive GT records
    all_weights:      list[ProvenanceWeight],   # all relevant GT records (positive + negative)
) -> BayesianPriorUpdate:
    """
    Compute the Bayesian province prior update.

    Π_post(c,r) = (α₀ + Σw_gt⁺) / (α₀ + β₀ + Σw_gt)

    PROOF: Π_post is a probability ∈ (0, 1).
    It updates the province prior used by core/priors.py at scan time.
    It does NOT compute or replace ACIF.

    Args:
      alpha_0:          Prior positive pseudocount (must be > 0)
      beta_0:           Prior negative pseudocount (must be > 0)
      positive_weights: ProvenanceWeights for confirmed positive records
      all_weights:      ProvenanceWeights for all relevant records

    Returns:
      BayesianPriorUpdate — frozen, immutable result.

    Raises:
      ValueError if alpha_0 ≤ 0 or beta_0 ≤ 0 or all_weights is empty.
    """
    if alpha_0 <= 0 or beta_0 <= 0:
        raise ValueError(f"alpha_0 and beta_0 must be > 0, got α₀={alpha_0}, β₀={beta_0}")
    if not all_weights:
        raise ValueError("all_weights must be non-empty for Bayesian update")

    sum_wgt_positive = sum(w.composite for w in positive_weights)
    sum_wgt_total    = sum(w.composite for w in all_weights)

    if sum_wgt_total <= 0:
        raise ValueError(
            f"sum_wgt_total is {sum_wgt_total} — all provenance weights are zero. "
            f"Check GT record confidence fields."
        )

    posterior = (alpha_0 + sum_wgt_positive) / (alpha_0 + beta_0 + sum_wgt_total)

    return BayesianPriorUpdate(
        commodity           = commodity,
        province_id         = province_id,
        alpha_0             = alpha_0,
        beta_0              = beta_0,
        sum_wgt_positive    = round(sum_wgt_positive, 8),
        sum_wgt_total       = round(sum_wgt_total, 8),
        posterior_prior     = round(posterior, 8),
        n_records_positive  = len(positive_weights),
        n_records_total     = len(all_weights),
        provenance_weights  = tuple(all_weights),
    )


# ---------------------------------------------------------------------------
# 3. Residual quantile threshold calibration
# ---------------------------------------------------------------------------

def _quantile(values: list[float], q: float) -> float:
    """
    Compute the q-th quantile of values (linear interpolation).
    q ∈ (0, 1].
    """
    if not values:
        raise ValueError("Cannot compute quantile of empty list")
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = q * (n - 1)
    lo  = int(idx)
    hi  = min(lo + 1, n - 1)
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def residual_quantile_threshold(
    commodity:        str,
    threshold_type:   str,    # "physics" | "gravity" | "temporal"
    residual_values:  list[float],
    weights:          list[ProvenanceWeight],
    quantile:         float = 0.95,
) -> ResidualQuantileThreshold:
    """
    Compute empirically grounded veto threshold from GT residual distributions.

    τ(c) = Q_0.95( R | confirmed positive GT records for commodity c )

    PROOF: τ is a threshold — configuration for the veto gate check.
    It does NOT compute ACIF or assign tier membership.
    It updates CalibrationParameters.tau_phys or .tau_grav only.

    Args:
      residual_values: residuals extracted from confirmed positive GT records
      weights:         ProvenanceWeights for those records (must match in length)
      quantile:        Q quantile — default 0.95

    Raises:
      ValueError if fewer than 3 confirmed records or mismatched lengths.
    """
    if threshold_type not in ("physics", "gravity", "temporal"):
        raise ValueError(
            f"threshold_type must be 'physics', 'gravity', or 'temporal', "
            f"got {threshold_type!r}"
        )
    if len(residual_values) != len(weights):
        raise ValueError(
            f"residual_values length ({len(residual_values)}) must match "
            f"weights length ({len(weights)})"
        )
    if len(residual_values) < 3:
        raise ValueError(
            f"Threshold calibration requires ≥ 3 confirmed records, "
            f"got {len(residual_values)}. Insufficient ground truth."
        )

    computed = _quantile(residual_values, quantile)

    return ResidualQuantileThreshold(
        commodity          = commodity,
        threshold_type     = threshold_type,
        quantile           = quantile,
        residual_values    = tuple(residual_values),
        computed_threshold = round(computed, 8),
        n_records          = len(residual_values),
        provenance_weights = tuple(weights),
    )


# ---------------------------------------------------------------------------
# 4. Uncertainty recalibration factor
# ---------------------------------------------------------------------------

def uncertainty_recalibration_factor(
    commodity:              str,
    predicted_uncertainties: list[float],   # U values from model for GT cells
    empirical_uncertainties: list[float],   # empirical error rates from GT records
    weights:                 list[ProvenanceWeight],
    min_k_u:                 float = 1.0,
) -> UncertaintyRecalibration:
    """
    Compute k_u, the uncertainty recalibration factor for commodity c.

    U' = 1 - (1 - U)^k_u    k_u ≥ 1.0

    k_u derived from:
      mean_overconfidence = mean(predicted_uncertainty - empirical_uncertainty)
      If mean_overconfidence < 0: model is underconfident → k_u = 1.0 (no change)
      If mean_overconfidence > 0: model is overconfident → k_u > 1.0 (inflate U)

    k_u estimation (simple linear heuristic, auditable):
      k_u = max(1.0, 1.0 + mean_overconfidence * 2.0)

    PROOF: k_u is a configuration scalar — not an ACIF value.
    It is stored in CalibrationParameters.uncertainty_ku_per_commodity.
    It is applied in core/uncertainty.py at scan time only —
    never retroactively to existing canonical scans.

    Raises:
      ValueError if k_u < min_k_u (default 1.0).
    """
    if len(predicted_uncertainties) != len(empirical_uncertainties):
        raise ValueError("predicted and empirical uncertainty lists must have same length")
    if len(predicted_uncertainties) < 3:
        raise ValueError("Uncertainty recalibration requires ≥ 3 records")

    gaps = [p - e for p, e in zip(predicted_uncertainties, empirical_uncertainties)]
    mean_overconfidence = statistics.mean(gaps)

    k_u = max(min_k_u, 1.0 + mean_overconfidence * 2.0)

    if k_u < 1.0:
        raise ValueError(
            f"Computed k_u={k_u:.4f} < 1.0 — deflating uncertainty is forbidden. "
            f"This would underestimate uncertainty without evidence of underestimation. "
            f"k_u is clamped to 1.0 — use min_k_u=1.0."
        )

    evidence = (
        f"mean overconfidence gap = {mean_overconfidence:.4f} "
        f"across {len(gaps)} GT records. "
        f"k_u = max(1.0, 1 + {mean_overconfidence:.4f} × 2) = {k_u:.4f}."
    )

    return UncertaintyRecalibration(
        commodity           = commodity,
        k_u                 = round(k_u, 6),
        mean_overconfidence = round(mean_overconfidence, 6),
        n_records           = len(predicted_uncertainties),
        provenance_weights  = tuple(weights),
        evidence_summary    = evidence,
    )


# ---------------------------------------------------------------------------
# 5. Lambda parameter update (direct, auditable)
# ---------------------------------------------------------------------------

def compute_lambda_updates(
    commodity:       str,
    current_lambda_1: float,
    current_lambda_2: float,
    positive_weights: list[ProvenanceWeight],
    all_weights:      list[ProvenanceWeight],
    learning_rate:   float = 0.05,
) -> dict[str, float]:
    """
    Compute updated λ₁, λ₂ weighting parameters.

    λ₁ (evidence weight) and λ₂ (causal weight) are nudged toward
    the empirical signal strength from GT-confirmed positives.

    Formula (gradient-free empirical update):
      signal_ratio = Σw_gt⁺ / Σw_gt_total
      Δλ = learning_rate × (signal_ratio - 0.5)   # relative to neutral 0.5
      λ₁_new = clamp(λ₁ + Δλ, 0.1, 2.0)
      λ₂_new = clamp(λ₂ + Δλ, 0.1, 2.0)

    PROOF: λ₁, λ₂ are multiplicative weights in the ACIF formula.
    Updating them is updating configuration — not computing ACIF.
    The formula does not evaluate ACIF for any scan.
    Bounds [0.1, 2.0] prevent degenerate parameter collapse.

    Returns:
      dict: {"lambda_1": float, "lambda_2": float}
    """
    sum_pos   = sum(w.composite for w in positive_weights)
    sum_total = sum(w.composite for w in all_weights) if all_weights else 0.0

    if sum_total <= 0:
        return {"lambda_1": current_lambda_1, "lambda_2": current_lambda_2}

    signal_ratio = sum_pos / sum_total
    delta = learning_rate * (signal_ratio - 0.5)

    lambda_1_new = round(max(0.1, min(2.0, current_lambda_1 + delta)), 6)
    lambda_2_new = round(max(0.1, min(2.0, current_lambda_2 + delta)), 6)

    return {"lambda_1": lambda_1_new, "lambda_2": lambda_2_new}