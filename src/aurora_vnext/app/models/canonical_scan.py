"""
Aurora OSI vNext — CanonicalScan Model
Phase F §F.5

CanonicalScan is the SOLE, IMMUTABLE result contract for all Aurora scans.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTITUTIONAL RULES (Phase 0 v1.1):

Rule 1 (Single Compute): All scientific computation occurs ONCE at scan
  completion. The CanonicalScan object is the output of that single compute.
  No field is recomputed at read time.

Rule 2 (One Scoring Authority): ACIF is computed exclusively by core/scoring.py.
  CanonicalScan carries the RESULT. It does not carry the equation.

Rule 3 (Frontend Render-Only): All result-bearing API responses derive
  EXCLUSIVELY from CanonicalScan fields. No alternative score vocabulary.

Rule 6 (Threshold Immutability): Thresholds are frozen at canonical freeze.
  tier_thresholds_used carries frozen values. No post-completion substitution.

Rule 7 (Historical Immutability): CanonicalScan records are never modified
  after write. Reprocessing creates a NEW record with parent_scan_id.

Rule 8 (Version Binding): Every CanonicalScan persists the full VersionRegistry
  snapshot. Historical reproducibility is guaranteed.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CanonicalScan deliberately contains ZERO pipeline execution fields.
No pipeline_stage, progress_pct, updated_at (as execution field), error_detail.
Those belong exclusively in ScanJob.

No scientific logic. No scoring formulas. No imports from core/ or services/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    MigrationClassEnum,
    ScanEnvironment,
    ScanStatus,
    ScanTier,
    SystemStatusEnum,
)
from app.models.gate_results import GateResults, ConfirmationReason
from app.models.observable_vector import NormalisedFloat
from app.models.threshold_policy import ThresholdPolicy
from app.models.tier_counts import TierCounts
from app.models.version_registry import VersionRegistry


class CanonicalScan(BaseModel):
    """
    Immutable result contract for one completed Aurora scan.

    Written ONCE at canonical freeze (pipeline step 19).
    Never modified. Reprocessing creates a new record with parent_scan_id.

    ⚠️  This model deliberately contains ZERO pipeline execution fields.
        Any pipeline_stage, progress_pct, or error_detail in this model
        is a constitutional violation — those belong in ScanJob.
    """

    # -------------------------------------------------------------------------
    # Identity and status
    # -------------------------------------------------------------------------
    scan_id: str = Field(min_length=1, description="Globally unique scan identifier")
    status: ScanStatus = Field(
        description="Must be COMPLETED for a valid canonical record. "
                    "MIGRATION_STUB for legacy Class C records."
    )

    # -------------------------------------------------------------------------
    # Scan configuration — frozen at submission time
    # -------------------------------------------------------------------------
    commodity: str = Field(min_length=1, description="Target commodity name")
    scan_tier: ScanTier = Field(description="BOOTSTRAP | SMART | PREMIUM")
    environment: ScanEnvironment = Field(description="ONSHORE | OFFSHORE | COMBINED")
    aoi_geojson: dict = Field(description="GeoJSON geometry of the area of interest")
    grid_resolution_degrees: float = Field(
        gt=0.0,
        description="Spatial grid resolution used for scan cell decomposition"
    )
    total_cells: int = Field(ge=0, description="Total number of scan cells in this scan")

    # -------------------------------------------------------------------------
    # Aggregate ACIF scores — §12 (computed by core/scoring.py ONLY)
    # -------------------------------------------------------------------------
    display_acif_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="Mean cell ACIF score — primary display metric (§12.1)"
    )
    max_acif_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="Maximum cell ACIF score across the AOI (§12.2)"
    )
    weighted_acif_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="Spatially weighted ACIF score (§12.3)"
    )

    # -------------------------------------------------------------------------
    # Tier summary — §13 (computed by core/tiering.py ONLY)
    # -------------------------------------------------------------------------
    tier_counts: Optional[TierCounts] = Field(
        default=None,
        description="Cell count per tier. Invariant: sum == total_cells"
    )
    tier_thresholds_used: Optional[ThresholdPolicy] = Field(
        default=None,
        description="Frozen threshold policy used to assign tiers. "
                    "GeoJSON rendering uses these values — never recomputes."
    )

    # -------------------------------------------------------------------------
    # System status and gate results — §14 (computed by core/gates.py ONLY)
    # -------------------------------------------------------------------------
    system_status: Optional[SystemStatusEnum] = Field(
        default=None,
        description="PASS_CONFIRMED | PARTIAL_SIGNAL | INCONCLUSIVE | REJECTED | OVERRIDE_CONFIRMED"
    )
    gate_results: Optional[GateResults] = Field(
        default=None,
        description="Full per-gate evaluation set"
    )
    confirmation_reason: Optional[ConfirmationReason] = Field(
        default=None,
        description="Structured explanation of system_status derivation"
    )

    # -------------------------------------------------------------------------
    # Score statistics — persisted for analytics; not re-derived from cells
    # -------------------------------------------------------------------------
    mean_evidence_score: Optional[NormalisedFloat] = Field(
        default=None, description="Mean Ẽ_i across all cells"
    )
    mean_causal_score: Optional[NormalisedFloat] = Field(
        default=None, description="Mean C_i across all cells"
    )
    mean_physics_score: Optional[NormalisedFloat] = Field(
        default=None, description="Mean Ψ_i across all cells"
    )
    mean_temporal_score: Optional[NormalisedFloat] = Field(
        default=None, description="Mean T_i across all cells"
    )
    mean_province_prior: Optional[NormalisedFloat] = Field(
        default=None, description="Mean Π_i across all cells"
    )
    mean_uncertainty: Optional[NormalisedFloat] = Field(
        default=None, description="Mean U_i across all cells"
    )

    # -------------------------------------------------------------------------
    # Hard veto cell counts — diagnostic summary
    # -------------------------------------------------------------------------
    causal_veto_cell_count: Optional[int] = Field(
        default=None, ge=0,
        description="Cells where causal hard veto fired (C=0)"
    )
    physics_veto_cell_count: Optional[int] = Field(
        default=None, ge=0,
        description="Cells where physics veto fired"
    )
    province_veto_cell_count: Optional[int] = Field(
        default=None, ge=0,
        description="Cells where province impossibility veto fired (P=0)"
    )
    offshore_blocked_cell_count: Optional[int] = Field(
        default=None, ge=0,
        description="Offshore cells blocked by correction gate"
    )

    # -------------------------------------------------------------------------
    # Offshore metadata
    # -------------------------------------------------------------------------
    offshore_cell_count: Optional[int] = Field(
        default=None, ge=0,
        description="Number of offshore cells in this scan"
    )
    water_column_corrected: bool = Field(
        default=False,
        description="True if water-column correction was applied to any cell"
    )

    # -------------------------------------------------------------------------
    # Version registry snapshot — frozen at canonical freeze time
    # -------------------------------------------------------------------------
    version_registry: Optional[VersionRegistry] = Field(
        default=None,
        description="Complete locked version state at scan completion time. "
                    "Required for scientific reproducibility."
    )

    # -------------------------------------------------------------------------
    # Normalisation parameters — frozen per-scan μ_k, σ_k (§3.2)
    # Stored as {observable_key: {"mu": float, "sigma": float}}
    # -------------------------------------------------------------------------
    normalisation_params: Optional[dict[str, dict[str, float]]] = Field(
        default=None,
        description="Per-observable normalisation parameters μ_k and σ_k computed for this AOI. "
                    "Keys match ObservableVector field names. Required for reproducibility."
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    submitted_at: datetime = Field(description="When the scan was submitted to the pipeline")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When canonical freeze occurred. None if not yet COMPLETED."
    )

    # -------------------------------------------------------------------------
    # Reprocessing lineage
    # -------------------------------------------------------------------------
    parent_scan_id: Optional[str] = Field(
        default=None,
        description="scan_id of the parent scan if this is a reprocess. "
                    "None for original scans."
    )
    reprocess_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Human-readable reason for reprocessing"
    )
    reprocess_changed_params: Optional[dict] = Field(
        default=None,
        description="Dict of {param_name: {old: v, new: v}} for params changed in reprocess"
    )

    # -------------------------------------------------------------------------
    # Migration metadata (Phase R — Class B and C legacy records)
    # -------------------------------------------------------------------------
    migration_class: Optional[MigrationClassEnum] = Field(
        default=None,
        description="Set for migrated legacy records: A (full), B (partial), C (stub)"
    )
    migration_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Notes from migration process explaining null fields or provenance decisions"
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_completed_scan_fields(self) -> "CanonicalScan":
        """
        A COMPLETED (non-migration-stub) scan must have core result fields populated.
        PENDING/RUNNING status records exist briefly during pipeline and should not
        appear in external API responses.
        """
        if self.status == ScanStatus.COMPLETED:
            missing_critical = []
            if self.display_acif_score is None:
                missing_critical.append("display_acif_score")
            if self.tier_counts is None:
                missing_critical.append("tier_counts")
            if self.tier_thresholds_used is None:
                missing_critical.append("tier_thresholds_used")
            if self.system_status is None:
                missing_critical.append("system_status")
            if self.version_registry is None:
                missing_critical.append("version_registry")
            if self.completed_at is None:
                missing_critical.append("completed_at")
            if missing_critical:
                raise ValueError(
                    f"CanonicalScan with status=COMPLETED is missing required fields: "
                    f"{missing_critical}. All critical fields must be set at canonical freeze."
                )
        return self

    @model_validator(mode="after")
    def validate_tier_counts_match_total(self) -> "CanonicalScan":
        """TierCounts.total_cells must match CanonicalScan.total_cells if both present."""
        if self.tier_counts is not None:
            if self.tier_counts.total_cells != self.total_cells:
                raise ValueError(
                    f"tier_counts.total_cells ({self.tier_counts.total_cells}) must equal "
                    f"canonical_scan.total_cells ({self.total_cells})."
                )
        return self

    model_config = {"frozen": True}


class CanonicalScanSummary(BaseModel):
    """
    Lightweight projection of CanonicalScan for list views and history index.
    All fields sourced directly from the canonical record — no re-derivation.
    """

    scan_id: str
    commodity: str
    scan_tier: ScanTier
    environment: ScanEnvironment
    status: ScanStatus
    display_acif_score: Optional[NormalisedFloat] = None
    max_acif_score: Optional[NormalisedFloat] = None
    system_status: Optional[SystemStatusEnum] = None
    tier_1_count: Optional[int] = None
    total_cells: int
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    parent_scan_id: Optional[str] = None
    migration_class: Optional[MigrationClassEnum] = None

    model_config = {"frozen": True}