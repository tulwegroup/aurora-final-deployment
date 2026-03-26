"""
Aurora OSI vNext — Observable Normalisation Engine
Phase H §H.1

Implements §3.2 normalisation and §3.3 missing-data handling.

CONSTITUTIONAL RULE: This is the ONLY location for observable normalisation.
No other module may scale, re-scale, or transform raw sensor values into [0,1].

Two-pass approach:
  Pass 1 (compute_scan_normalisation_params): across all cells in AOI,
          compute μ_k and σ_k per observable. This ensures all cells in
          a scan are normalised against the SAME population distribution.
  Pass 2 (normalise_observable): apply z-score transform and clamp to [0,1]
          for each cell independently using the per-scan params.

Missing data handling (§3.3):
  - Missing observable → null value (0.5 mid-range sentinel)
  - u_sensor contribution set to 1.0 (maximum uncertainty)
  - Missing is NEVER zero — zero means a measured zero signal

No scoring. No ACIF. No imports from core/scoring, core/tiering, core/gates.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.extraction_types import (
    MissingObservable,
    ObservableNormParams,
    ScanNormalisationParams,
)

# All 42 observable field names — must match ObservableVector field order
OBSERVABLE_KEYS: tuple[str, ...] = (
    "x_spec_1", "x_spec_2", "x_spec_3", "x_spec_4",
    "x_spec_5", "x_spec_6", "x_spec_7", "x_spec_8",
    "x_sar_1",  "x_sar_2",  "x_sar_3",  "x_sar_4",  "x_sar_5",  "x_sar_6",
    "x_therm_1", "x_therm_2", "x_therm_3", "x_therm_4",
    "x_grav_1", "x_grav_2", "x_grav_3", "x_grav_4", "x_grav_5", "x_grav_6",
    "x_mag_1",  "x_mag_2",  "x_mag_3",  "x_mag_4",  "x_mag_5",
    "x_struct_1", "x_struct_2", "x_struct_3", "x_struct_4", "x_struct_5",
    "x_hydro_1", "x_hydro_2", "x_hydro_3", "x_hydro_4",
    "x_off_1",  "x_off_2",  "x_off_3",  "x_off_4",
)

assert len(OBSERVABLE_KEYS) == 42, "OBSERVABLE_KEYS must have exactly 42 entries"

# Minimum samples required before σ-based normalisation is reliable
_MIN_SAMPLES_FOR_SIGMA = 5

# Fallback σ used when population has insufficient spread (avoids division by zero)
_FALLBACK_SIGMA = 1.0


def compute_scan_normalisation_params(
    raw_stacks: list[dict[str, Optional[float]]],
    scan_id: str,
) -> ScanNormalisationParams:
    """
    Pass 1: Compute per-observable μ_k and σ_k across the full AOI population.

    Args:
        raw_stacks: List of dicts, one per cell, each mapping observable_key → raw_value.
                    None values are excluded from statistics.
        scan_id:    The scan for which params are being computed.

    Returns:
        ScanNormalisationParams with all 42 observable keys populated.
        Keys with insufficient data use fallback μ=0.5, σ=1.0.

    CONSTITUTIONAL RULE: Normalisation parameters are per-scan.
    A new scan over the same AOI with different acquisition dates
    will produce different μ_k, σ_k values.
    """
    # Collect non-null values per observable key
    value_lists: dict[str, list[float]] = {k: [] for k in OBSERVABLE_KEYS}
    for cell_raw in raw_stacks:
        for key in OBSERVABLE_KEYS:
            v = cell_raw.get(key)
            if v is not None and math.isfinite(v):
                value_lists[key].append(v)

    params: dict[str, ObservableNormParams] = {}
    for key in OBSERVABLE_KEYS:
        values = value_lists[key]
        n = len(values)
        if n >= _MIN_SAMPLES_FOR_SIGMA:
            mu = sum(values) / n
            variance = sum((v - mu) ** 2 for v in values) / n
            sigma = math.sqrt(variance) if variance > 0 else _FALLBACK_SIGMA
        else:
            # Insufficient data: use population mid-point as mu, unit sigma
            mu = 0.5
            sigma = _FALLBACK_SIGMA
        params[key] = ObservableNormParams(
            observable_key=key,
            mu=mu,
            sigma=sigma,
            n_samples=n,
        )

    return ScanNormalisationParams(scan_id=scan_id, params=params)


def normalise_observable(
    raw_value: Optional[float],
    norm_params: ObservableNormParams,
) -> tuple[Optional[float], float]:
    """
    Pass 2: Apply z-score normalisation and clamp to [0, 1] (§3.2).

    Normalised value: x̂_k = clamp((x_k - μ_k) / σ_k * 0.5 + 0.5, 0, 1)
    The scaling factor 0.5 maps ±1σ to [0.0, 1.0] range.

    Returns:
        (normalised_value, u_sensor_contribution)

        normalised_value:     float ∈ [0, 1] or None if raw_value is None
        u_sensor_contribution: 0.0 if present, 1.0 if missing (§3.3)

    CONSTITUTIONAL RULE: This function is the ONLY normalisation path.
    No other module applies z-score transforms to sensor values.
    """
    if raw_value is None or not math.isfinite(raw_value):
        return None, 1.0  # §3.3: missing → null + full sensor uncertainty

    sigma = norm_params.sigma if norm_params.sigma > 0 else _FALLBACK_SIGMA
    z_score = (raw_value - norm_params.mu) / sigma
    # Map z-score to [0, 1]: 0 at -2σ, 0.5 at μ, 1.0 at +2σ
    scaled = z_score * 0.25 + 0.5
    clamped = max(norm_params.clamp_min, min(norm_params.clamp_max, scaled))
    return clamped, 0.0  # Present observable → zero sensor uncertainty contribution


def handle_missing_observable(key: str, reason: str = "no_data") -> MissingObservable:
    """
    Create a MissingObservable sentinel for a key with no available measurement.

    §3.3: Missing observables:
      - Normalised value = 0.5 (neutral mid-range, not zero)
      - u_sensor_contribution = 1.0 (maximum sensor uncertainty)

    This ensures missing sensors contribute maximum uncertainty but do not
    incorrectly appear as a zero-signal measurement.
    """
    return MissingObservable(
        key=key,
        reason=reason,
        normalised_value=0.5,
        u_sensor_contribution=1.0,
    )


def compute_coverage_stats(
    normalised_values: dict[str, Optional[float]],
) -> tuple[int, int, float]:
    """
    Compute present_count, missing_count, coverage_fraction for one cell.

    Returns:
        (present_count, missing_count, coverage_fraction)
    """
    present = sum(1 for v in normalised_values.values() if v is not None)
    missing = 42 - present
    return present, missing, present / 42