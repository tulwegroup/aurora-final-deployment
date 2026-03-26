"""
Aurora OSI vNext — Temporal Coherence Module
Phase I §I.4 | Phase B §7

CONSTITUTIONAL RULE: This is the ONLY location for temporal coherence scoring.
Geometric mean is CONSTITUTIONALLY REQUIRED — arithmetic mean is prohibited.

Mathematical formulation:

  §7.3 — Temporal sub-scores (persistence and stability):
    Each sub-score q_j ∈ [0, 1] measures signal persistence across multiple epochs.

    InSAR persistence:
      q_insar = exp(-γ × σ²_deform / μ_deform)
      where σ²_deform / μ_deform = coefficient of variation of InSAR deformation signal.
      High persistence (low CV) → q_insar → 1.

    Thermal stability:
      q_therm = exp(-γ × σ²_LST / (ΔT_day-night + ε))
      High stability (low variance relative to diurnal range) → q_therm → 1.

    Vegetation stress persistence:
      q_veg = count(epochs with anomaly > τ_veg) / total_epochs
      q_veg ∈ [0, 1].

    Moisture stability:
      q_moist = 1 - (σ²_moisture / max_variance)
      Stable (low variance) soil moisture → q_moist → 1.

  §7.2 — Temporal coherence (WEIGHTED GEOMETRIC MEAN):
    T_i^(c) = ∏_j q_j^(α_j) ^ (1/Σ_j α_j)
    where α_j are temporal modality weights from Θ_c.

    CONSTITUTIONAL INVARIANT: If any q_j = 0, then T_i = 0.
    This is why geometric mean is required — arithmetic mean would not enforce this.

  §7.4 — Hard veto:
    If T_i < τ_temp_veto → T_i = 0.0 (veto fires)

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.component_scores import TemporalResult, TemporalSubScores

_EPSILON = 1e-10
_DEFAULT_TAU_TEMP_VETO = 0.05   # Default temporal veto threshold


def compute_persistence_sub_score(
    deformation_time_series: list[float],
    gamma: float = 1.0,
) -> Optional[float]:
    """
    §7.3 — InSAR deformation persistence sub-score q_insar.

    q_insar = exp(-γ × σ² / (|μ| + ε))
    Measures how consistent InSAR surface deformation is across epochs.
    High γ → sharper penalisation of variable signals.

    Args:
        deformation_time_series: InSAR deformation values across epochs (mm)
        gamma: Persistence sensitivity (Θ_c)

    Returns:
        q_insar ∈ [0, 1], or None if fewer than 2 epochs.
    """
    n = len(deformation_time_series)
    if n < 2:
        return None

    mu = sum(deformation_time_series) / n
    variance = sum((v - mu) ** 2 for v in deformation_time_series) / n
    cv = variance / (abs(mu) + _EPSILON)
    q = math.exp(-gamma * cv)
    return max(0.0, min(1.0, q))


def compute_stability_sub_score(
    time_series: list[float],
    delta: float = 1.0,
    reference_variance: Optional[float] = None,
) -> Optional[float]:
    """
    §7.3 — Stability sub-score for any temporal modality (thermal, moisture).

    q_stable = exp(-delta × σ² / (reference_variance + ε))

    Measures temporal stability relative to a reference variance level.
    If reference_variance is None, uses the series maximum variance (normalised).

    Returns:
        q_stable ∈ [0, 1], or None if fewer than 2 epochs.
    """
    n = len(time_series)
    if n < 2:
        return None

    mu = sum(time_series) / n
    variance = sum((v - mu) ** 2 for v in time_series) / n
    ref_var = reference_variance if reference_variance is not None else (variance + _EPSILON)
    q = math.exp(-delta * variance / (ref_var + _EPSILON))
    return max(0.0, min(1.0, q))


def compute_vegetation_stress_persistence(
    ndvi_anomaly_series: list[float],
    tau_veg: float = -0.05,
) -> Optional[float]:
    """
    §7.3 — Vegetation stress persistence sub-score q_veg.

    q_veg = count(anomaly < τ_veg) / n
    where τ_veg < 0 indicates below-baseline NDVI (stress condition).
    High q_veg → consistent stress → possible subsurface influence.

    Returns:
        q_veg ∈ [0, 1], or None if no data.
    """
    if not ndvi_anomaly_series:
        return None
    n = len(ndvi_anomaly_series)
    stressed = sum(1 for v in ndvi_anomaly_series if v < tau_veg)
    return stressed / n


def compute_temporal_coherence(
    sub_scores: TemporalSubScores,
    weights: Optional[dict[str, float]] = None,
) -> float:
    """
    §7.2 — Compute temporal coherence T_i^(c) as WEIGHTED GEOMETRIC MEAN.

    T_i = ∏_j q_j^(α_j / Σα_j)

    CONSTITUTIONAL INVARIANT: Any q_j = 0 → T_i = 0.
    This is NOT arithmetic mean — the geometric mean enforces this.

    Args:
        sub_scores: TemporalSubScores with q_j values (None = missing)
        weights:    α_j weight per sub-score. Defaults to equal weights.

    Returns:
        T_i^(c) ∈ [0, 1]
    """
    # Map sub-score values to (value, weight) pairs
    default_weights = {
        "insar_persistence":             1.0,
        "thermal_stability":             1.0,
        "vegetation_stress_persistence": 0.7,
        "moisture_stability":            0.7,
    }
    w = weights or default_weights

    score_map = {
        "insar_persistence":             sub_scores.insar_persistence,
        "thermal_stability":             sub_scores.thermal_stability,
        "vegetation_stress_persistence": sub_scores.vegetation_stress_persistence,
        "moisture_stability":            sub_scores.moisture_stability,
    }

    # Only include sub-scores that are non-null
    active = [(v, w.get(k, 1.0)) for k, v in score_map.items() if v is not None]

    if not active:
        return 0.5  # No temporal data → neutral temporal coherence

    weight_sum = sum(wt for _, wt in active)
    if weight_sum == 0.0:
        return 0.5

    # Weighted geometric mean: exp(Σ(α_j × ln(q_j + ε)) / Σα_j)
    log_weighted_sum = sum(wt * math.log(max(q, _EPSILON)) for q, wt in active)
    t_i = math.exp(log_weighted_sum / weight_sum)
    return max(0.0, min(1.0, t_i))


def apply_temporal_veto(
    t_i: float,
    tau_temp_veto: float = _DEFAULT_TAU_TEMP_VETO,
) -> bool:
    """
    §7.4 — Temporal hard veto.

    Returns True (veto fires) if T_i < τ_temp_veto.
    When veto fires, T_i is set to 0.0 by the caller.
    """
    return t_i < tau_temp_veto


def score_temporal(
    cell_id: str,
    commodity: str,
    insar_series: Optional[list[float]] = None,
    thermal_series: Optional[list[float]] = None,
    ndvi_anomaly_series: Optional[list[float]] = None,
    moisture_series: Optional[list[float]] = None,
    gamma: float = 1.0,
    delta: float = 1.0,
    tau_veg: float = -0.05,
    tau_temp_veto: float = _DEFAULT_TAU_TEMP_VETO,
    weights: Optional[dict[str, float]] = None,
    n_epochs: int = 0,
) -> TemporalResult:
    """
    Full temporal coherence pipeline for one cell.
    Computes all available sub-scores → weighted geometric mean → veto check.
    """
    q_insar = compute_persistence_sub_score(insar_series or [], gamma)
    q_therm = compute_stability_sub_score(thermal_series or [], delta)
    q_veg   = compute_vegetation_stress_persistence(ndvi_anomaly_series or [], tau_veg)
    q_moist = compute_stability_sub_score(moisture_series or [], delta)

    sub_scores = TemporalSubScores(
        insar_persistence=q_insar,
        thermal_stability=q_therm,
        vegetation_stress_persistence=q_veg,
        moisture_stability=q_moist,
    )

    t_i = compute_temporal_coherence(sub_scores, weights)
    veto = apply_temporal_veto(t_i, tau_temp_veto)
    if veto:
        t_i = 0.0

    return TemporalResult(
        cell_id=cell_id,
        commodity=commodity,
        sub_scores=sub_scores,
        temporal_score=t_i,
        temporal_veto_fired=veto,
        n_epochs_used=n_epochs,
    )