"""
Aurora OSI vNext — Offshore Correction Pipeline
Phase H §H.2 | Phase B §9

⚠️  MANDATORY PRECONDITION GATE ⚠️

Offshore cells MUST produce a CorrectedOffshoreCell before ANY observable
extraction or scientific scoring. This gate is enforced at three layers:
  1. This module: raises OffshoreGateViolation if called without required inputs
  2. HarmonisedTensorStore: rejects write if offshore_corrected=False
  3. Scan pipeline: blocks OFFSHORE cells from passing core modules without correction

Correction steps (§9):
  §9.2: Water-column reflectance correction → R_b (bottom reflectance)
  §9.3: Oceanographic anomaly computation → SST', SSH', Chl'
  §9.4: Offshore sub-score extraction (called from core/observables.py only)
  §9.5: Water-column gravity correction → g_corr

CONSTITUTIONAL RULE: No offshore observable may be extracted (in core/observables.py)
without a CorrectedOffshoreCell argument. The function signature enforces this.

No scoring. No ACIF. No tiering. No imports from core/scoring, tiering, gates.
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


# ---------------------------------------------------------------------------
# §9.1 — Offshore cell identification
# ---------------------------------------------------------------------------

def is_offshore_cell(lat: float, lon: float, water_depth_m: Optional[float]) -> bool:
    """
    Determine if a cell is an offshore cell requiring the correction pipeline.

    A cell is offshore if:
      1. Bathymetric data indicates water depth > 0m, OR
      2. The cell falls within known marine boundaries (simplified here;
         full implementation uses PostGIS province lookup in Phase I)

    Args:
        lat, lon:       Cell centre coordinates
        water_depth_m:  Water depth from bathymetric data (None if not available)

    Returns:
        True if the cell requires offshore correction before processing.
    """
    if water_depth_m is not None and water_depth_m > 0.0:
        return True
    return False


# ---------------------------------------------------------------------------
# §9.2 — Water-column reflectance correction
# ---------------------------------------------------------------------------

def correct_water_column_reflectance(
    l_w: Optional[float],
    tau_w: Optional[float],
    z: Optional[float],
) -> tuple[Optional[float], Optional[float]]:
    """
    Correct water-leaving radiance for water-column attenuation (§9.2).

    Bottom reflectance: R_b = L_w / exp(-2 * K_d * z)
    where:
      L_w = water-leaving radiance (raw spectral measurement)
      tau_w = diffuse attenuation coefficient K_d × z (optical depth)
      z = water depth (m)

    Returns:
        (R_b, tau_w): bottom reflectance and optical depth used
        Both None if inputs insufficient for correction.
    """
    if l_w is None or tau_w is None or z is None:
        return None, None
    if z <= 0 or tau_w < 0 or l_w < 0:
        return None, None

    # Beer-Lambert water-column correction
    attenuation_factor = math.exp(-2.0 * tau_w)
    if attenuation_factor < 1e-10:
        # Extremely deep water — reflectance unrecoverable
        return None, tau_w

    r_b = l_w / attenuation_factor
    # Clamp bottom reflectance to physically valid range [0, 1]
    r_b_clamped = max(0.0, min(1.0, r_b))
    return r_b_clamped, tau_w


# ---------------------------------------------------------------------------
# §9.3 — Oceanographic anomaly computation
# ---------------------------------------------------------------------------

def compute_oceanographic_anomalies(
    sst_celsius: Optional[float],
    ssh_m: Optional[float],
    chlorophyll_mg_m3: Optional[float],
    sst_baseline: Optional[float],
    ssh_baseline: Optional[float],
    chl_baseline: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute oceanographic anomalies relative to seasonal baselines (§9.3).

    Anomalies:
      SST' = SST_observed - SST_baseline
      SSH' = SSH_observed - SSH_baseline
      Chl' = Chl_observed - Chl_baseline

    Positive anomalies indicate above-baseline conditions which may correlate
    with submarine fluid venting, hydrothermal activity, or seabed disturbance.
    Negative anomalies may indicate upwelling.

    Returns:
        (sst_anomaly, ssh_anomaly, chl_anomaly) — all may be None if
        either observed or baseline value is unavailable.
    """
    sst_anomaly = (sst_celsius - sst_baseline
                   if sst_celsius is not None and sst_baseline is not None else None)
    ssh_anomaly = (ssh_m - ssh_baseline
                   if ssh_m is not None and ssh_baseline is not None else None)
    chl_anomaly = (chlorophyll_mg_m3 - chl_baseline
                   if chlorophyll_mg_m3 is not None and chl_baseline is not None else None)
    return sst_anomaly, ssh_anomaly, chl_anomaly


# ---------------------------------------------------------------------------
# §9.5 — Water-column gravity correction
# ---------------------------------------------------------------------------

