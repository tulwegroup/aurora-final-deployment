"""
Aurora OSI vNext — Evidence Score Module
Phase I §I.1 | Phase B §4.2, §4.3

CONSTITUTIONAL RULE: This is the ONLY location for evidence score computation.

Mathematical formulation:

  §4.2 — Weighted evidence score:
    E_i^(c) = Σ_k [ w_k^(c) × x̂_k ] / Σ_k [ w_k^(c) ]
    where:
      x̂_k  = normalised observable k for cell i (∈ [0,1], None if missing)
      w_k^(c) = commodity-specific evidence weight for modality k
                sourced from observable_weighting_vectors (commodity library)
      Sum runs only over non-null observable keys.

  §4.3 — Spatial clustering adjustment:
    κ_i = (1/|N_i|) × Σ_{j∈N_i} [ E_j^(c) ] / E_max
    where:
      N_i = neighbourhood of cell i (spatial adjacency)
      E_max = maximum evidence score in AOI
    κ_i ∈ [0, 1]

    Ẽ_i^(c) = E_i^(c) × (1 + α_c × (κ_i - 0.5))
    where α_c ∈ [0, 1] is the clustering sensitivity parameter from Θ_c.
    If α_c = 0: Ẽ_i = E_i (no clustering effect).
    Ẽ_i is clamped to [0, 1].

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.component_scores import EvidenceResult
from app.models.observable_vector import ObservableVector


def compute_evidence_score(
    obs_vec: ObservableVector,
    weights: dict[str, float],
) -> tuple[float, dict[str, Optional[float]]]:
    """
    §4.2 — Compute the commodity-weighted evidence score E_i^(c).

    Args:
        obs_vec:   Normalised ObservableVector for this cell.
        weights:   Commodity-specific weight map {observable_key: weight}.
                   Must be non-negative; zero-weight keys are excluded.
                   Sourced from observable_weighting_vectors (Phase G).

    Returns:
        (E_i, modality_contributions)
        E_i ∈ [0, 1]: weighted evidence score.
        modality_contributions: per-key weighted contribution (for audit trail).

    If no observable with non-zero weight is non-null, returns (0.0, {}).
    """
    weighted_sum = 0.0
    weight_total = 0.0
    contributions: dict[str, Optional[float]] = {}

    for key, weight in weights.items():
        if weight <= 0.0:
            continue
        value = getattr(obs_vec, key, None)
        if value is None:
            contributions[key] = None
            continue
        weighted_sum += weight * value
        weight_total += weight
        contributions[key] = weight * value

    if weight_total == 0.0:
        return 0.0, contributions

    e_i = weighted_sum / weight_total
    return max(0.0, min(1.0, e_i)), contributions


def compute_clustering_metric(
    cell_evidence: float,
    neighbour_evidence_scores: list[float],
    e_max: float,
) -> float:
    """
    §4.3 — Compute spatial clustering metric κ_i.

    κ_i = (1/|N_i|) × Σ_{j∈N_i}[E_j] / E_max

    Measures how anomalous the neighbourhood is relative to the AOI maximum.
    High κ_i (→ 1): cell is in a high-evidence cluster — boosts adjusted score.
    Low κ_i (→ 0): isolated anomaly — reduces adjusted score.

    Args:
        cell_evidence:            E_i for the target cell (unused in formula;
                                  included for traceability).
        neighbour_evidence_scores: E_j values for spatial neighbours.
        e_max:                    Maximum evidence score in the AOI.

    Returns:
        κ_i ∈ [0, 1]
    """
    if not neighbour_evidence_scores or e_max <= 0.0:
        return 0.5  # No neighbourhood data → neutral clustering metric

    n = len(neighbour_evidence_scores)
    mean_neighbour_e = sum(neighbour_evidence_scores) / n
    kappa = mean_neighbour_e / e_max
    return max(0.0, min(1.0, kappa))


def compute_adjusted_evidence(
    e_i: float,
    kappa_i: float,
    alpha_c: float,
) -> float:
    """
    §4.3 — Compute clustering-adjusted evidence Ẽ_i^(c).

    Ẽ_i^(c) = clamp(E_i × (1 + α_c × (κ_i - 0.5)), 0, 1)

    α_c = 0: no clustering effect (Ẽ = E).
    α_c = 1: full clustering effect (±50% modulation at κ extremes).

    Args:
        e_i:     Base evidence score E_i^(c) ∈ [0, 1]
        kappa_i: Clustering metric κ_i ∈ [0, 1]
        alpha_c: Clustering sensitivity from Θ_c ∈ [0, 1]

    Returns:
        Ẽ_i^(c) ∈ [0, 1]
    """
    if not (0.0 <= alpha_c <= 1.0):
        raise ValueError(f"alpha_c must be in [0, 1], got {alpha_c}")
    e_tilde = e_i * (1.0 + alpha_c * (kappa_i - 0.5))
    return max(0.0, min(1.0, e_tilde))


def _group_contributions(
    obs_vec: ObservableVector,
    contributions: dict[str, Optional[float]],
) -> dict[str, Optional[float]]:
    """Aggregate per-key contributions into modality-level sums for audit trail."""
    groups = {
        "spectral":   ("x_spec_1","x_spec_2","x_spec_3","x_spec_4","x_spec_5","x_spec_6","x_spec_7","x_spec_8"),
        "sar":        ("x_sar_1","x_sar_2","x_sar_3","x_sar_4","x_sar_5","x_sar_6"),
        "thermal":    ("x_therm_1","x_therm_2","x_therm_3","x_therm_4"),
        "gravity":    ("x_grav_1","x_grav_2","x_grav_3","x_grav_4","x_grav_5","x_grav_6"),
        "magnetic":   ("x_mag_1","x_mag_2","x_mag_3","x_mag_4","x_mag_5"),
        "structural": ("x_struct_1","x_struct_2","x_struct_3","x_struct_4","x_struct_5"),
        "hydro":      ("x_hydro_1","x_hydro_2","x_hydro_3","x_hydro_4"),
        "offshore":   ("x_off_1","x_off_2","x_off_3","x_off_4"),
    }
    result: dict[str, Optional[float]] = {}
    for group, keys in groups.items():
        vals = [contributions[k] for k in keys if k in contributions and contributions[k] is not None]
        result[group] = sum(vals) if vals else None
    return result


def score_evidence(
    cell_id: str,
    commodity: str,
    obs_vec: ObservableVector,
    weights: dict[str, float],
    neighbour_evidence_scores: list[float],
    e_max: float,
    alpha_c: float,
) -> EvidenceResult:
    """
    Full evidence scoring pipeline for one cell.
    Calls compute_evidence_score → compute_clustering_metric → compute_adjusted_evidence.
    """
    e_i, contributions = compute_evidence_score(obs_vec, weights)
    kappa_i = compute_clustering_metric(e_i, neighbour_evidence_scores, e_max)
    e_tilde = compute_adjusted_evidence(e_i, kappa_i, alpha_c)
    group_contributions = _group_contributions(obs_vec, contributions)

    return EvidenceResult(
        cell_id=cell_id,
        commodity=commodity,
        evidence_score=e_i,
        clustering_metric=kappa_i,
        adjusted_evidence_score=e_tilde,
        spectral_contribution=group_contributions.get("spectral"),
        sar_contribution=group_contributions.get("sar"),
        thermal_contribution=group_contributions.get("thermal"),
        gravity_contribution=group_contributions.get("gravity"),
        magnetic_contribution=group_contributions.get("magnetic"),
        structural_contribution=group_contributions.get("structural"),
        hydro_contribution=group_contributions.get("hydro"),
        offshore_contribution=group_contributions.get("offshore"),
    )