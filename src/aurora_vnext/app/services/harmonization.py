"""
Aurora OSI vNext — Cross-Mission Sensor Harmonisation Service
Phase H §H.4 | Patent Breakthrough 10

Converts raw sensor observations from ANY satellite mission into a
universal, normalised feature tensor keyed by the 42 ObservableVector fields.

Harmonisation is MISSION-NEUTRAL — the pipeline never sees mission-specific
band names after this stage. All downstream scientific modules operate on
the canonical 42-observable vocabulary.

Two-stage process:
  Stage 1 (mission_to_canonical): Convert mission-specific band readings to
           canonical observable keys using per-mission spectral mappings.
  Stage 2 (build_universal_feature_tensor): Aggregate harmonised values from
           multiple missions for the same cell; compute final raw feature tensor.

The feature tensor is RAW (un-normalised). Normalisation is applied separately
by core/normalisation.py after per-scan μ_k, σ_k are computed across the AOI.

Environmental regime modifiers for offshore cells are applied here —
weighting the x_off_* observables more heavily relative to spectral features
for offshore commodity scans.

No scoring. No ACIF. No tiering. No imports from core/scoring, tiering, gates.
"""

from __future__ import annotations

from typing import Optional

from app.models.extraction_types import (
    CorrectedOffshoreCell,
    GravityComposite,
    OffshoreGateViolation,
    RawBathymetricData,
    RawGravityData,
    RawMagneticData,
    RawOpticalStack,
    RawSARStack,
    RawThermalStack,
)


# ---------------------------------------------------------------------------
# Mission-specific spectral mappings
# Maps {mission_name: {observable_key: band_name}}
# ---------------------------------------------------------------------------

MISSION_BAND_MAP: dict[str, dict[str, str]] = {
    "Sentinel-2": {
        "x_spec_1": "B2",   # Blue 490nm
        "x_spec_2": "B3",   # Green 560nm
        "x_spec_3": "B4",   # Red 665nm
        "x_spec_4": "B5",   # Red Edge 1 705nm
        "x_spec_5": "B8",   # NIR 842nm
        "x_spec_6": "B8A",  # NIR narrow 865nm
        "x_spec_7": "B11",  # SWIR 1 1610nm
        "x_spec_8": "B12",  # SWIR 2 2190nm
    },
    "Landsat-9": {
        "x_spec_1": "B2",   # Blue 482nm
        "x_spec_2": "B3",   # Green 562nm
        "x_spec_3": "B4",   # Red 655nm
        "x_spec_4": "B5",   # NIR 865nm
        "x_spec_5": "B5",   # NIR (no red-edge equivalent — duplicate NIR)
        "x_spec_6": "B5",   # NIR
        "x_spec_7": "B6",   # SWIR 1 1610nm
        "x_spec_8": "B7",   # SWIR 2 2200nm
    },
    "Sentinel-1": {
        "x_sar_1": "VV",    # VV backscatter
        "x_sar_2": "VH",    # VH backscatter
        "x_sar_3": "coherence",
    },
    "ALOS-2": {
        "x_sar_1": "HH",
        "x_sar_2": "HV",
    },
    "ASTER": {
        "x_therm_1": "TIR1",
        "x_therm_2": "TIR2",
        "x_therm_3": "TIR3",
        "x_therm_4": "TIR4",
    },
    "ECOSTRESS": {
        "x_therm_1": "LST",
    },
}


# ---------------------------------------------------------------------------
# Stage 1: Mission-to-canonical translation
# ---------------------------------------------------------------------------

def translate_optical_to_canonical(
    stack: RawOpticalStack,
) -> dict[str, Optional[float]]:
    """
    Map mission-specific optical band values to canonical x_spec_* keys.

    Returns dict with keys matching ObservableVector x_spec_* fields.
    Missing bands produce None (not zero).
    """
    result: dict[str, Optional[float]] = {}
    mission_map = MISSION_BAND_MAP.get(stack.mission, {})
    for obs_key, band_name in mission_map.items():
        if obs_key.startswith("x_spec_"):
            result[obs_key] = stack.band_values.get(band_name)
    return result


