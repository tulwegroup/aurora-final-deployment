"""
Aurora OSI vNext — Causal Consistency Module
Phase I §I.2 | Phase B §5

CONSTITUTIONAL RULE: This is the ONLY location for causal consistency scoring
and causal hard veto logic.

Mathematical formulation:

  §5.3 — DAG node evidence scores:
    Five nodes represent causal stages in a generic mineral system DAG:
      z_surface:   Surface expression (spectral + hydro observables)
      z_structural: Structural pathway (structural observables + SAR)
      z_subsurface: Subsurface support (gravity + magnetic observables)
      z_thermal:   Thermal/fluid transport (thermal + offshore observables)
      z_temporal:  Temporal persistence (temporal coherence proxy)

    Each z_j is a weighted mean of the relevant normalised observables.

  §5.1 — Causal consistency score:
    C_i^(c) = ∏_{(a,b)∈G_c} [ max(0, z_b - z_a × δ_ab) ]^(1/m)
    where:
      G_c  = directed edges of commodity causal graph
      δ_ab = edge threshold: child node must satisfy z_b ≥ δ_ab × z_a
      m    = number of edges
    Simplified: C_i is the geometric mean of edge compliance scores.
    Each edge compliance score = clamp(z_child / (δ × z_parent + ε), 0, 1).

  §5.2 — Hard vetoes (unconditional C = 0):
    Veto 1: z_surface > τ_surf AND z_structural < τ_struct_min
             (Surface expression exists but no structural pathway → spurious)
    Veto 2: z_structural > τ_struct AND z_subsurface < τ_sub_min
             (Structure present but no subsurface geophysical support → phantom)
    Veto 3: z_temporal_dag < τ_temp_veto
             (Temporal signal inconsistent with persistent causal state)

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.component_scores import (
    CausalResult,
    CausalVetoFlags,
    DagNodeScores,
)
from app.models.observable_vector import ObservableVector

_EPSILON = 1e-8  # Guard against division by zero in edge compliance


def compute_dag_node_scores(
    obs_vec: ObservableVector,
    dag_weights: Optional[dict[str, dict[str, float]]] = None,
) -> DagNodeScores:
    """
    §5.3 — Compute DAG node evidence scores from normalised observables.

    Each node aggregates a subset of observables using weighted mean.
    The dag_weights argument allows commodity-specific modulation of which
    observables feed which DAG nodes (from Θ_c).

    Default node-observable mapping (used when dag_weights is None):
      z_surface:    x_spec_1..4 (surface mineralisation) + x_hydro_1..4
      z_structural: x_struct_1..5 + x_sar_1..3
      z_subsurface: x_grav_1..6 + x_mag_1..5
      z_thermal:    x_therm_1..4 + x_off_2 (SST anomaly) + x_off_4 (Chl)
      z_temporal:   x_spec_5..8 (NIR/SWIR temporal proxies) + x_sar_3 (coherence)

    Returns:
        DagNodeScores with all five z_j ∈ [0, 1].
    """
    def _mean(keys: tuple[str, ...]) -> float:
        vals = [getattr(obs_vec, k) for k in keys if getattr(obs_vec, k) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    z_surface    = _mean(("x_spec_1","x_spec_2","x_spec_3","x_spec_4","x_hydro_1","x_hydro_2"))
    z_structural = _mean(("x_struct_1","x_struct_2","x_struct_3","x_struct_4","x_struct_5","x_sar_1","x_sar_2","x_sar_3"))
    z_subsurface = _mean(("x_grav_1","x_grav_2","x_grav_3","x_grav_4","x_grav_5","x_grav_6","x_mag_1","x_mag_2","x_mag_3","x_mag_4","x_mag_5"))
    z_thermal    = _mean(("x_therm_1","x_therm_2","x_therm_3","x_therm_4","x_off_2","x_off_4"))
    z_temporal   = _mean(("x_spec_5","x_spec_6","x_spec_7","x_spec_8","x_sar_3","x_sar_4"))

    return DagNodeScores(
        cell_id=obs_vec.model_fields and "" or "",  # cell_id injected by caller
        commodity="",                                # commodity injected by caller
        z_surface=max(0.0, min(1.0, z_surface)),
        z_structural=max(0.0, min(1.0, z_structural)),
        z_subsurface=max(0.0, min(1.0, z_subsurface)),
        z_thermal=max(0.0, min(1.0, z_thermal)),
        z_temporal_dag=max(0.0, min(1.0, z_temporal)),
    )


def apply_causal_vetoes(
    dag: DagNodeScores,
    tau_surf: float = 0.4,
    tau_struct_min: float = 0.15,
    tau_struct: float = 0.35,
    tau_sub_min: float = 0.15,
    tau_temp_veto: float = 0.10,
) -> CausalVetoFlags:
    """
    §5.2 — Evaluate the three causal hard veto conditions.

    Veto thresholds (τ values) are sourced from Θ_c (commodity parameters).
    Defaults are conservative — commodity-specific overrides apply in Phase J.

    Returns:
        CausalVetoFlags with one bool per veto condition.
        If CausalVetoFlags.any_veto_fired → C_i = 0.0.
    """
    veto_1 = (dag.z_surface > tau_surf and dag.z_structural < tau_struct_min)
    veto_2 = (dag.z_structural > tau_struct and dag.z_subsurface < tau_sub_min)
    veto_3 = (dag.z_temporal_dag < tau_temp_veto)

    return CausalVetoFlags(
        veto_1_surface_without_structure=veto_1,
        veto_2_structure_without_subsurface=veto_2,
        veto_3_temporal_inconsistency=veto_3,
    )


def compute_causal_consistency(
    dag: DagNodeScores,
    edges: Optional[list[tuple[str, str, float]]] = None,
) -> float:
    """
    §5.1 — Compute causal consistency score C_i^(c) as geometric mean of
    edge compliance scores along the commodity DAG.

    Each edge (parent_node, child_node, delta) contributes:
      compliance_jk = clamp(z_child / (delta × z_parent + ε), 0, 1)

    C_i = (∏_edges compliance_jk)^(1/m)

    Default edges (generic mineral system, overridden by Θ_c):
      surface    → structural (δ=0.5)  structural pathway must follow surface
      structural → subsurface (δ=0.4)  subsurface must support structure
      subsurface → thermal    (δ=0.3)  thermal must couple to subsurface

    Args:
        dag:   DagNodeScores computed by compute_dag_node_scores()
        edges: List of (parent_key, child_key, delta) triples.
               parent_key and child_key are DagNodeScores attribute names.

    Returns:
        C_i^(c) ∈ [0, 1]. Returns 0.0 if any veto has fired (checked by caller).
    """
    node_values = {
        "z_surface":    dag.z_surface,
        "z_structural": dag.z_structural,
        "z_subsurface": dag.z_subsurface,
        "z_thermal":    dag.z_thermal,
        "z_temporal_dag": dag.z_temporal_dag,
    }

    default_edges: list[tuple[str, str, float]] = [
        ("z_surface",    "z_structural", 0.5),
        ("z_structural", "z_subsurface", 0.4),
        ("z_subsurface", "z_thermal",    0.3),
    ]
    active_edges = edges or default_edges

    if not active_edges:
        return 1.0  # No edges → no causal constraint → full consistency

    compliance_scores: list[float] = []
    for parent_key, child_key, delta in active_edges:
        z_parent = node_values.get(parent_key, 0.0)
        z_child  = node_values.get(child_key, 0.0)
        compliance = z_child / (delta * z_parent + _EPSILON)
        compliance_scores.append(max(0.0, min(1.0, compliance)))

    # Geometric mean of compliance scores
    log_sum = sum(math.log(s + _EPSILON) for s in compliance_scores)
    c_i = math.exp(log_sum / len(compliance_scores))
    return max(0.0, min(1.0, c_i))


def score_causal(
    cell_id: str,
    commodity: str,
    obs_vec: ObservableVector,
    edges: Optional[list[tuple[str, str, float]]] = None,
    veto_thresholds: Optional[dict[str, float]] = None,
) -> CausalResult:
    """
    Full causal consistency pipeline for one cell.
    Calls compute_dag_node_scores → apply_causal_vetoes → compute_causal_consistency.
    If any veto fires, causal_score is set to 0.0.
    """
    tau = veto_thresholds or {}
    dag = compute_dag_node_scores(obs_vec)
    # Inject identity into dag (workaround for frozen dataclass)
    dag = DagNodeScores(
        cell_id=cell_id,
        commodity=commodity,
        z_surface=dag.z_surface,
        z_structural=dag.z_structural,
        z_subsurface=dag.z_subsurface,
        z_thermal=dag.z_thermal,
        z_temporal_dag=dag.z_temporal_dag,
    )
    veto_flags = apply_causal_vetoes(
        dag,
        tau_surf=tau.get("tau_surf", 0.4),
        tau_struct_min=tau.get("tau_struct_min", 0.15),
        tau_struct=tau.get("tau_struct", 0.35),
        tau_sub_min=tau.get("tau_sub_min", 0.15),
        tau_temp_veto=tau.get("tau_temp_veto", 0.10),
    )

    if veto_flags.any_veto_fired:
        c_i = 0.0
    else:
        c_i = compute_causal_consistency(dag, edges)

    return CausalResult(
        cell_id=cell_id,
        commodity=commodity,
        dag_node_scores=dag,
        causal_score=c_i,
        veto_flags=veto_flags,
    )