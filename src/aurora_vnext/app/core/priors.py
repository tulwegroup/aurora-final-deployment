"""
Aurora OSI vNext — Province Prior Module
Phase I §I.5 | Phase B §8

CONSTITUTIONAL RULE: This is the ONLY location for province prior scoring
and province impossibility veto logic.

Mathematical formulation:

  §8.2 — Province prior lookup:
    Π^(c)(r_i) = baseline prior probability for commodity c in province r_i
    Sourced from the tectono-stratigraphic province prior database.
    Π^(c)(r_i) ∈ [0, 1].

  §8.3 — Province impossibility veto:
    If province r_i is geologically impossible for commodity c:
      Π^(c)(r_i) = 0.0  (ABSOLUTE — not low, exactly zero)
    This propagates through the ACIF multiplicative formula to zero the cell.

  §8.4 — Bayesian posterior update:
    When ground-truth calibration data D_GT is available:
      Π_post^(c)(r_i) = P(r_i | D_GT, c) ∝ P(D_GT | r_i, c) × Π^(c)(r_i)

    Simplified conjugate update for Beta-distributed prior:
      Π_post = (α_0 + n_pos) / (α_0 + β_0 + n_total)
    where:
      α_0 = effective_prior × n_prior_weight    (prior successes)
      β_0 = (1 - effective_prior) × n_prior_weight (prior failures)
      n_pos   = number of positive ground-truth observations
      n_total = total ground-truth observations

    Posterior is stored separately — NEVER overwrites baseline prior.

Province prior uncertainty u_prior is derived from the 95% CI width:
    u_prior = (CI_upper - CI_lower) / 1.0    (normalised CI width)
This feeds into core/uncertainty.py.

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.component_scores import ProvincePriorResult

_EPSILON = 1e-10


def lookup_province_prior(
    province_code: Optional[str],
    commodity: str,
    prior_probability: Optional[float],
    is_impossible: bool = False,
    impossibility_reason: Optional[str] = None,
    ci_95_lower: Optional[float] = None,
    ci_95_upper: Optional[float] = None,
) -> tuple[float, bool, Optional[str]]:
    """
    §8.2 / §8.3 — Look up and validate province prior probability.

    This function accepts pre-fetched values from the province prior store
    (storage/province_priors.py) and applies constitutional rules.

    Args:
        province_code:       Province identifier (None = unknown province)
        commodity:           Commodity name
        prior_probability:   Pre-fetched Π^(c)(r_i) from DB (None = no prior available)
        is_impossible:       True if DB flags this as an impossible province
        impossibility_reason: Why it is impossible
        ci_95_lower/upper:   Confidence interval bounds

    Returns:
        (prior_value, veto_fired, impossibility_reason)
    """
    # Impossible province → absolute veto
    if is_impossible:
        return 0.0, True, impossibility_reason

    # Unknown province → moderate uncertainty (no veto, but no strong prior either)
    if prior_probability is None or province_code is None:
        return 0.3, False, None  # Conservative default for unknown provinces

    # Validate bounds
    clamped = max(0.0, min(1.0, prior_probability))
    return clamped, False, None


def apply_province_veto(
    prior_value: float,
    epsilon_province: float = 0.0,
) -> bool:
    """
    §8.3 — Apply province veto condition.

    Veto fires if prior_value ≤ epsilon_province (default: exactly 0.0).
    epsilon_province allows commodity-specific near-zero thresholds.

    Returns:
        True if province veto fires (P_i = 0.0 in ACIF).
    """
    return prior_value <= epsilon_province


def compute_bayesian_posterior(
    prior_probability: float,
    n_positive_observations: int,
    n_total_observations: int,
    prior_weight: float = 10.0,
) -> float:
    """
    §8.4 — Beta-conjugate Bayesian posterior update.

    Treats the prior as a Beta(α₀, β₀) distribution with effective weight
    n_prior_weight observations, then updates with ground-truth counts.

    Π_post = (α₀ + n_pos) / (α₀ + β₀ + n_total)
    where:
      α₀ = prior_probability × prior_weight
      β₀ = (1 - prior_probability) × prior_weight

    Args:
        prior_probability:        Π^(c)(r_i) ∈ [0, 1]
        n_positive_observations:  Count of GT-confirmed presence events
        n_total_observations:     Total GT observations in province
        prior_weight:             Effective sample size of prior (α₀ + β₀)

    Returns:
        Posterior Π_post^(c)(r_i) ∈ [0, 1]
    """
    if n_total_observations < 0 or n_positive_observations < 0:
        raise ValueError("Observation counts must be non-negative")
    if n_positive_observations > n_total_observations:
        raise ValueError("Positive observations cannot exceed total observations")
    if prior_weight <= 0:
        raise ValueError("prior_weight must be > 0")

    alpha_0 = prior_probability * prior_weight
    beta_0  = (1.0 - prior_probability) * prior_weight

    posterior = (alpha_0 + n_positive_observations) / (alpha_0 + beta_0 + n_total_observations)
    return max(0.0, min(1.0, posterior))


def compute_prior_uncertainty(
    ci_95_lower: Optional[float],
    ci_95_upper: Optional[float],
) -> float:
    """
    Compute province prior uncertainty u_prior from 95% CI width (§10.2).

    u_prior = (CI_upper - CI_lower)
    Normalised: a CI spanning [0, 1] gives u_prior = 1.0 (maximum uncertainty).
    A point estimate gives u_prior = 0.0.

    Returns:
        u_prior ∈ [0, 1]
    """
    if ci_95_lower is None or ci_95_upper is None:
        return 0.5  # Unknown CI → moderate uncertainty
    width = max(0.0, ci_95_upper - ci_95_lower)
    return max(0.0, min(1.0, width))


def score_province_prior(
    cell_id: str,
    commodity: str,
    province_code: Optional[str],
    prior_probability: Optional[float],
    is_impossible: bool = False,
    impossibility_reason: Optional[str] = None,
    ci_95_lower: Optional[float] = None,
    ci_95_upper: Optional[float] = None,
    n_positive_gt: int = 0,
    n_total_gt: int = 0,
    prior_weight: float = 10.0,
    epsilon_province: float = 0.0,
) -> ProvincePriorResult:
    """
    Full province prior pipeline for one cell.
    Calls lookup → veto check → Bayesian posterior (if GT data available).
    """
    prior_val, veto_fired, reason = lookup_province_prior(
        province_code=province_code,
        commodity=commodity,
        prior_probability=prior_probability,
        is_impossible=is_impossible,
        impossibility_reason=impossibility_reason,
        ci_95_lower=ci_95_lower,
        ci_95_upper=ci_95_upper,
    )

    if veto_fired:
        prior_val = 0.0

    # Bayesian posterior update (only if ground-truth data available)
    posterior = None
    if n_total_gt > 0 and not veto_fired:
        posterior = compute_bayesian_posterior(
            prior_probability=prior_val,
            n_positive_observations=n_positive_gt,
            n_total_observations=n_total_gt,
            prior_weight=prior_weight,
        )

    return ProvincePriorResult(
        cell_id=cell_id,
        commodity=commodity,
        province_code=province_code,
        prior_probability=prior_val,
        posterior_probability=posterior,
        province_veto_fired=veto_fired,
        impossibility_reason=reason,
        ci_95_lower=ci_95_lower,
        ci_95_upper=ci_95_upper,
    )