def translate_sar_to_canonical(
    stack: RawSARStack,
) -> dict[str, Optional[float]]:
    """Map SAR measurements to canonical x_sar_* keys."""
    result: dict[str, Optional[float]] = {
        "x_sar_1": None, "x_sar_2": None, "x_sar_3": None,
        "x_sar_4": None, "x_sar_5": None, "x_sar_6": None,
    }
    if stack.polarisation in ("VV", "HH"):
        result["x_sar_1"] = stack.backscatter_vv or stack.backscatter_vv
    if stack.polarisation in ("VH", "HV"):
        result["x_sar_2"] = stack.backscatter_vh
    result["x_sar_3"] = stack.coherence
    result["x_sar_4"] = stack.incidence_angle_deg
    return result


def translate_thermal_to_canonical(
    stack: RawThermalStack,
) -> dict[str, Optional[float]]:
    """Map thermal measurements to canonical x_therm_* keys."""
    return {
        "x_therm_1": stack.lst_kelvin,
        "x_therm_2": stack.heat_flow_mw_m2,
        "x_therm_3": stack.thermal_inertia,
        "x_therm_4": stack.emissivity,
    }


def translate_gravity_to_canonical(
    composite: GravityComposite,
    raw: RawGravityData,
) -> dict[str, Optional[float]]:
    """Map gravity decomposition outputs to canonical x_grav_* keys."""
    return {
        "x_grav_1": composite.g_composite_mgal,       # Composite gravity anomaly
        "x_grav_2": raw.bouguer_anomaly_mgal,          # Bouguer anomaly
        "x_grav_3": composite.g_long_mgal,             # Long-wavelength component
        "x_grav_4": composite.g_medium_mgal,           # Medium-wavelength component
        "x_grav_5": composite.g_short_mgal,            # Super-resolved short-wavelength
        "x_grav_6": raw.vertical_gradient_eotvos,      # Vertical gradient tensor Γ_zz
    }


def translate_magnetic_to_canonical(
    mag: RawMagneticData,
) -> dict[str, Optional[float]]:
    """Map magnetic measurements to canonical x_mag_* keys."""
    return {
        "x_mag_1": mag.total_field_nt,
        "x_mag_2": mag.rtp_anomaly_nt,
        "x_mag_3": mag.analytic_signal_nt_m,
        "x_mag_4": mag.horizontal_derivative_nt_m,
        "x_mag_5": mag.depth_to_source_m,
    }


def translate_offshore_corrected_to_canonical(
    corrected: CorrectedOffshoreCell,
) -> dict[str, Optional[float]]:
    """
    Map corrected offshore values to canonical x_off_* keys.

    CONSTITUTIONAL RULE: This translation may only be called with a
    CorrectedOffshoreCell — never with raw bathymetric data.
    The presence of the CorrectedOffshoreCell object IS the gate proof.
    """
    return {
        "x_off_1": corrected.bottom_reflectance,
        "x_off_2": corrected.sst_anomaly_celsius,
        "x_off_3": corrected.ssh_anomaly_m,
        "x_off_4": corrected.chlorophyll_anomaly_mg_m3,
    }


# ---------------------------------------------------------------------------
# Stage 2: Universal feature tensor assembly
# ---------------------------------------------------------------------------

