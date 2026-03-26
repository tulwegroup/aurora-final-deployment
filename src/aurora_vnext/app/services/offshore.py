"""
Aurora OSI vNext — Offshore Correction Pipeline Service
Phase K §K.4 | Phase B §9

⚠️  MANDATORY PRECONDITION GATE ⚠️

OFFSHORE cells MUST produce a CorrectedOffshoreCell before ANY
observable extraction, harmonisation, or scientific processing.

Gate enforcement layers:
  1. This module:             raises OffshoreGateViolation on invalid inputs.
  2. services/harmonization:  raises OffshoreGateViolation if offshore and no correction.
  3. core/observables.py:     raises OffshoreGateViolation for offshore sub-score extraction.
  4. storage/scans.py:        rejects write if offshore_corrected=False in harmonised tensor.

Correction pipeline (§9):
  §9.2: Water-column reflectance correction   → R_b (bottom reflectance)
  §9.3: Oceanographic anomaly computation     → SST', SSH', Chl'
  §9.5: Water-column gravity correction       → g_corr, R_wc (first-class physics output)

Layer rule: This is a Layer-2 Service.
  - NO scoring, tiering, gates, or ACIF logic.
  - Produces ONLY CorrectedOffshoreCell (a raw corrected signal object).
  - water_column_residual is a FIRST-CLASS PHYSICS OUTPUT stored in ScanCell.

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.extraction_types import (
    CorrectedOffshoreCell,
    OffshoreGateViolation,
    RawBathymetricData,
    RawGravityData,
)

_G_SI    = 6.674e-11   # m³ kg⁻¹ s⁻²
_G_MGAL  = _G_SI * 1e5 # Converts to mGal units


def is_offshore_cell(water_depth_m: Optional[float]) -> bool:
    """Return True if the cell has positive water depth (offshore/seabed)."""
    return water_depth_m is not None and water_depth_m > 0.0


def correct_water_column_reflectance(
    l_w: Optional[float],
    tau_w: Optional[float],
    z: Optional[float],
) -> tuple[Optional[float], Optional[float]]:
    """
    §9.2 — Remove water-column attenuation from water-leaving radiance.

    R_b = L_w / exp(-2 × τ_w)
    where τ_w = K_d × z (optical depth).

    Returns:
        (R_b, tau_w_used) — bottom reflectance and optical depth.
        Both None if inputs insufficient or recovery impossible.
    """
    if l_w is None or tau_w is None or z is None:
        return None, None
    if z <= 0 or tau_w < 0 or l_w < 0:
        return None, None
    attenuation = math.exp(-2.0 * tau_w)
    if attenuation < 1e-10:
        return None, tau_w   # Unrecoverable: extreme optical depth
    r_b = max(0.0, min(1.0, l_w / attenuation))
    return r_b, tau_w


def compute_oceanographic_anomalies(
    sst_celsius: Optional[float],
    ssh_m: Optional[float],
    chlorophyll_mg_m3: Optional[float],
    sst_baseline: Optional[float],
    ssh_baseline: Optional[float],
    chl_baseline: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    §9.3 — Compute oceanographic anomalies vs. seasonal baselines.

    SST' = SST_obs - SST_baseline
    SSH' = SSH_obs - SSH_baseline
    Chl' = Chl_obs - Chl_baseline

    Returns:
        (sst_anomaly, ssh_anomaly, chl_anomaly) — any may be None.
    """
    sst_a = (sst_celsius - sst_baseline
             if sst_celsius is not None and sst_baseline is not None else None)
    ssh_a = (ssh_m - ssh_baseline
             if ssh_m is not None and ssh_baseline is not None else None)
    chl_a = (chlorophyll_mg_m3 - chl_baseline
             if chlorophyll_mg_m3 is not None and chl_baseline is not None else None)
    return sst_a, ssh_a, chl_a


