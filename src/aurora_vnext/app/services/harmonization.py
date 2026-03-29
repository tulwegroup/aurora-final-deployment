"""
Aurora OSI vNext — Cross-Mission Sensor Harmonisation Service
Phase K §K.2 | Patent Breakthrough 10

Responsibility: Convert all raw sensor stacks into the canonical 42-observable
feature tensor keyed by ObservableVector field names.

Layer rule: This is a Layer-2 Service.
  - NO scoring, tiering, gates, or ACIF logic.
  - Output is a raw (un-normalised) feature tensor ONLY.
  - Normalisation is applied downstream by core/normalisation.py.

Harmonisation is MISSION-NEUTRAL: after this stage, all downstream
scientific modules operate on the canonical 42-observable vocabulary only.

Two-stage process:
  Stage 1: mission_to_canonical — convert mission-specific band names
           to canonical observable keys via MISSION_BAND_MAP.
  Stage 2: build_universal_feature_tensor — aggregate across missions,
           fuse multi-source inputs, apply environmental modifiers.

Environmental regime modifiers (from commodity library):
  For OFFSHORE cells: x_off_* observables weighted > 1.0.
  For ONSHORE cells: x_off_* fields forced to None regardless of inputs.
  The modifier is multiplicative — never additive.

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.models.extraction_types import (
    CorrectedOffshoreCell,
    GravityComposite,
    OffshoreGateViolation,
    RawGravityData,
    RawMagneticData,
    RawOpticalStack,
    RawSARStack,
    RawThermalStack,
)
from app.services.spectral_extraction import extract_spectral_indices_from_s2_bands
        "x_spec_5": "B5",   # NIR     865 nm
        "x_spec_6": "B5",   # NIRn    865 nm (no equivalent)
        "x_spec_7": "B6",   # SWIR1  1610 nm
        "x_spec_8": "B7",   # SWIR2  2200 nm
    },
    "Sentinel-1": {
        "x_sar_1": "VV",
        "x_sar_2": "VH",
        "x_sar_3": "coherence",
        "x_sar_4": "incidence_angle",
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

# All 42 canonical observable keys in field order
CANONICAL_KEYS: tuple[str, ...] = (
    "x_spec_1", "x_spec_2", "x_spec_3", "x_spec_4",
    "x_spec_5", "x_spec_6", "x_spec_7", "x_spec_8",
    "x_sar_1",  "x_sar_2",  "x_sar_3",  "x_sar_4",  "x_sar_5",  "x_sar_6",
    "x_therm_1","x_therm_2","x_therm_3","x_therm_4",
    "x_grav_1", "x_grav_2", "x_grav_3", "x_grav_4", "x_grav_5", "x_grav_6",
    "x_mag_1",  "x_mag_2",  "x_mag_3",  "x_mag_4",  "x_mag_5",
    "x_struct_1","x_struct_2","x_struct_3","x_struct_4","x_struct_5",
    "x_hydro_1","x_hydro_2","x_hydro_3","x_hydro_4",
    "x_off_1",  "x_off_2",  "x_off_3",  "x_off_4",
)
assert len(CANONICAL_KEYS) == 42


# ---------------------------------------------------------------------------
# Stage 1: Mission-to-canonical translators
# ---------------------------------------------------------------------------

def translate_optical(stack: RawOpticalStack) -> dict[str, Optional[float]]:
    """
    Map mission-specific optical bands to canonical x_spec_* keys.
    
    CONSTITUTIONAL BRIDGE: For Sentinel-2, extract spectral indices from raw bands.
    For other missions, use mission-specific band mappings only.
    """
    result: dict[str, Optional[float]] = {}
    
    # Sentinel-2: extract spectral indices (clay, ferric, NDVI, etc.) from raw bands
    if stack.mission == "Sentinel-2":
        b4 = stack.band_values.get("B4")
        b8 = stack.band_values.get("B8")
        b11 = stack.band_values.get("B11")
        b12 = stack.band_values.get("B12")
        
        indices = extract_spectral_indices_from_s2_bands(b4, b8, b11, b12)
        for key, val in indices.items():
            result[key] = val
    else:
        # Other missions: use mission-specific band mappings only
        mission_map = MISSION_BAND_MAP.get(stack.mission, {})
        for obs_key, band_name in mission_map.items():
            if obs_key.startswith("x_spec_"):
                result[obs_key] = stack.band_values.get(band_name)
    
    return result


def translate_thermal(stack: RawThermalStack) -> dict[str, Optional[float]]:
    """Map thermal observations to canonical x_therm_* keys."""
    return {
        "x_therm_1": stack.lst_kelvin,
        "x_therm_2": stack.heat_flow_mw_m2,
        "x_therm_3": stack.thermal_inertia,
        "x_therm_4": stack.emissivity,
    }


def translate_gravity(
    composite: GravityComposite,
    raw: RawGravityData,
) -> dict[str, Optional[float]]:
    """Map gravity decomposition outputs to canonical x_grav_* keys."""
    return {
        "x_grav_1": composite.g_composite_mgal,
        "x_grav_2": raw.bouguer_anomaly_mgal,
        "x_grav_3": composite.g_long_mgal,
        "x_grav_4": composite.g_medium_mgal,
        "x_grav_5": composite.g_short_mgal,
        "x_grav_6": raw.vertical_gradient_eotvos,
    }


def translate_magnetic(mag: RawMagneticData) -> dict[str, Optional[float]]:
    """Map magnetic measurements to canonical x_mag_* keys."""
    return {
        "x_mag_1": mag.total_field_nt,
        "x_mag_2": mag.rtp_anomaly_nt,
        "x_mag_3": mag.analytic_signal_nt_m,
        "x_mag_4": mag.horizontal_derivative_nt_m,
        "x_mag_5": mag.depth_to_source_m,
    }


def translate_offshore_corrected(corrected: CorrectedOffshoreCell) -> dict[str, Optional[float]]:
    """
    Map corrected offshore outputs to canonical x_off_* keys.
    CONSTITUTIONAL: Only callable with a CorrectedOffshoreCell — never with raw bathy.
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

