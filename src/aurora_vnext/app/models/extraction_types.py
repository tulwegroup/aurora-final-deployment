"""
Aurora OSI vNext — Extraction Intermediate Types
Phase H

Typed containers produced during the observable extraction pipeline.
These are TRANSIENT pipeline objects — they exist between pipeline stages
and are NOT persisted directly. Their final values are written to:
  - harmonised_tensors table (ObservableVector + normalisation params)
  - raw_observables table (raw sensor stacks)

No scoring. No ACIF. No tiering.
No imports from core/scoring.py, core/tiering.py, core/gates.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Raw sensor stacks (output of services/gee.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawOpticalStack:
    """
    Un-harmonised, un-normalised optical raster stack for one cell.
    Values are raw sensor digital numbers or TOA reflectance — NOT normalised.
    """
    cell_id: str
    scan_id: str
    mission: str                          # e.g. "Sentinel-2", "Landsat-9"
    scene_id: Optional[str]
    acquisition_date: Optional[str]
    # Band reflectance values keyed by band name (mission-specific)
    band_values: dict[str, Optional[float]] = field(default_factory=dict)
    cloud_cover_fraction: Optional[float] = None


@dataclass(frozen=True)
class RawSARStack:
    """Un-normalised SAR backscatter and coherence for one cell."""
    cell_id: str
    scan_id: str
    mission: str                          # e.g. "Sentinel-1", "ALOS-2"
    polarisation: str                     # e.g. "VV", "VH", "HH"
    backscatter_vv: Optional[float] = None
    backscatter_vh: Optional[float] = None
    coherence: Optional[float] = None
    incidence_angle_deg: Optional[float] = None
    acquisition_date: Optional[str] = None


@dataclass(frozen=True)
class RawThermalStack:
    """Un-normalised thermal infrared values for one cell."""
    cell_id: str
    scan_id: str
    mission: str
    lst_kelvin: Optional[float] = None          # Land surface temperature
    heat_flow_mw_m2: Optional[float] = None     # Geothermal heat flow
    thermal_inertia: Optional[float] = None
    emissivity: Optional[float] = None
    acquisition_date: Optional[str] = None


@dataclass(frozen=True)
class RawGravityData:
    """Raw gravity measurements for one cell (multi-orbit composite input)."""
    cell_id: str
    scan_id: str
    # Free-air anomaly in mGal from each orbit class
    free_air_leo_mgal: Optional[float] = None   # LEO (e.g. GRACE-FO)
    free_air_meo_mgal: Optional[float] = None   # MEO (e.g. GOCE)
    free_air_legacy_mgal: Optional[float] = None  # Legacy (e.g. EGM2008)
    # Bouguer anomaly
    bouguer_anomaly_mgal: Optional[float] = None
    # Vertical gravity gradient (Eötvös)
    vertical_gradient_eotvos: Optional[float] = None
    # Reference terrain (for Bouguer correction)
    terrain_elevation_m: Optional[float] = None


@dataclass(frozen=True)
class RawMagneticData:
    """Raw aeromagnetic and total-field magnetic data for one cell."""
    cell_id: str
    scan_id: str
    total_field_nt: Optional[float] = None
    rtp_anomaly_nt: Optional[float] = None          # Reduced-to-pole
    analytic_signal_nt_m: Optional[float] = None
    horizontal_derivative_nt_m: Optional[float] = None
    depth_to_source_m: Optional[float] = None


@dataclass(frozen=True)
class RawBathymetricData:
    """Raw bathymetric and oceanographic data for offshore cells."""
    cell_id: str
    scan_id: str
    water_depth_m: Optional[float] = None
    seafloor_slope_deg: Optional[float] = None
    sst_celsius: Optional[float] = None           # Sea surface temperature
    ssh_m: Optional[float] = None                 # Sea surface height
    chlorophyll_mg_m3: Optional[float] = None
    backscatter_db: Optional[float] = None        # Seafloor backscatter


# ---------------------------------------------------------------------------
# Offshore correction outputs (output of services/offshore.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CorrectedOffshoreCell:
    """
    Output of the offshore correction pipeline for one cell.
    This object is a MANDATORY GATE — offshore cells must produce a
    CorrectedOffshoreCell before observable extraction proceeds.

    Attempting to extract offshore observables from a raw cell without
    this correction object raises OffshoreGateViolation.
    """
    cell_id: str
    scan_id: str

    # Corrected reflectance (bottom reflectance after water-column removal, §9.2)
    bottom_reflectance: Optional[float]           # R_b
    water_column_tau: Optional[float]             # Optical depth τ_w
    water_depth_m: Optional[float]

    # Oceanographic anomalies (§9.3) — deviations from seasonal baseline
    sst_anomaly_celsius: Optional[float]          # SST' = SST - baseline
    ssh_anomaly_m: Optional[float]                # SSH'
    chlorophyll_anomaly_mg_m3: Optional[float]    # Chl'

    # Gravity correction (§9.5)
    gravity_water_column_correction_mgal: Optional[float]   # Δg_wc
    corrected_gravity_mgal: Optional[float]                 # g_corr = g_obs - Δg_wc

    # Water-column residual for physics module (first-class output)
    water_column_residual: Optional[float]                  # R_wc ≥ 0

    # Correction quality flags
    correction_quality: str = "nominal"           # "nominal" | "degraded" | "failed"
    correction_warnings: tuple[str, ...] = ()


class OffshoreGateViolation(Exception):
    """
    Raised when observable extraction is attempted on an offshore cell
    without a valid CorrectedOffshoreCell object.

    This is a constitutional enforcement — offshore cells must pass
    through services/offshore.py before any scientific processing.
    """


# ---------------------------------------------------------------------------
# Gravity decomposition output (output of services/gravity.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GravityComposite:
    """
    Multi-orbit gravity decomposition result for one cell (§6.3).
    Produced by services/gravity.py — consumed by core/physics.py.
    """
    cell_id: str
    scan_id: str

    # Wavelength-decomposed components
    g_long_mgal: Optional[float]          # Long-wavelength (MEO/legacy)
    g_medium_mgal: Optional[float]        # Medium-wavelength (LEO)
    g_short_mgal: Optional[float]         # Short-wavelength (super-resolved)
    g_composite_mgal: Optional[float]     # g_composite = g_long + g_medium + g_short

    # Vertical gradient used for short-wave super-resolution
    delta_h_m: Optional[float]            # Height separation between observing platforms

    # Quality metrics
    orbit_sources_used: tuple[str, ...] = ()   # e.g. ("LEO", "MEO", "legacy")
    super_resolution_applied: bool = False


# ---------------------------------------------------------------------------
# Normalisation parameters (per-scan, per-observable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservableNormParams:
    """
    Per-scan normalisation parameters μ_k, σ_k for one observable (§3.2).
    Computed from the full AOI population before any individual cell is normalised.
    Ensures comparable scaling across all cells in a scan.
    """
    observable_key: str                   # e.g. "x_spec_1"
    mu: float                             # Population mean across AOI
    sigma: float                          # Population standard deviation
    n_samples: int                        # Number of non-null cells used for estimation
    clamp_min: float = 0.0               # Normalised value floor
    clamp_max: float = 1.0               # Normalised value ceiling


@dataclass(frozen=True)
class ScanNormalisationParams:
    """
    Complete set of normalisation parameters for all 42 observables in one scan.
    Stored in canonical_scans.normalisation_params at canonical freeze.
    """
    scan_id: str
    params: dict[str, ObservableNormParams]    # observable_key → ObservableNormParams

    def get(self, key: str) -> Optional[ObservableNormParams]:
        return self.params.get(key)

    def as_jsonb_dict(self) -> dict[str, dict[str, float]]:
        """Serialise to JSONB-compatible dict for storage."""
        return {
            k: {"mu": v.mu, "sigma": v.sigma, "n_samples": v.n_samples}
            for k, v in self.params.items()
        }


# ---------------------------------------------------------------------------
# Missing data sentinel
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MissingObservable:
    """
    Represents a missing (null) observable measurement for one cell.
    Carrying explicit MissingObservable objects (rather than bare None) allows
    the pipeline to distinguish between:
      - None: observable not yet extracted
      - MissingObservable: explicitly missing — sensor absent, cloud, etc.

    The uncertainty module (core/uncertainty.py) consumes this to set u_sensor.
    """
    key: str                      # Observable field name e.g. "x_spec_1"
    reason: str                   # "cloud", "sensor_absent", "no_data", "offshore_uncorrected"
    normalised_value: float = 0.5  # §3.3: missing observables default to 0.5 (mid-range)
    u_sensor_contribution: float = 1.0  # §3.3: missing → full sensor uncertainty