def correct_water_column_gravity(
    g_observed_mgal: Optional[float],
    water_depth_m: Optional[float],
    water_density_kg_m3: float = 1025.0,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    §9.5 — Remove gravitational effect of the water column.

    Δg_wc = 2πGρ_w × z   [mGal]
    g_corr = g_observed - Δg_wc
    R_wc = |Δg_wc|   (first-class physics output stored in ScanCell)

    Returns:
        (g_corr_mgal, delta_g_wc_mgal, water_column_residual)
        All None if inputs insufficient.
    """
    if g_observed_mgal is None or water_depth_m is None or water_depth_m <= 0:
        return None, None, None
    delta_g_wc = 2.0 * math.pi * _G_MGAL * water_density_kg_m3 * water_depth_m
    g_corr = g_observed_mgal - delta_g_wc
    return g_corr, delta_g_wc, abs(delta_g_wc)


def apply_offshore_correction(
    cell_id: str,
    scan_id: str,
    bathymetric: RawBathymetricData,
    gravity: Optional[RawGravityData] = None,
    sst_baseline: Optional[float] = None,
    ssh_baseline: Optional[float] = None,
    chl_baseline: Optional[float] = None,
    tau_w: Optional[float] = None,
) -> CorrectedOffshoreCell:
    """
    Full offshore correction pipeline for one cell.

    Orchestrates §9.2 + §9.3 + §9.5. This is the ONLY path through which
    a CorrectedOffshoreCell may be produced. Any attempt to call
    harmonisation or sub-score extraction for an offshore cell without
    first calling this function will raise OffshoreGateViolation.

    Returns:
        CorrectedOffshoreCell — GATE PROOF OBJECT for downstream services.
    """
    if bathymetric is None:
        raise OffshoreGateViolation(
            f"Cell {cell_id}: apply_offshore_correction requires RawBathymetricData."
        )

    warnings: list[str] = []

    # §9.2 Water-column reflectance correction
    r_b, optical_depth = correct_water_column_reflectance(
        l_w=bathymetric.backscatter_db,
        tau_w=tau_w,
        z=bathymetric.water_depth_m,
    )
    if r_b is None:
        warnings.append("water_column_reflectance_correction_skipped")

    # §9.3 Oceanographic anomalies
    sst_a, ssh_a, chl_a = compute_oceanographic_anomalies(
        sst_celsius=bathymetric.sst_celsius,
        ssh_m=bathymetric.ssh_m,
        chlorophyll_mg_m3=bathymetric.chlorophyll_mg_m3,
        sst_baseline=sst_baseline,
        ssh_baseline=ssh_baseline,
        chl_baseline=chl_baseline,
    )
    if sst_a is None: warnings.append("sst_anomaly_unavailable")
    if ssh_a is None: warnings.append("ssh_anomaly_unavailable")
    if chl_a is None: warnings.append("chlorophyll_anomaly_unavailable")

    # §9.5 Water-column gravity correction
    g_obs = gravity.free_air_leo_mgal if gravity else None
    g_corr, delta_g_wc, r_wc = correct_water_column_gravity(
        g_observed_mgal=g_obs,
        water_depth_m=bathymetric.water_depth_m,
    )
    if g_corr is None:
        warnings.append("gravity_water_column_correction_skipped")

    # Correction quality classification
    critical = [r_b, sst_a, ssh_a]
    n_missing = sum(1 for v in critical if v is None)
    quality = "nominal" if n_missing == 0 else "degraded"

    return CorrectedOffshoreCell(
        cell_id=cell_id,
        scan_id=scan_id,
        bottom_reflectance=r_b,
        water_column_tau=optical_depth,
        water_depth_m=bathymetric.water_depth_m,
        sst_anomaly_celsius=sst_a,
        ssh_anomaly_m=ssh_a,
        chlorophyll_anomaly_mg_m3=chl_a,
        gravity_water_column_correction_mgal=delta_g_wc,
        corrected_gravity_mgal=g_corr,
        water_column_residual=r_wc,
        correction_quality=quality,
        correction_warnings=tuple(warnings),
    )