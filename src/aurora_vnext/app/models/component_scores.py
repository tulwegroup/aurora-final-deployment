"""
Aurora OSI vNext — Component Score Intermediate Types
Phase I

Typed containers for the six independent score components produced by
the Phase I scientific core modules. These are TRANSIENT pipeline objects
consumed by core/scoring.py (Phase J) to compute the ACIF.

CONSTITUTIONAL RULE: These types carry component RESULTS.
They do NOT contain the ACIF formula — that lives exclusively in core/scoring.py.

No imports from core/scoring, core/tiering, core/gates, services/, storage/, api/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class EvidenceResult:
    """
    Output of core/evidence.py for one cell.

    E_i^(c): commodity-adjusted evidence score ∈ [0, 1]
    Ẽ_i^(c): clustering-adjusted evidence score ∈ [0, 1] — the value used in ACIF
    """
    cell_id: str
    commodity: str

    # §4.2 — Base weighted evidence score
    evidence_score: float                           # E_i^(c) ∈ [0, 1]

    # §4.3 — Spatial clustering metric
    clustering_metric: float                        # κ_i ∈ [0, 1]

    # §4.3 — Clustering-adjusted evidence (ACIF input)
    adjusted_evidence_score: float                  # Ẽ_i^(c) ∈ [0, 1]

    # Modality sub-score contributions (for audit / debugging)
    spectral_contribution: Optional[float] = None
    sar_contribution: Optional[float] = None
    thermal_contribution: Optional[float] = None
    gravity_contribution: Optional[float] = None
    magnetic_contribution: Optional[float] = None
    structural_contribution: Optional[float] = None
    hydro_contribution: Optional[float] = None
    offshore_contribution: Optional[float] = None


@dataclass(frozen=True)
class DagNodeScores:
    """
    Intermediate DAG node evidence scores used by causal consistency (§5.3).
    Each node represents one causal pathway in the mineral system graph.
    """
    cell_id: str
    commodity: str

    # Surface expression node
    z_surface: float                               # Surface mineralisation indicators ∈ [0, 1]

    # Structural pathway node
    z_structural: float                            # Structural conduit indicators ∈ [0, 1]

    # Subsurface support node
    z_subsurface: float                            # Gravity + magnetic subsurface anomaly ∈ [0, 1]

    # Thermal/fluid transport node
    z_thermal: float                               # Heat flow / hydrothermal indicators ∈ [0, 1]

    # Temporal stability node
    z_temporal_dag: float                          # Multi-epoch signal persistence ∈ [0, 1]


@dataclass(frozen=True)
class CausalVetoFlags:
    """Explicit boolean record of which causal hard vetoes fired."""
    veto_1_surface_without_structure: bool = False   # Surface signal without structural pathway
    veto_2_structure_without_subsurface: bool = False # Structure without subsurface support
    veto_3_temporal_inconsistency: bool = False       # Temporal pattern inconsistent with causal state

    @property
    def any_veto_fired(self) -> bool:
        return (self.veto_1_surface_without_structure
                or self.veto_2_structure_without_subsurface
                or self.veto_3_temporal_inconsistency)


@dataclass(frozen=True)
class CausalResult:
    """
    Output of core/causal.py for one cell.
    C_i^(c): causal consistency score ∈ [0, 1].
    If any hard veto fires, causal_score = 0.0 unconditionally.
    """
    cell_id: str
    commodity: str
    dag_node_scores: DagNodeScores
    causal_score: float                            # C_i^(c) ∈ [0, 1]; 0.0 if any veto fired
    veto_flags: CausalVetoFlags


@dataclass(frozen=True)
class PhysicsResiduals:
    """
    First-class physics residual outputs (§6.1, §6.2, §6.5).
    These are persisted in ScanCell and are NOT internal diagnostics.
    """
    cell_id: str

    gravity_residual: Optional[float] = None       # R_grav = ||W_d(g_obs - g_pred)||² ≥ 0
    physics_residual: Optional[float] = None       # R_phys = ||∇²Φ - 4πGρ||² ≥ 0
    darcy_residual: Optional[float] = None         # R_darcy for fluid systems ≥ 0
    water_column_residual: Optional[float] = None  # R_wc for offshore ≥ 0


@dataclass(frozen=True)
class PhysicsResult:
    """
    Output of core/physics.py for one cell.
    Ψ_i: physics consistency score ∈ [0, 1].
    """
    cell_id: str
    commodity: str
    residuals: PhysicsResiduals
    physics_score: float                           # Ψ_i ∈ [0, 1]; approaches 1 at zero residuals
    physics_veto_fired: bool                       # True if residuals exceed tolerance bounds


@dataclass(frozen=True)
class TemporalSubScores:
    """Individual temporal modality persistence sub-scores q_j ∈ [0, 1]."""
    insar_persistence: Optional[float] = None      # InSAR deformation persistence
    thermal_stability: Optional[float] = None      # Thermal anomaly stability
    vegetation_stress_persistence: Optional[float] = None  # Veg stress persistence
    moisture_stability: Optional[float] = None     # Soil moisture stability


@dataclass(frozen=True)
class TemporalResult:
    """
    Output of core/temporal.py for one cell.
    T_i^(c): temporal coherence score ∈ [0, 1].
    Computed as WEIGHTED GEOMETRIC MEAN of sub-scores (§7.2).
    """
    cell_id: str
    commodity: str
    sub_scores: TemporalSubScores
    temporal_score: float                          # T_i^(c) ∈ [0, 1]
    temporal_veto_fired: bool                      # True if T_i < τ_temp_veto
    n_epochs_used: int = 0                         # Number of temporal epochs contributing


@dataclass(frozen=True)
class ProvincePriorResult:
    """
    Output of core/priors.py for one cell.
    Π^(c)(r_i): province prior score ∈ [0, 1].
    """
    cell_id: str
    commodity: str
    province_code: Optional[str]
    prior_probability: float                       # Π^(c)(r_i) ∈ [0, 1]; 0.0 if impossible
    posterior_probability: Optional[float]         # Bayesian posterior if ground-truth available
    province_veto_fired: bool                      # True if geologically impossible province
    impossibility_reason: Optional[str]            # Why veto fired, if applicable
    ci_95_lower: Optional[float] = None
    ci_95_upper: Optional[float] = None

    @property
    def effective_prior(self) -> float:
        """Return posterior if available, else prior."""
        return self.posterior_probability if self.posterior_probability is not None else self.prior_probability


@dataclass(frozen=True)
class UncertaintyComponents:
    """The five independent uncertainty contributions per cell (§10.2)."""
    u_sensor: float  # Sensor coverage uncertainty ∈ [0, 1]
    u_model: float   # Inversion model uncertainty ∈ [0, 1]
    u_physics: float # 1 - Ψ_i ∈ [0, 1]
    u_temporal: float# 1 - T_i ∈ [0, 1]
    u_prior: float   # Province ambiguity from CI width ∈ [0, 1]


@dataclass(frozen=True)
class UncertaintyResult:
    """
    Output of core/uncertainty.py for one cell.
    U_i^(c): total uncertainty ∈ [0, 1].
    Computed via PROBABILISTIC UNION: U = 1 - ∏(1 - u_k).
    """
    cell_id: str
    commodity: str
    components: UncertaintyComponents
    total_uncertainty: float                       # U_i^(c) ∈ [0, 1]


@dataclass(frozen=True)
class ComponentScoreBundle:
    """
    Complete set of all six component scores for one cell.
    Passed as a unit to core/scoring.py (Phase J) for ACIF computation.
    """
    cell_id: str
    commodity: str
    evidence: EvidenceResult
    causal: CausalResult
    physics: PhysicsResult
    temporal: TemporalResult
    province_prior: ProvincePriorResult
    uncertainty: UncertaintyResult