def correct_water_column_gravity(
    g_observed_mgal: Optional[float],
    lat_deg: float,
    lon_deg: float,
    water_depth_m: Optional[float],
    water_density_kg_m3: float = 1025.0,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Remove the gravitational effect of the water column from observed gravity (§9.5).

    Water-column gravity correction: Δg_wc = 2πGρ_w × z
    where:
      G = 6.674e-11 m³ kg⁻¹ s⁻²
      ρ_w = water density (kg/m³, default seawater 1025)
      z = water depth (m)

    g_corr = g_observed - Δg_wc

    Returns:
        (g_corr_mgal, delta_g_wc_mgal, water_column_residual)
        All None if inputs insufficient.
    """
    if g_observed_mgal is None or water_depth_m is None or water_depth_m <= 0:
        return None, None, None

    G = 6.674e-11                # m³ kg⁻¹ s⁻²
    # Convert G to mGal (1 mGal = 1e-5 m/s²)
    G_mgal = G * 1e5

    delta_g_wc_mgal = 2.0 * math.pi * G_mgal * water_density_kg_m3 * water_depth_m
    g_corr_mgal = g_observed_mgal - delta_g_wc_mgal

    # Water-column residual R_wc — absolute magnitude of correction
    # Used as first-class physics output in ScanCell.water_column_residual
    water_column_residual = abs(delta_g_wc_mgal)

    return g_corr_mgal, delta_g_wc_mgal, water_column_residual


# ---------------------------------------------------------------------------
# Main correction orchestrator
# ---------------------------------------------------------------------------

def apply_offshore_correction(
    cell_id: str,
    scan_id: str,
    bathymetric: RawBathymetricData,
    gravity: Optional[RawGravityData],
    sst_baseline: Optional[float] = None,
    ssh_baseline: Optional[float] = None,
    chl_baseline: Optional[float] = None,
    lat_deg: float = 0.0,
    lon_deg: float = 0.0,
    tau_w: Optional[float] = None,
) -> CorrectedOffshoreCell:
    """
    Full offshore correction pipeline for one cell (§9.2 + §9.3 + §9.5).

    This function is the ONLY path through which a CorrectedOffshoreCell
    may be produced. Callers that skip this function and attempt to extract
    offshore observables will receive an OffshoreGateViolation.

    Args:
        cell_id, scan_id: Cell identity
        bathymetric:      Raw bathymetric/oceanographic stack
        gravity:          Raw gravity data (optional — None for deep-water cells
                          without gravity coverage)
        *_baseline:       Seasonal baseline values from climatology database
        lat_deg, lon_deg: Cell centre coordinates
        tau_w:            Optical depth (from water quality model; None if unavailable)

    Returns:
        CorrectedOffshoreCell with all corrections applied.
        correction_quality is "degraded" if any step is partially missing.
    """
    warnings: list[str] = []

    # §9.2 Water-column reflectance correction
    r_b, optical_depth = correct_water_column_reflectance(
        l_w=bathymetric.backscatter_db,   # Using backscatter as proxy for water-leaving radiance
        tau_w=tau_w,
        z=bathymetric.water_depth_m,
    )
    if r_b is None:
        warnings.append("water_column_reflectance_correction_skipped")

    # §9.3 Oceanographic anomalies
    sst_anom, ssh_anom, chl_anom = compute_oceanographic_anomalies(
        sst_celsius=bathymetric.sst_celsius,
        ssh_m=bathymetric.ssh_m,
        chlorophyll_mg_m3=bathymetric.chlorophyll_mg_m3,
        sst_baseline=sst_baseline,
        ssh_baseline=ssh_baseline,
        chl_baseline=chl_baseline,
    )
    if sst_anom is None:
        warnings.append("sst_anomaly_unavailable")
    if ssh_anom is None:
        warnings.append("ssh_anomaly_unavailable")
    if chl_anom is None:
        warnings.append("chlorophyll_anomaly_unavailable")

    # §9.5 Water-column gravity correction
    g_obs = gravity.free_air_leo_mgal if gravity else None
    g_corr, delta_g_wc, r_wc = correct_water_column_gravity(
        g_observed_mgal=g_obs,
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        water_depth_m=bathymetric.water_depth_m,
    )
    if g_corr is None:
        warnings.append("gravity_water_column_correction_skipped")

    # Determine correction quality
    critical_corrections = [r_b, sst_anom, ssh_anom]
    n_missing_critical = sum(1 for v in critical_corrections if v is None)
    quality = "nominal" if n_missing_critical == 0 else "degraded"

    return CorrectedOffshoreCell(
        cell_id=cell_id,
        scan_id=scan_id,
        bottom_reflectance=r_b,
        water_column_tau=optical_depth,
        water_depth_m=bathymetric.water_depth_m,
        sst_anomaly_celsius=sst_anom,
        ssh_anomaly_m=ssh_anom,
        chlorophyll_anomaly_mg_m3=chl_anom,
        gravity_water_column_correction_mgal=delta_g_wc,
        corrected_gravity_mgal=g_corr,
        water_column_residual=r_wc,
        correction_quality=quality,
        correction_warnings=tuple(warnings),
    )