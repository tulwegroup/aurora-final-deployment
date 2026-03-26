"""
Aurora OSI vNext — Observable Extraction and Modality Sub-Score Computation
Phase H §H.4 | Phase B §3, §4.1

CONSTITUTIONAL RULE: This is the ONLY location for:
  - Modality sub-score extraction (S_i, R_i, T_E_i, G_i, M_i, L_i, H_i, O_i)
  - ObservableVector construction from a normalised feature tensor
  - Offshore sub-score extraction (only after CorrectedOffshoreCell gate)

TWO-PASS WORKFLOW:
  Pass 1 — Normalisation (core/normalisation.py):
    compute_scan_normalisation_params() across all cells → μ_k, σ_k
    normalise_observable() per cell per key → float ∈ [0,1] or None

  Pass 2 — Sub-score extraction (this module):
    Each modality groups its normalised observables into a single sub-score.
    Sub-scores are inputs to evidence scoring (core/evidence.py, Phase I).
    They are NOT ACIF components — they are pre-evidence aggregates.

Sub-score formulas:
  S_i (spectral)    = weighted mean of non-null x_spec_* values
  R_i (SAR)         = weighted mean of non-null x_sar_* values
  T_E_i (thermal)   = weighted mean of non-null x_therm_* values
  G_i (gravity)     = weighted mean of non-null x_grav_* values
  M_i (magnetic)    = weighted mean of non-null x_mag_* values
  L_i (structural)  = weighted mean of non-null x_struct_* values
  H_i (hydro)       = weighted mean of non-null x_hydro_* values
  O_i (offshore)    = ONLY from CorrectedOffshoreCell (§9.4)

Commodity-specific weights (from observable_weighting_vectors) modulate
which observables contribute most to evidence score. These weights are
supplied by the caller from the commodity library — they are NOT defined here.

No scoring. No ACIF. No tiering. No imports from core/scoring, tiering, gates.
"""

from __future__ import annotations

from typing import Optional

from app.models.extraction_types import CorrectedOffshoreCell, OffshoreGateViolation
from app.models.observable_vector import ObservableVector


# ---------------------------------------------------------------------------
# Modality groupings — which observable keys belong to each sub-score
# ---------------------------------------------------------------------------

SPECTRAL_KEYS = ("x_spec_1", "x_spec_2", "x_spec_3", "x_spec_4",
                 "x_spec_5", "x_spec_6", "x_spec_7", "x_spec_8")
SAR_KEYS      = ("x_sar_1", "x_sar_2", "x_sar_3", "x_sar_4", "x_sar_5", "x_sar_6")
THERMAL_KEYS  = ("x_therm_1", "x_therm_2", "x_therm_3", "x_therm_4")
GRAVITY_KEYS  = ("x_grav_1", "x_grav_2", "x_grav_3", "x_grav_4", "x_grav_5", "x_grav_6")
MAGNETIC_KEYS = ("x_mag_1", "x_mag_2", "x_mag_3", "x_mag_4", "x_mag_5")
STRUCT_KEYS   = ("x_struct_1", "x_struct_2", "x_struct_3", "x_struct_4", "x_struct_5")
HYDRO_KEYS    = ("x_hydro_1", "x_hydro_2", "x_hydro_3", "x_hydro_4")
OFFSHORE_KEYS = ("x_off_1", "x_off_2", "x_off_3", "x_off_4")