def build_universal_feature_tensor(
    cell_id: str,
    optical_stacks: list[RawOpticalStack] | None = None,
    sar_stacks: list[RawSARStack] | None = None,
    thermal_stacks: list[RawThermalStack] | None = None,
    gravity_composite: Optional[GravityComposite] = None,
    raw_gravity: Optional[RawGravityData] = None,
    magnetic: Optional[RawMagneticData] = None,
    corrected_offshore: Optional[CorrectedOffshoreCell] = None,
    environment: str = "ONSHORE",
    structural_features: Optional[dict[str, Optional[float]]] = None,
    hydro_features: Optional[dict[str, Optional[float]]] = None,
    environmental_modifier: Optional[dict[str, float]] = None,
) -> dict[str, Optional[float]]:
    """
    Build the universal 42-key feature tensor for one cell.

    This is the output of harmonisation — a dict keyed by all 42
    ObservableVector field names, with raw (un-normalised) values or None.

    Multi-mission fusion: when multiple optical or SAR stacks are available,
    the value with lowest cloud cover / best quality is preferred.
    Future: ensemble averaging with quality weights.

    Environmental modifier: applies multiplicative scaling to specific
    observables based on the commodity's environmental regime. For offshore
    scans, x_off_* observables receive higher priority (modifier > 1.0);
    for onshore scans, x_off_* are set to None regardless of inputs.

    Args:
        corrected_offshore: REQUIRED for offshore cells. Raises OffshoreGateViolation
                            if environment=OFFSHORE and this is None.

    Returns:
        dict[str, Optional[float]] with all 42 keys present.
    """
    if environment == "OFFSHORE" and corrected_offshore is None:
        raise OffshoreGateViolation(
            f"Cell {cell_id}: build_universal_feature_tensor called with "
            f"environment=OFFSHORE but no CorrectedOffshoreCell provided. "
            f"services/offshore.apply_offshore_correction() must be called first."
        )

    # Initialise all 42 keys to None
    tensor: dict[str, Optional[float]] = {
        "x_spec_1": None, "x_spec_2": None, "x_spec_3": None, "x_spec_4": None,
        "x_spec_5": None, "x_spec_6": None, "x_spec_7": None, "x_spec_8": None,
        "x_sar_1": None,  "x_sar_2": None,  "x_sar_3": None,  "x_sar_4": None,
        "x_sar_5": None,  "x_sar_6": None,
        "x_therm_1": None, "x_therm_2": None, "x_therm_3": None, "x_therm_4": None,
        "x_grav_1": None, "x_grav_2": None, "x_grav_3": None, "x_grav_4": None,
        "x_grav_5": None, "x_grav_6": None,
        "x_mag_1": None,  "x_mag_2": None,  "x_mag_3": None,  "x_mag_4": None,
        "x_mag_5": None,
        "x_struct_1": None, "x_struct_2": None, "x_struct_3": None,
        "x_struct_4": None, "x_struct_5": None,
        "x_hydro_1": None, "x_hydro_2": None, "x_hydro_3": None, "x_hydro_4": None,
        "x_off_1": None,  "x_off_2": None,  "x_off_3": None,  "x_off_4": None,
    }

    # Optical: use best-quality stack (lowest cloud cover)
    if optical_stacks:
        best = min(
            optical_stacks,
            key=lambda s: s.cloud_cover_fraction or 1.0,
        )
        tensor.update({k: v for k, v in translate_optical_to_canonical(best).items() if v is not None})

    # SAR: merge across stacks (different polarisations from same or different missions)
    if sar_stacks:
        for sar in sar_stacks:
            translated = translate_sar_to_canonical(sar)
            for k, v in translated.items():
                if v is not None and tensor.get(k) is None:
                    tensor[k] = v

    # Thermal
    if thermal_stacks:
        best_thermal = thermal_stacks[0]
        tensor.update({k: v for k, v in translate_thermal_to_canonical(best_thermal).items() if v is not None})

    # Gravity
    if gravity_composite and raw_gravity:
        tensor.update({k: v for k, v in translate_gravity_to_canonical(gravity_composite, raw_gravity).items() if v is not None})

    # Magnetic
    if magnetic:
        tensor.update({k: v for k, v in translate_magnetic_to_canonical(magnetic).items() if v is not None})

    # Structural (pre-computed from DEM / lineament analysis)
    if structural_features:
        for k in ("x_struct_1", "x_struct_2", "x_struct_3", "x_struct_4", "x_struct_5"):
            if k in structural_features:
                tensor[k] = structural_features[k]

    # Hydrological (pre-computed from soil moisture / drainage models)
    if hydro_features:
        for k in ("x_hydro_1", "x_hydro_2", "x_hydro_3", "x_hydro_4"):
            if k in hydro_features:
                tensor[k] = hydro_features[k]

    # Offshore: only populate x_off_* for offshore cells with valid correction
    if environment == "OFFSHORE" and corrected_offshore is not None:
        tensor.update(translate_offshore_corrected_to_canonical(corrected_offshore))
    else:
        # Onshore cells: offshore observables remain None
        tensor["x_off_1"] = None
        tensor["x_off_2"] = None
        tensor["x_off_3"] = None
        tensor["x_off_4"] = None

    # Apply environmental regime modifier (multiplicative scaling on specific keys)
    if environmental_modifier:
        for key, modifier in environmental_modifier.items():
            if key in tensor and tensor[key] is not None:
                tensor[key] = tensor[key] * modifier  # type: ignore

    assert len(tensor) == 42, f"Feature tensor must have 42 keys, got {len(tensor)}"
    return tensor