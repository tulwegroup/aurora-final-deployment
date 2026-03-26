"""
Aurora OSI vNext — Gate Logic and System Status Engine
Phase J §J.3 | Phase B §13

CONSTITUTIONAL RULE: This is the SOLE location for system status derivation.
No API handler, service, or storage layer may independently derive system status.

═══════════════════════════════════════════════════════════════════
SYSTEM STATUS DEFINITIONS (§13.1)
═══════════════════════════════════════════════════════════════════

  PASS_CONFIRMED:    Strong, spatially coherent, physically consistent signal.
                     High Tier-1/2 fraction + spatial clustering + low uncertainty.

  PARTIAL_SIGNAL:    Detectable but incomplete signal.
                     Moderate Tier-1/2 fraction OR isolated high-ACIF cells
                     OR physics/temporal degradation present.

  INCONCLUSIVE:      Signal ambiguous — insufficient evidence or high uncertainty.
                     Low Tier-1 fraction AND high uncertainty envelope.

  REJECTED:          Geologically or physically impossible response.
                     Province veto OR physics veto coverage > τ_reject.

  OVERRIDE_CONFIRMED: Admin override with documented reason.
                      Status set externally; stored in canonical_scans.

═══════════════════════════════════════════════════════════════════
GATE EVALUATION (§13.2)
═══════════════════════════════════════════════════════════════════

  Gates are evaluated in priority order (higher priority wins):
    1. REJECTED     — if hard rejection conditions met (vetoes dominate)
    2. OVERRIDE_CONFIRMED — if admin override active (skips all gate logic)
    3. PASS_CONFIRMED — if all positive criteria satisfied
    4. PARTIAL_SIGNAL — if partial criteria met
    5. INCONCLUSIVE   — fallthrough

  Status derivation depends on:
    • Tier distribution (tier_counts): fraction in Tier 1+2
    • Spatial clustering: mean_clustering_metric of Tier-1 cells
    • Physics veto state: fraction of cells with physics veto fired
    • Temporal persistence: scan-level T_mean
    • Uncertainty envelope: scan-level U_mean

No imports from core/scoring, core/tiering, services/, storage/, api/.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SystemStatus(str, Enum):
    PASS_CONFIRMED      = "PASS_CONFIRMED"
    PARTIAL_SIGNAL      = "PARTIAL_SIGNAL"
    INCONCLUSIVE        = "INCONCLUSIVE"
    REJECTED            = "REJECTED"
    OVERRIDE_CONFIRMED  = "OVERRIDE_CONFIRMED"


@dataclass(frozen=True)
class GateInputs:
    """
    All inputs required for gate evaluation.
    Computed from scan-level aggregates — no ACIF formula here.

    Fields:
        n_cells:              Total cell count in scan
        n_tier_1:             Cells at Tier 1 (CONFIRMED)
        n_tier_2:             Cells at Tier 2 (HIGH)
        n_vetoed_cells:       Cells where any veto fired
        n_physics_vetoed:     Cells where physics veto specifically fired
        n_province_vetoed:    Cells where province veto fired
        mean_clustering_t1:   Mean κ_i of Tier-1 cells (spatial coherence metric)
        t_mean:               Scan-level mean temporal coherence T̄
        u_mean:               Scan-level mean total uncertainty Ū
        physics_veto_fraction: Fraction of cells with physics veto (≈ n_physics / n_cells)
        province_veto_fraction: Fraction of cells with province veto
        admin_override_active:  True if admin has set an explicit override status
        override_reason:       Required if admin_override_active is True
    """
    n_cells: int
    n_tier_1: int
    n_tier_2: int
    n_vetoed_cells: int
    n_physics_vetoed: int
    n_province_vetoed: int
    mean_clustering_t1: float          # κ̄ of Tier-1 cells ∈ [0, 1]
    t_mean: float                      # Mean temporal coherence ∈ [0, 1]
    u_mean: float                      # Mean total uncertainty ∈ [0, 1]
    physics_veto_fraction: float       # ∈ [0, 1]
    province_veto_fraction: float      # ∈ [0, 1]
    admin_override_active: bool = False
    override_reason: Optional[str] = None


@dataclass(frozen=True)
class GateEvaluationResult:
    """
    Full system gate evaluation output for one scan.
    The system_status field is the value stored in CanonicalScan.
    """
    system_status: SystemStatus

    # Which gate triggered the final status
    gate_triggered: str

    # Supporting rationale (human-readable, for ConfirmationReason model)
    rationale: str

    # Metric snapshot at evaluation time (for audit trail)
    tier_1_fraction: float
    tier_1_2_fraction: float
    mean_clustering_t1: float
    physics_veto_fraction: float
    t_mean: float
    u_mean: float

    # Whether any admin override was applied
    override_applied: bool = False


# ---------------------------------------------------------------------------
# Gate threshold parameters (must not be hard-coded in production calls)
# Defaults are provided for testing only — production uses Θ_c parameters.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateThresholds:
    """
    Gate evaluation threshold parameters.
    Sourced from Θ_c (commodity parameters) in Phase L orchestration.
    All field defaults are for TESTING ONLY — never used in production scans.
    """
    # PASS_CONFIRMED thresholds
    tau_pass_tier12_fraction: float = 0.25    # ≥ 25% Tier-1+2 cells required
    tau_pass_clustering: float       = 0.50   # Mean T1 clustering ≥ 0.5
    tau_pass_u_max: float            = 0.60   # Mean uncertainty ≤ 0.6
    tau_pass_t_min: float            = 0.40   # Mean temporal ≥ 0.4

    # PARTIAL_SIGNAL thresholds
    tau_partial_tier1_fraction: float = 0.05  # ≥ 5% Tier-1 cells
    tau_partial_tier12_fraction: float = 0.10 # OR ≥ 10% Tier-1+2 cells
    tau_partial_u_max: float          = 0.80  # Mean uncertainty ≤ 0.8

    # REJECTED thresholds
    tau_reject_physics_fraction: float  = 0.50  # > 50% physics-vetoed cells
    tau_reject_province_fraction: float = 0.80  # > 80% province-vetoed cells


def evaluate_gates(
    inputs: GateInputs,
    thresholds: Optional[GateThresholds] = None,
) -> GateEvaluationResult:
    """
    §13.2 — Evaluate all gates in priority order and return system status.

    Priority: REJECTED > OVERRIDE_CONFIRMED > PASS_CONFIRMED > PARTIAL_SIGNAL > INCONCLUSIVE

    Args:
        inputs:     GateInputs computed from scan-level aggregates.
        thresholds: GateThresholds from Θ_c. If None, uses defaults (testing only).

    Returns:
        GateEvaluationResult with system_status and full audit fields.
    """
    τ = thresholds or GateThresholds()
    n = max(inputs.n_cells, 1)

    tier_1_fraction   = inputs.n_tier_1 / n
    tier_12_fraction  = (inputs.n_tier_1 + inputs.n_tier_2) / n

    # ── Gate 1: REJECTED ─────────────────────────────────────────────────────
    # Physics vetoes dominate OR province vetoes dominate
    if (inputs.physics_veto_fraction > τ.tau_reject_physics_fraction
            or inputs.province_veto_fraction > τ.tau_reject_province_fraction):
        return GateEvaluationResult(
            system_status=SystemStatus.REJECTED,
            gate_triggered="REJECTED_VETO_DOMINANCE",
            rationale=(
                f"REJECTED: physics_veto_fraction={inputs.physics_veto_fraction:.3f} "
                f"(τ={τ.tau_reject_physics_fraction}) | "
                f"province_veto_fraction={inputs.province_veto_fraction:.3f} "
                f"(τ={τ.tau_reject_province_fraction})"
            ),
            tier_1_fraction=tier_1_fraction,
            tier_1_2_fraction=tier_12_fraction,
            mean_clustering_t1=inputs.mean_clustering_t1,
            physics_veto_fraction=inputs.physics_veto_fraction,
            t_mean=inputs.t_mean,
            u_mean=inputs.u_mean,
        )

    # ── Gate 2: OVERRIDE_CONFIRMED ───────────────────────────────────────────
    if inputs.admin_override_active:
        return GateEvaluationResult(
            system_status=SystemStatus.OVERRIDE_CONFIRMED,
            gate_triggered="ADMIN_OVERRIDE",
            rationale=f"OVERRIDE_CONFIRMED: reason={inputs.override_reason or 'not provided'}",
            tier_1_fraction=tier_1_fraction,
            tier_1_2_fraction=tier_12_fraction,
            mean_clustering_t1=inputs.mean_clustering_t1,
            physics_veto_fraction=inputs.physics_veto_fraction,
            t_mean=inputs.t_mean,
            u_mean=inputs.u_mean,
            override_applied=True,
        )

    # ── Gate 3: PASS_CONFIRMED ───────────────────────────────────────────────
    # Strong T1+2 fraction + spatial clustering + low uncertainty + temporal coherence
    pass_conditions = {
        "tier12_fraction":  tier_12_fraction  >= τ.tau_pass_tier12_fraction,
        "clustering":       inputs.mean_clustering_t1 >= τ.tau_pass_clustering,
        "uncertainty":      inputs.u_mean     <= τ.tau_pass_u_max,
        "temporal":         inputs.t_mean     >= τ.tau_pass_t_min,
    }
    if all(pass_conditions.values()):
        return GateEvaluationResult(
            system_status=SystemStatus.PASS_CONFIRMED,
            gate_triggered="PASS_ALL_CONDITIONS",
            rationale=(
                f"PASS_CONFIRMED: tier_12={tier_12_fraction:.3f}≥{τ.tau_pass_tier12_fraction} | "
                f"clustering={inputs.mean_clustering_t1:.3f}≥{τ.tau_pass_clustering} | "
                f"u_mean={inputs.u_mean:.3f}≤{τ.tau_pass_u_max} | "
                f"t_mean={inputs.t_mean:.3f}≥{τ.tau_pass_t_min}"
            ),
            tier_1_fraction=tier_1_fraction,
            tier_1_2_fraction=tier_12_fraction,
            mean_clustering_t1=inputs.mean_clustering_t1,
            physics_veto_fraction=inputs.physics_veto_fraction,
            t_mean=inputs.t_mean,
            u_mean=inputs.u_mean,
        )

    # ── Gate 4: PARTIAL_SIGNAL ───────────────────────────────────────────────
    # Some Tier-1 OR Tier-1+2 cells AND uncertainty not overwhelming
    partial_conditions = (
        (tier_1_fraction  >= τ.tau_partial_tier1_fraction
         or tier_12_fraction >= τ.tau_partial_tier12_fraction)
        and inputs.u_mean <= τ.tau_partial_u_max
    )
    if partial_conditions:
        # Describe which condition failed for PASS
        failed = [k for k, v in pass_conditions.items() if not v]
        return GateEvaluationResult(
            system_status=SystemStatus.PARTIAL_SIGNAL,
            gate_triggered="PARTIAL_ABOVE_NOISE",
            rationale=(
                f"PARTIAL_SIGNAL: tier_1={tier_1_fraction:.3f} | "
                f"tier_12={tier_12_fraction:.3f} | "
                f"u_mean={inputs.u_mean:.3f} | "
                f"PASS_failed_conditions={failed}"
            ),
            tier_1_fraction=tier_1_fraction,
            tier_1_2_fraction=tier_12_fraction,
            mean_clustering_t1=inputs.mean_clustering_t1,
            physics_veto_fraction=inputs.physics_veto_fraction,
            t_mean=inputs.t_mean,
            u_mean=inputs.u_mean,
        )

    # ── Gate 5: INCONCLUSIVE (fallthrough) ───────────────────────────────────
    return GateEvaluationResult(
        system_status=SystemStatus.INCONCLUSIVE,
        gate_triggered="INCONCLUSIVE_FALLTHROUGH",
        rationale=(
            f"INCONCLUSIVE: tier_1={tier_1_fraction:.3f} | "
            f"tier_12={tier_12_fraction:.3f} | "
            f"u_mean={inputs.u_mean:.3f} | "
            f"t_mean={inputs.t_mean:.3f}"
        ),
        tier_1_fraction=tier_1_fraction,
        tier_1_2_fraction=tier_12_fraction,
        mean_clustering_t1=inputs.mean_clustering_t1,
        physics_veto_fraction=inputs.physics_veto_fraction,
        t_mean=inputs.t_mean,
        u_mean=inputs.u_mean,
    )