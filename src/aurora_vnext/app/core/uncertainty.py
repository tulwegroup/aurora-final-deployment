"""
Aurora OSI vNext — Uncertainty Propagation Module
Phase I §I.6 | Phase B §10

CONSTITUTIONAL RULE: This is the ONLY location for uncertainty aggregation.
Probabilistic union is CONSTITUTIONALLY REQUIRED — arithmetic mean is prohibited.

Mathematical formulation:

  §10.2 — Five independent uncertainty components:

    u_sensor:  Sensor coverage uncertainty
               u_sensor = 1 - (n_present / 42)
               One missing observable contributes u_sensor += 1/42.
               All missing → u_sensor = 1.0.

    u_model:   Inversion model uncertainty
               u_model = σ_ρ / (ρ̄ + ε)
               Coefficient of variation of the density model posterior distribution.
               High σ_ρ relative to ρ̄ → high u_model.

    u_physics: Physics residual uncertainty
               u_physics = 1 - Ψ_i
               Directly derived from the physics consistency score.
               Perfect physics fit (Ψ=1) → u_physics = 0.

    u_temporal: Temporal instability uncertainty
               u_temporal = 1 - T_i
               Directly derived from the temporal coherence score.
               Perfect temporal coherence (T=1) → u_temporal = 0.

    u_prior:   Province ambiguity uncertainty
               u_prior = (CI_95_upper - CI_95_lower)
               Width of the province prior 95% CI.
               Point estimate → u_prior = 0; full-range prior → u_prior = 1.

  §10.3 — Probabilistic union (CONSTITUTIONALLY REQUIRED):
    U_i^(c) = 1 - ∏_{k=1}^{5} (1 - u_k)

    Properties:
      If any u_k = 1.0 → U_i = 1.0  (total uncertainty)
      If all u_k = 0.0 → U_i = 0.0  (zero uncertainty)
      Always ≥ max(u_k)             (never less than dominant component)

    FORBIDDEN: U_i = Σ u_k / 5 (arithmetic mean — underestimates joint uncertainty)

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

from typing import Optional

from app.models.component_scores import (
    PhysicsResult,
    ProvincePriorResult,
    TemporalResult,
    UncertaintyComponents,
    UncertaintyResult,
)
from app.core.priors import compute_prior_uncertainty

_EPSILON = 1e-10


def compute_sensor_uncertainty(
    present_count: int,
    total_observables: int = 42,
) -> float:
    """
    §10.2 — Sensor coverage uncertainty u_sensor.

    u_sensor = 1 - (present_count / total_observables)

    All observables present → u_sensor = 0.0
    All observables missing → u_sensor = 1.0

    Args:
        present_count:      Number of non-null observables in ObservableVector
        total_observables:  Always 42 (constitutional constant)

    Returns:
        u_sensor ∈ [0, 1]
    """
    if total_observables <= 0:
        raise ValueError("total_observables must be > 0")
    clamped = max(0, min(total_observables, present_count))
    return 1.0 - (clamped / total_observables)


def compute_model_uncertainty(
    sigma_rho: Optional[float],
    rho_bar: Optional[float],
) -> float:
    """
    §10.2 — Inversion model uncertainty u_model.

    u_model = clamp(σ_ρ / (ρ̄ + ε), 0, 1)

    Coefficient of variation of the density posterior.
    Large spread relative to mean → high model uncertainty.

    Returns:
        u_model ∈ [0, 1]
    """
    if sigma_rho is None or rho_bar is None:
        return 0.5  # Unknown inversion quality → moderate uncertainty
    if sigma_rho < 0:
        raise ValueError(f"sigma_rho must be ≥ 0, got {sigma_rho}")

    u_model = sigma_rho / (abs(rho_bar) + _EPSILON)
    return max(0.0, min(1.0, u_model))


def compute_physics_uncertainty(psi_i: float) -> float:
    """
    §10.2 — Physics residual uncertainty u_physics = 1 - Ψ_i.

    Perfect physics (Ψ_i = 1.0) → u_physics = 0.0.
    Physics veto (Ψ_i = 0.0)   → u_physics = 1.0.

    Returns:
        u_physics ∈ [0, 1]
    """
    if not (0.0 <= psi_i <= 1.0):
        raise ValueError(f"psi_i must be in [0, 1], got {psi_i}")
    return max(0.0, min(1.0, 1.0 - psi_i))


def compute_temporal_uncertainty(t_i: float) -> float:
    """
    §10.2 — Temporal instability uncertainty u_temporal = 1 - T_i.

    Perfect coherence (T_i = 1.0) → u_temporal = 0.0.
    No coherence (T_i = 0.0)     → u_temporal = 1.0.

    Returns:
        u_temporal ∈ [0, 1]
    """
    if not (0.0 <= t_i <= 1.0):
        raise ValueError(f"t_i must be in [0, 1], got {t_i}")
    return max(0.0, min(1.0, 1.0 - t_i))


def compute_total_uncertainty(components: UncertaintyComponents) -> float:
    """
    §10.3 — Probabilistic union: U_i = 1 - ∏(1 - u_k).

    CONSTITUTIONAL INVARIANT: Any u_k = 1.0 → U_i = 1.0.
    This is enforced by the product formula — not special-cased.

    Returns:
        U_i^(c) ∈ [0, 1]
    """
    u_values = [
        components.u_sensor,
        components.u_model,
        components.u_physics,
        components.u_temporal,
        components.u_prior,
    ]

    # Validate all components
    for i, u in enumerate(u_values):
        if not (0.0 <= u <= 1.0):
            raise ValueError(f"Uncertainty component {i} out of bounds: {u}")

    # Probabilistic union: U = 1 - ∏(1 - u_k)
    product = 1.0
    for u in u_values:
        product *= (1.0 - u)

    total = 1.0 - product
    return max(0.0, min(1.0, total))


def score_uncertainty(
    cell_id: str,
    commodity: str,
    physics_result: PhysicsResult,
    temporal_result: TemporalResult,
    province_result: ProvincePriorResult,
    present_observable_count: int,
    sigma_rho: Optional[float] = None,
    rho_bar: Optional[float] = None,
) -> UncertaintyResult:
    """
    Full uncertainty propagation pipeline for one cell.
    Assembles all five components and computes probabilistic union U_i.
    """
    u_sensor  = compute_sensor_uncertainty(present_observable_count)
    u_model   = compute_model_uncertainty(sigma_rho, rho_bar)
    u_physics = compute_physics_uncertainty(physics_result.physics_score)
    u_temporal = compute_temporal_uncertainty(temporal_result.temporal_score)
    u_prior   = compute_prior_uncertainty(
        ci_95_lower=province_result.ci_95_lower,
        ci_95_upper=province_result.ci_95_upper,
    )

    components = UncertaintyComponents(
        u_sensor=u_sensor,
        u_model=u_model,
        u_physics=u_physics,
        u_temporal=u_temporal,
        u_prior=u_prior,
    )
    total_u = compute_total_uncertainty(components)

    return UncertaintyResult(
        cell_id=cell_id,
        commodity=commodity,
        components=components,
        total_uncertainty=total_u,
    )