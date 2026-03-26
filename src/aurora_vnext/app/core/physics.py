"""
Aurora OSI vNext — Physics Consistency Module
Phase I §I.3 | Phase B §6

CONSTITUTIONAL RULE: This is the ONLY location for physics residual computation
and physics consistency scoring.

Mathematical formulation:

  §6.1 — Gravity data residual:
    R_grav = ||W_d (g_obs - g_pred)||²
    where:
      g_obs  = observed gravity from harmonised GravityComposite (g_composite_mgal)
      g_pred = forward model prediction of gravity from density model ρ̂
      W_d    = diagonal data weighting matrix (inverse of observational error)
    R_grav ≥ 0; R_grav = 0 ↔ perfect gravity model fit.

  §6.2 — Poisson physics residual:
    R_phys = ||∇²Φ - 4πGρ||²
    where:
      Φ   = gravitational potential
      ρ   = density model
      G   = gravitational constant 6.674×10⁻¹¹ m³ kg⁻¹ s⁻²
    R_phys enforces that the density model is self-consistent with Poisson's equation.

  §6.4 — Physics consistency score:
    Ψ_i = exp(-λ₁ R_grav - λ₂ R_phys)
    where λ₁, λ₂ > 0 are commodity-specific penalty weights from Θ_c.
    Ψ_i → 1 at zero residuals, Ψ_i → 0 at large residuals.

  §6.5 — Fluid system residuals:
    R_darcy = ||v - (-k/μ)∇P||²     (Darcy flow, hydrocarbon systems)
    R_wc    = |Δg_wc - g_corr_obs|² (water-column gravity, offshore)

  §6.6 — Physics hard veto:
    If R_grav > τ_grav_veto OR R_phys > τ_phys_veto → Ψ_i = 0.0

Physics residuals are FIRST-CLASS OUTPUTS — persisted in ScanCell.
They are NOT internal diagnostics.

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.component_scores import (
    PhysicsResiduals,
    PhysicsResult,
)

# Physical constant
G_SI = 6.674e-11   # m³ kg⁻¹ s⁻²
G_MGAL = G_SI * 1e5  # Convert to mGal units

# Default penalty weights (overridden by Θ_c in Phase J)
_DEFAULT_LAMBDA_1 = 0.5   # Gravity residual penalty
_DEFAULT_LAMBDA_2 = 0.3   # Poisson residual penalty


def compute_gravity_residual(
    g_obs_mgal: Optional[float],
    g_pred_mgal: Optional[float],
    w_d: float = 1.0,
) -> Optional[float]:
    """
    §6.1 — Compute gravity data residual R_grav.

    R_grav = (W_d × (g_obs - g_pred))²

    For scalar case: W_d = 1 / observational_error_mgal (default 1.0).
    Returns None if either g_obs or g_pred is unavailable.

    Returns:
        R_grav ≥ 0, or None if inputs insufficient.
    """
    if g_obs_mgal is None or g_pred_mgal is None:
        return None
    if w_d < 0:
        raise ValueError(f"Data weight W_d must be ≥ 0, got {w_d}")
    residual = (w_d * (g_obs_mgal - g_pred_mgal)) ** 2
    return max(0.0, residual)


def compute_poisson_residual(
    phi_laplacian: Optional[float],
    rho_model: Optional[float],
) -> Optional[float]:
    """
    §6.2 — Compute Poisson physics residual R_phys.

    R_phys = (∇²Φ - 4πGρ)²

    Args:
        phi_laplacian: ∇²Φ — Laplacian of the gravitational potential field.
                       In practice: derived from vertical gradient Γ_zz (Eötvös).
                       1 Eötvös = 10⁻⁹ s⁻², converted via ∇²Φ = Γ_zz in s⁻².
        rho_model:     Density model ρ in kg/m³ from inversion.

    Returns:
        R_phys ≥ 0, or None if inputs insufficient.
    """
    if phi_laplacian is None or rho_model is None:
        return None

    poisson_rhs = 4.0 * math.pi * G_SI * rho_model
    residual = (phi_laplacian - poisson_rhs) ** 2
    return max(0.0, residual)


def compute_darcy_residual(
    v_observed: Optional[float],
    k_permeability: Optional[float],
    mu_viscosity: Optional[float],
    pressure_gradient: Optional[float],
) -> Optional[float]:
    """
    §6.5 — Compute Darcy flow residual R_darcy (fluid/hydrocarbon systems).

    R_darcy = (v_obs - (-k/μ) × ∇P)²
    where:
      v_obs          = observed fluid velocity proxy (m/s)
      k              = permeability (m²)
      μ              = dynamic viscosity (Pa·s)
      ∇P             = pressure gradient (Pa/m)

    Returns:
        R_darcy ≥ 0, or None if inputs insufficient.
    """
    if any(v is None for v in [v_observed, k_permeability, mu_viscosity, pressure_gradient]):
        return None
    if mu_viscosity <= 0:
        return None

    v_darcy_pred = -(k_permeability / mu_viscosity) * pressure_gradient
    residual = (v_observed - v_darcy_pred) ** 2
    return max(0.0, residual)


def compute_water_column_residual(
    g_obs_offshore_mgal: Optional[float],
    g_obs_uncorrected_mgal: Optional[float],
    delta_g_wc_mgal: Optional[float],
) -> Optional[float]:
    """
    §6.5 — Compute water-column gravity residual R_wc (offshore systems).

    R_wc = |Δg_wc - (g_uncorrected - g_corrected)|²
    Measures how well the water-column correction model explains the
    gravity difference between the raw and corrected observations.

    Returns:
        R_wc ≥ 0, or None if inputs insufficient.
    """
    if any(v is None for v in [g_obs_offshore_mgal, g_obs_uncorrected_mgal, delta_g_wc_mgal]):
        return None

    observed_difference = g_obs_uncorrected_mgal - g_obs_offshore_mgal
    residual = (delta_g_wc_mgal - observed_difference) ** 2
    return max(0.0, residual)


def compute_physics_score(
    r_grav: Optional[float],
    r_phys: Optional[float],
    lambda_1: float = _DEFAULT_LAMBDA_1,
    lambda_2: float = _DEFAULT_LAMBDA_2,
) -> float:
    """
    §6.4 — Compute physics consistency score Ψ_i.

    Ψ_i = exp(-λ₁ R_grav - λ₂ R_phys)

    Properties:
      Ψ_i = 1.0 when R_grav = R_phys = 0 (perfect physics consistency)
      Ψ_i → 0 as residuals grow large
      Missing residuals (None) contribute 0 to the exponent (not penalised)

    Args:
        r_grav:   Gravity residual R_grav ≥ 0 (or None)
        r_phys:   Poisson residual R_phys ≥ 0 (or None)
        lambda_1: Gravity penalty weight (Θ_c)
        lambda_2: Poisson penalty weight (Θ_c)

    Returns:
        Ψ_i ∈ (0, 1]
    """
    if lambda_1 < 0 or lambda_2 < 0:
        raise ValueError(f"Lambda penalties must be ≥ 0: λ₁={lambda_1}, λ₂={lambda_2}")

    exponent = 0.0
    if r_grav is not None:
        exponent += lambda_1 * r_grav
    if r_phys is not None:
        exponent += lambda_2 * r_phys

    psi = math.exp(-exponent)
    return max(0.0, min(1.0, psi))


def apply_physics_veto(
    r_grav: Optional[float],
    r_phys: Optional[float],
    tau_grav_veto: float = 100.0,
    tau_phys_veto: float = 50.0,
) -> bool:
    """
    §6.6 — Check if physics residuals exceed veto thresholds.

    Returns True (veto fires → Ψ_i = 0.0) if:
      R_grav > τ_grav_veto  OR  R_phys > τ_phys_veto

    Threshold values are sourced from Θ_c (overridden by commodity in Phase J).
    None residuals are NOT vetoed — absence of data is handled by u_sensor.
    """
    if r_grav is not None and r_grav > tau_grav_veto:
        return True
    if r_phys is not None and r_phys > tau_phys_veto:
        return True
    return False


def score_physics(
    cell_id: str,
    commodity: str,
    g_obs_mgal: Optional[float],
    g_pred_mgal: Optional[float],
    phi_laplacian: Optional[float],
    rho_model: Optional[float],
    v_observed: Optional[float] = None,
    k_permeability: Optional[float] = None,
    mu_viscosity: Optional[float] = None,
    pressure_gradient: Optional[float] = None,
    g_obs_uncorrected_mgal: Optional[float] = None,
    delta_g_wc_mgal: Optional[float] = None,
    lambda_1: float = _DEFAULT_LAMBDA_1,
    lambda_2: float = _DEFAULT_LAMBDA_2,
    tau_grav_veto: float = 100.0,
    tau_phys_veto: float = 50.0,
    w_d: float = 1.0,
) -> PhysicsResult:
    """
    Full physics scoring pipeline for one cell.
    Computes all residuals → physics score → veto check.
    """
    r_grav = compute_gravity_residual(g_obs_mgal, g_pred_mgal, w_d)
    r_phys = compute_poisson_residual(phi_laplacian, rho_model)
    r_darcy = compute_darcy_residual(v_observed, k_permeability, mu_viscosity, pressure_gradient)
    r_wc = compute_water_column_residual(g_obs_mgal, g_obs_uncorrected_mgal, delta_g_wc_mgal)

    veto_fired = apply_physics_veto(r_grav, r_phys, tau_grav_veto, tau_phys_veto)
    psi = 0.0 if veto_fired else compute_physics_score(r_grav, r_phys, lambda_1, lambda_2)

    return PhysicsResult(
        cell_id=cell_id,
        commodity=commodity,
        residuals=PhysicsResiduals(
            cell_id=cell_id,
            gravity_residual=r_grav,
            physics_residual=r_phys,
            darcy_residual=r_darcy,
            water_column_residual=r_wc,
        ),
        physics_score=psi,
        physics_veto_fired=veto_fired,
    )