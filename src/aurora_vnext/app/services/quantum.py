"""
Aurora OSI vNext — Quantum Inversion Service (Stub / Classical Fallback)
Phase K §K.5 | Patent Breakthrough 9 (post-MVP)

This module is a STUB for the quantum-assisted gravity inversion component
described in Patent Breakthrough 9. Full quantum implementation is a
post-MVP deliverable (Phase Q+).

Current state: classical fallback only.
  - Classical fallback uses iterative gradient-descent density inversion.
  - Quantum path: blocked behind QUANTUM_INVERSION_ENABLED feature flag.
  - API surface is stable — Phase Q will implement the quantum solver
    behind the same interface without requiring changes to callers.

Layer rule: This is a Layer-2 Service.
  - NO scoring, tiering, gates, or ACIF logic.
  - Returns ONLY InversionResult (density model + uncertainty).
  - core/physics.py consumes InversionResult to compute residuals.

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InversionMode(str, Enum):
    CLASSICAL = "classical"    # Current implementation
    QUANTUM   = "quantum"      # Post-MVP (Phase Q+)


@dataclass(frozen=True)
class InversionResult:
    """
    Output of the gravity inversion service for one cell.

    rho_mean:   Best-estimate density (kg/m³) from inversion.
    rho_sigma:  Standard deviation of the density posterior (kg/m³).
                Used by core/uncertainty.py to compute u_model.
    g_pred:     Predicted gravity (mGal) from the density model.
                Used by core/physics.py to compute R_grav.
    mode:       Which solver produced this result.
    converged:  True if the inversion converged within tolerance.
    n_iterations: Number of solver iterations executed.
    residual_norm: Final ||g_obs - g_pred|| (diagnostic only — not R_grav).
    """
    cell_id: str
    scan_id: str
    rho_mean: Optional[float]           # Density estimate (kg/m³)
    rho_sigma: Optional[float]          # Posterior uncertainty (kg/m³)
    g_pred: Optional[float]             # Predicted gravity (mGal)
    mode: InversionMode
    converged: bool
    n_iterations: int
    residual_norm: Optional[float]      # Diagnostic — NOT R_grav


def _classical_inversion(
    g_obs_mgal: Optional[float],
    depth_m: float,
    background_density_kg_m3: float,
    max_iterations: int,
    tolerance: float,
) -> tuple[Optional[float], Optional[float], Optional[float], bool, int]:
    """
    Simplified classical gradient-descent density inversion.

    Implements a scalar Bouguer-slab approximation:
      g_pred = 2πG × ρ × h  (Bouguer plate formula)
      ρ̂ = g_obs / (2πG × h)

    Returns:
        (rho_mean, rho_sigma, g_pred, converged, n_iterations)
    """
    if g_obs_mgal is None or depth_m <= 0:
        return None, None, None, False, 0

    G_MGAL = 6.674e-11 * 1e5   # mGal units
    import math
    bouguer_factor = 2.0 * math.pi * G_MGAL * depth_m

    rho_est = g_obs_mgal / bouguer_factor if bouguer_factor != 0 else background_density_kg_m3
    g_pred  = bouguer_factor * rho_est

    residual = abs(g_obs_mgal - g_pred)
    converged = residual <= tolerance

    # Uncertainty: a fixed 5% coefficient of variation for the classical solver
    rho_sigma = abs(rho_est) * 0.05 if rho_est else None

    return rho_est, rho_sigma, g_pred, converged, 1


def invert_gravity(
    cell_id: str,
    scan_id: str,
    g_obs_mgal: Optional[float],
    depth_m: float = 1000.0,
    background_density_kg_m3: float = 2670.0,
    max_iterations: int = 100,
    tolerance: float = 0.01,
    force_classical: bool = True,
) -> InversionResult:
    """
    Gravity inversion service entry point.

    Current behaviour: always uses classical fallback (force_classical=True).
    When QUANTUM_INVERSION_ENABLED flag is active (Phase Q+), the quantum
    path will be selectable here.

    Args:
        cell_id, scan_id:           Cell identity.
        g_obs_mgal:                 Observed composite gravity (mGal).
        depth_m:                    Target inversion depth (m).
        background_density_kg_m3:  Reference crustal density.
        max_iterations:             Solver iteration limit.
        tolerance:                  Convergence criterion (mGal).
        force_classical:            Always True until Phase Q.

    Returns:
        InversionResult with density estimate and predicted gravity.
    """
    rho_mean, rho_sigma, g_pred, converged, n_iter = _classical_inversion(
        g_obs_mgal=g_obs_mgal,
        depth_m=depth_m,
        background_density_kg_m3=background_density_kg_m3,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    residual_norm = abs(g_obs_mgal - g_pred) if g_obs_mgal is not None and g_pred is not None else None

    return InversionResult(
        cell_id=cell_id,
        scan_id=scan_id,
        rho_mean=rho_mean,
        rho_sigma=rho_sigma,
        g_pred=g_pred,
        mode=InversionMode.CLASSICAL,
        converged=converged,
        n_iterations=n_iter,
        residual_norm=residual_norm,
    )