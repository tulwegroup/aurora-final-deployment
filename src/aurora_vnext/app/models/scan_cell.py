"""
Aurora OSI vNext — Scan Cell Model
Phase F §F.5

ScanCell: full per-cell scientific output, including the complete component
score stack, ACIF value, tier assignment, physics residuals, veto flags,
observable vector reference, and spatial geometry.

One ScanCell record is produced per spatial cell per scan.
ScanCells are written once at canonical freeze alongside the CanonicalScan
and never modified.

ARCHITECTURAL RULE: ScanCell is part of the canonical result layer.
It is not a pipeline execution record. It does not exist until canonical freeze.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import TierLabel
from app.models.observable_vector import NormalisedFloat


class ScanCell(BaseModel):
    """
    Full scored and tiered output for one spatial cell in a scan.
    All score fields are in [0, 1] per Phase B mathematics.
    """

    # -------------------------------------------------------------------------
    # Spatial identity
    # -------------------------------------------------------------------------
    cell_id: str = Field(min_length=1, description="Unique cell identifier within this scan")
    scan_id: str = Field(min_length=1, description="Parent scan ID")
    lat_center: float = Field(ge=-90.0, le=90.0)
    lon_center: float = Field(ge=-180.0, le=180.0)
    cell_size_degrees: float = Field(gt=0.0, description="Cell width/height in decimal degrees")
    environment: str = Field(description="ONSHORE | OFFSHORE | COMBINED")

    # -------------------------------------------------------------------------
    # Component score stack — six independent scores from Phase I modules
    # -------------------------------------------------------------------------
    evidence_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="Ẽ_i^(c): clustering-adjusted evidence score (§4.3)"
    )
    causal_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="C_i^(c): causal consistency score (§5.1)"
    )
    physics_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="Ψ_i: physics consistency score (§6.4)"
    )
    temporal_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="T_i^(c): temporal coherence score (§7.2)"
    )
    province_prior: Optional[NormalisedFloat] = Field(
        default=None,
        description="Π^(c)(r_i): province prior score (§8.2)"
    )
    uncertainty: Optional[NormalisedFloat] = Field(
        default=None,
        description="U_i^(c): total uncertainty (§10.3). Higher = more uncertain."
    )

    # -------------------------------------------------------------------------
    # ACIF and tier assignment — computed by Phase J modules
    # -------------------------------------------------------------------------
    acif_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="ACIF_i^(c) = Ẽ·C·Ψ·T·Π·(1-U) — §11.1. Zero if any hard veto fires."
    )
    tier: Optional[TierLabel] = Field(
        default=None,
        description="Tier assigned to this cell against frozen ThresholdPolicy (§13.2)"
    )

    # -------------------------------------------------------------------------
    # Physics residuals — first-class outputs, not diagnostic values (§6.1, §6.2)
    # -------------------------------------------------------------------------
    gravity_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_grav = ||W_d(g_obs - g_pred)||² (§6.1)"
    )
    physics_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_phys = ||∇²Φ - 4πGρ||² (§6.2)"
    )
    darcy_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_darcy for fluid/hydrocarbon systems (§6.5)"
    )
    water_column_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_wc for offshore water column correction (§6.5)"
    )

    # -------------------------------------------------------------------------
    # Veto flags — explicit boolean markers for audit and debugging
    # -------------------------------------------------------------------------
    causal_veto_fired: bool = Field(
        default=False,
        description="True if any causal hard veto triggered C=0 for this cell (§5.2)"
    )
    physics_veto_fired: bool = Field(
        default=False,
        description="True if physics residuals exceeded tolerance bound (§6.6)"
    )
    temporal_veto_fired: bool = Field(
        default=False,
        description="True if T_i < τ_temp_veto threshold (§7.4)"
    )
    province_veto_fired: bool = Field(
        default=False,
        description="True if province is geologically impossible for this commodity (§8.3)"
    )
    offshore_gate_blocked: bool = Field(
        default=False,
        description="True if cell is offshore and failed the offshore correction gate (§9)"
    )

    # -------------------------------------------------------------------------
    # Uncertainty component breakdown — persisted for full audit trail
    # -------------------------------------------------------------------------
    u_sensor: Optional[NormalisedFloat] = Field(
        default=None, description="Sensor coverage uncertainty component (§10.2)"
    )
    u_model: Optional[NormalisedFloat] = Field(
        default=None, description="Inversion model uncertainty component (§10.2)"
    )
    u_physics: Optional[NormalisedFloat] = Field(
        default=None, description="Physics residual uncertainty = 1 - Ψ_i (§10.2)"
    )
    u_temporal: Optional[NormalisedFloat] = Field(
        default=None, description="Temporal instability uncertainty = 1 - T_i (§10.2)"
    )
    u_prior: Optional[NormalisedFloat] = Field(
        default=None, description="Province ambiguity uncertainty (§10.2)"
    )

    # -------------------------------------------------------------------------
    # Observable vector reference
    # -------------------------------------------------------------------------
    observable_coverage_fraction: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of the 42 observables that were present (non-null)"
    )
    missing_observable_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=42,
        description="Count of null observables — directly drives u_sensor"
    )

    model_config = {"frozen": True}