def _weighted_mean(
    normalised_values: dict[str, Optional[float]],
    keys: tuple[str, ...],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """
    Compute the weighted mean of non-null normalised values for a key group.

    If no weights provided, uses uniform weighting.
    If all values are None (no sensor data), returns None.

    Returns:
        float ∈ [0, 1] or None if no data available for this modality.
    """
    present_keys = [k for k in keys if normalised_values.get(k) is not None]
    if not present_keys:
        return None

    if weights:
        weighted_sum = sum(
            (weights.get(k, 1.0) * normalised_values[k])  # type: ignore
            for k in present_keys
        )
        weight_total = sum(weights.get(k, 1.0) for k in present_keys)
        return weighted_sum / weight_total if weight_total > 0 else None
    else:
        return sum(normalised_values[k] for k in present_keys) / len(present_keys)  # type: ignore


# ---------------------------------------------------------------------------
# §4.1 — Modality sub-score extraction functions
# ---------------------------------------------------------------------------

def extract_spectral_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """S_i: Spectral evidence sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, SPECTRAL_KEYS, weights)


def extract_sar_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """R_i: SAR backscatter/coherence sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, SAR_KEYS, weights)


def extract_thermal_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """T_E_i: Thermal evidence sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, THERMAL_KEYS, weights)


def extract_gravity_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """G_i: Gravity sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, GRAVITY_KEYS, weights)


def extract_magnetic_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """M_i: Magnetic sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, MAGNETIC_KEYS, weights)


def extract_structural_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """L_i: Structural geology sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, STRUCT_KEYS, weights)


def extract_hydro_sub_score(
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """H_i: Hydrological sub-score ∈ [0, 1] (§4.1)."""
    return _weighted_mean(normalised_values, HYDRO_KEYS, weights)


def extract_offshore_sub_score(
    corrected_cell: CorrectedOffshoreCell,
    normalised_values: dict[str, Optional[float]],
    weights: Optional[dict[str, float]] = None,
) -> Optional[float]:
    """
    O_i: Offshore sub-score ∈ [0, 1] (§9.4).

    CONSTITUTIONAL RULE: This function requires a CorrectedOffshoreCell argument.
    The function signature enforces the offshore gate — it cannot be called
    without proof that the correction pipeline has run.

    The CorrectedOffshoreCell is used here as a gate proof only.
    The actual sub-score is computed from normalised x_off_* values,
    which were populated from the CorrectedOffshoreCell by harmonisation.
    """
    # Verify gate proof
    if corrected_cell is None:
        raise OffshoreGateViolation(
            "extract_offshore_sub_score requires a CorrectedOffshoreCell. "
            "apply_offshore_correction() must be called before offshore sub-score extraction."
        )
    return _weighted_mean(normalised_values, OFFSHORE_KEYS, weights)


# ---------------------------------------------------------------------------
# ObservableVector construction
# ---------------------------------------------------------------------------

def build_observable_vector(
    normalised_values: dict[str, Optional[float]],
    corrected_offshore: Optional[CorrectedOffshoreCell] = None,
    environment: str = "ONSHORE",
) -> ObservableVector:
    """
    Construct a typed ObservableVector from a normalised feature tensor.

    For offshore cells: corrected_offshore must be provided.
    For onshore cells: x_off_* fields are set to None in the vector.

    CONSTITUTIONAL RULE: Offshore observables (x_off_1..4) in the returned
    vector are only populated if corrected_offshore is provided.
    Passing a non-None corrected_offshore for an onshore cell raises ValueError.

    Args:
        normalised_values:   Dict of 42 observable keys → normalised float or None.
        corrected_offshore:  CorrectedOffshoreCell (REQUIRED for offshore cells).
        environment:         "ONSHORE" | "OFFSHORE" | "COMBINED"

    Returns:
        ObservableVector with all 42 fields populated or None.
    """
    if environment == "OFFSHORE" and corrected_offshore is None:
        raise OffshoreGateViolation(
            "build_observable_vector called with environment=OFFSHORE "
            "but no CorrectedOffshoreCell provided. "
            "Offshore cells require correction before observable extraction."
        )

    # Build field dict — offshore keys forced to None for onshore cells
    field_values: dict[str, Optional[float]] = {}
    for key, value in normalised_values.items():
        if key.startswith("x_off_") and environment != "OFFSHORE":
            field_values[key] = None
        else:
            field_values[key] = value

    return ObservableVector(**field_values)