@dataclass(frozen=True)
class HarmonisedTensor:
    """
    Output of the harmonisation service for one cell.
    Contains the raw (un-normalised) 42-key feature tensor plus metadata.
    """
    cell_id: str
    scan_id: str
    environment: str
    feature_tensor: dict[str, Optional[float]]   # 42 keys, raw values
    missions_used: tuple[str, ...]
    correction_quality: Optional[str]             # from CorrectedOffshoreCell if offshore
    offshore_corrected: bool

    def __post_init__(self) -> None:
        if len(self.feature_tensor) != 42:
            raise ValueError(
                f"HarmonisedTensor must have exactly 42 keys, got {len(self.feature_tensor)}"
            )

    @property
    def present_count(self) -> int:
        return sum(1 for v in self.feature_tensor.values() if v is not None)

    @property
    def coverage_fraction(self) -> float:
        return self.present_count / 42


def build_harmonised_tensor(
    cell_id: str,
    scan_id: str,
    environment: str,
    optical_stacks: Optional[list[RawOpticalStack]] = None,
    sar_stacks: Optional[list[RawSARStack]] = None,
    thermal_stacks: Optional[list[RawThermalStack]] = None,
    gravity_composite: Optional[GravityComposite] = None,
    raw_gravity: Optional[RawGravityData] = None,
    magnetic: Optional[RawMagneticData] = None,
    corrected_offshore: Optional[CorrectedOffshoreCell] = None,
    structural_features: Optional[dict[str, Optional[float]]] = None,
    hydro_features: Optional[dict[str, Optional[float]]] = None,
    environmental_modifier: Optional[dict[str, float]] = None,
) -> HarmonisedTensor:
    """
    Build the canonical 42-key raw feature tensor for one cell.

    OFFSHORE GATE: Raises OffshoreGateViolation if environment=OFFSHORE
    and no CorrectedOffshoreCell is provided.

    Multi-mission fusion: best-quality optical (lowest cloud cover);
    SAR stacks merged across polarisations.

    Environmental regime modifier: multiplicative scaling on specific keys.
    Applied AFTER all translations — never before.

    Returns:
        HarmonisedTensor with all 42 keys and coverage metadata.
    """
    if environment == "OFFSHORE" and corrected_offshore is None:
        raise OffshoreGateViolation(
            f"Cell {cell_id}: build_harmonised_tensor called with environment=OFFSHORE "
            f"but no CorrectedOffshoreCell provided. services/offshore.apply_offshore_correction() "
            f"must be called first."
        )

    # Initialise all 42 keys to None
    tensor: dict[str, Optional[float]] = {k: None for k in CANONICAL_KEYS}
    missions_used: list[str] = []

    # Optical: best-quality stack
    if optical_stacks:
        best = min(optical_stacks, key=lambda s: s.cloud_cover_fraction or 1.0)
        for k, v in translate_optical(best).items():
            if v is not None:
                tensor[k] = v
        missions_used.append(best.mission)

    # SAR: merge across stacks
    if sar_stacks:
        for sar in sar_stacks:
            for k, v in translate_sar(sar).items():
                if v is not None and tensor.get(k) is None:
                    tensor[k] = v
            missions_used.append(sar.mission)

    # Thermal: best available
    if thermal_stacks:
        for k, v in translate_thermal(thermal_stacks[0]).items():
            if v is not None:
                tensor[k] = v
        missions_used.append(thermal_stacks[0].mission)

    # Gravity
    if gravity_composite and raw_gravity:
        for k, v in translate_gravity(gravity_composite, raw_gravity).items():
            if v is not None:
                tensor[k] = v

    # Magnetic
    if magnetic:
        for k, v in translate_magnetic(magnetic).items():
            if v is not None:
                tensor[k] = v

    # Structural (pre-computed, passed in)
    if structural_features:
        for k in ("x_struct_1","x_struct_2","x_struct_3","x_struct_4","x_struct_5"):
            if k in structural_features:
                tensor[k] = structural_features[k]

    # Hydrological (pre-computed, passed in)
    if hydro_features:
        for k in ("x_hydro_1","x_hydro_2","x_hydro_3","x_hydro_4"):
            if k in hydro_features:
                tensor[k] = hydro_features[k]

    # Offshore observables: ONLY from CorrectedOffshoreCell
    if environment == "OFFSHORE" and corrected_offshore is not None:
        for k, v in translate_offshore_corrected(corrected_offshore).items():
            tensor[k] = v
        correction_quality = corrected_offshore.correction_quality
        offshore_corrected = True
    else:
        # Force x_off_* to None for non-offshore cells
        for k in ("x_off_1","x_off_2","x_off_3","x_off_4"):
            tensor[k] = None
        correction_quality = None
        offshore_corrected = False

    # Environmental regime modifier (multiplicative)
    if environmental_modifier:
        for key, modifier in environmental_modifier.items():
            if key in tensor and tensor[key] is not None:
                tensor[key] = tensor[key] * modifier  # type: ignore

    return HarmonisedTensor(
        cell_id=cell_id,
        scan_id=scan_id,
        environment=environment,
        feature_tensor=dict(tensor),
        missions_used=tuple(dict.fromkeys(missions_used)),
        correction_quality=correction_quality,
        offshore_corrected=offshore_corrected,
    )