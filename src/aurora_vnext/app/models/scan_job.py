"""
Aurora OSI vNext — ScanJob Model
Phase F §F.5

ScanJob is the MUTABLE pipeline execution record.
It tracks ONLY the state of a scan during active pipeline processing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL DISTINCTION (Phase C refinement / Phase D §L note):

  ScanJob      = MUTABLE  — updated throughout pipeline execution (steps 1–18)
  CanonicalScan = IMMUTABLE — written ONCE at canonical freeze (step 19)

ScanJob fields:
  ✅  pipeline_stage, progress_pct, updated_at, error_detail
  ✅  scan_id_ref (foreign key to the canonical scan record being built)
  ❌  NO score fields (no acif_score, no display_score, no tier data)
  ❌  NO threshold fields
  ❌  NO gate results
  ❌  NO component scores (evidence, causal, physics, etc.)

After canonical freeze, ScanJob is ARCHIVED (not deleted).
It is never exposed through result-bearing API endpoints.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

No scientific logic. No score fields. No imports from core/ or services/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import PipelineStageEnum, ScanStatus


class ScanJob(BaseModel):
    """
    Mutable pipeline execution record for one active scan.

    ⚠️  This model deliberately contains ZERO score-equivalent fields.
        Any ACIF, tier, threshold, gate, or component score field
        in this model is a constitutional violation.
    """

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    scan_job_id: str = Field(min_length=1, description="Unique pipeline job ID")
    scan_id_ref: str = Field(
        min_length=1,
        description="Reference to the CanonicalScan.scan_id being built by this job"
    )

    # -------------------------------------------------------------------------
    # Execution state — the ONLY fields ScanJob carries
    # -------------------------------------------------------------------------
    status: ScanStatus = Field(
        default=ScanStatus.PENDING,
        description="Current pipeline execution status (PENDING | RUNNING | COMPLETED | FAILED)"
    )
    pipeline_stage: Optional[PipelineStageEnum] = Field(
        default=None,
        description="Current named stage within the 21-step pipeline"
    )
    progress_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Pipeline completion percentage [0, 100]"
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: datetime = Field(description="When this ScanJob was created")
    started_at: Optional[datetime] = Field(
        default=None,
        description="When pipeline execution began (None if still PENDING)"
    )
    updated_at: datetime = Field(description="Last state update timestamp")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When pipeline completed or failed (None if still running)"
    )

    # -------------------------------------------------------------------------
    # Error handling
    # -------------------------------------------------------------------------
    error_detail: Optional[str] = Field(
        default=None,
        max_length=4096,
        description="Error message if status=FAILED"
    )
    error_stage: Optional[PipelineStageEnum] = Field(
        default=None,
        description="Pipeline stage at which the error occurred"
    )

    # -------------------------------------------------------------------------
    # Archival flag — set after canonical freeze
    # -------------------------------------------------------------------------
    is_archived: bool = Field(
        default=False,
        description="Set True after canonical freeze. Archived jobs are excluded from active lists."
    )

    # =========================================================================
    # SCORE FIELD EXCLUSION ZONE
    # The following fields are explicitly ABSENT from ScanJob — by design:
    #   display_acif_score, max_acif_score, weighted_acif_score
    #   evidence_score, causal_score, physics_score, temporal_score
    #   province_prior, uncertainty
    #   tier_counts, threshold_policy, tier_threshold_source
    #   gate_results, system_status, confirmation_reason
    #   observable_vector, version_registry
    #
    # All of the above belong exclusively in CanonicalScan.
    # If you find any of the above in this model, it is a constitutional violation.
    # =========================================================================