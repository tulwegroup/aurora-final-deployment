"""
Aurora OSI vNext — Scan Request and Status Response Models
Phase F §F.8

Models for scan submission and status polling.

ARCHITECTURAL RULE:
  ScanStatusResponse returns ONLY ScanJob execution fields when status ≠ COMPLETED.
  When status = COMPLETED, it returns a CanonicalScanSummary projection.
  These two payloads use distinct response types — never mixed.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.canonical_scan import CanonicalScanSummary
from app.models.enums import (
    PipelineStageEnum,
    ScanEnvironment,
    ScanStatus,
    ScanTier,
)


# ---------------------------------------------------------------------------
# Scan submission geometry types
# ---------------------------------------------------------------------------

class ScanPolygon(BaseModel):
    """GeoJSON Polygon geometry for a scan AOI."""

    type: str = Field(default="Polygon")
    coordinates: list[list[list[float]]] = Field(
        description="GeoJSON polygon coordinate rings: [[[lon, lat], ...]]"
    )

    @model_validator(mode="after")
    def validate_type(self) -> "ScanPolygon":
        if self.type != "Polygon":
            raise ValueError("ScanPolygon.type must be 'Polygon'")
        return self


class ScanGrid(BaseModel):
    """Regular grid specification for a scan AOI."""

    min_lat: float = Field(ge=-90.0, le=90.0)
    max_lat: float = Field(ge=-90.0, le=90.0)
    min_lon: float = Field(ge=-180.0, le=180.0)
    max_lon: float = Field(ge=-180.0, le=180.0)
    resolution_degrees: float = Field(gt=0.0, le=10.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ScanGrid":
        if self.max_lat <= self.min_lat:
            raise ValueError("max_lat must be > min_lat")
        if self.max_lon <= self.min_lon:
            raise ValueError("max_lon must be > min_lon")
        return self


# ---------------------------------------------------------------------------
# Scan submission request models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    """
    Common scan submission parameters.
    Geometry is provided via one of: aoi_polygon, grid (mutually exclusive).
    """

    commodity: str = Field(min_length=1, description="Target commodity name from commodity library")
    scan_tier: ScanTier = Field(description="BOOTSTRAP | SMART | PREMIUM")
    environment: ScanEnvironment = Field(
        default=ScanEnvironment.ONSHORE,
        description="ONSHORE | OFFSHORE | COMBINED"
    )
    aoi_polygon: Optional[ScanPolygon] = Field(
        default=None,
        description="Free-form polygon AOI (mutually exclusive with grid)"
    )
    grid: Optional[ScanGrid] = Field(
        default=None,
        description="Regular grid AOI (mutually exclusive with aoi_polygon)"
    )
    date_range_start: Optional[datetime] = Field(
        default=None,
        description="Start of temporal window for sensor data acquisition"
    )
    date_range_end: Optional[datetime] = Field(
        default=None,
        description="End of temporal window for sensor data acquisition"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional operator notes for this scan"
    )

    @model_validator(mode="after")
    def validate_geometry_exclusive(self) -> "ScanRequest":
        if self.aoi_polygon is not None and self.grid is not None:
            raise ValueError(
                "ScanRequest must provide either aoi_polygon or grid — not both."
            )
        if self.aoi_polygon is None and self.grid is None:
            raise ValueError(
                "ScanRequest must provide either aoi_polygon or grid."
            )
        return self

    @model_validator(mode="after")
    def validate_date_range(self) -> "ScanRequest":
        if (
            self.date_range_start is not None
            and self.date_range_end is not None
            and self.date_range_end <= self.date_range_start
        ):
            raise ValueError("date_range_end must be after date_range_start")
        return self


# ---------------------------------------------------------------------------
# Scan submission response
# ---------------------------------------------------------------------------

class ScanSubmitResponse(BaseModel):
    """
    Response returned immediately after scan submission.
    Contains scan_id and initial job state only — no score fields.
    """

    scan_id: str = Field(min_length=1)
    scan_job_id: str = Field(min_length=1)
    status: ScanStatus = Field(default=ScanStatus.PENDING)
    submitted_at: datetime
    message: str = Field(default="Scan submitted successfully")

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Scan status response — strict type separation
# ---------------------------------------------------------------------------

class ScanJobStatusResponse(BaseModel):
    """
    Status response for an IN-PROGRESS scan (status ≠ COMPLETED).
    Contains ONLY ScanJob execution fields — no score fields.

    ARCHITECTURAL RULE: This response type must never contain
    display_acif_score, tier_counts, system_status, or any other
    CanonicalScan score field. That is the CanonicalScanSummary's domain.
    """

    scan_id: str
    scan_job_id: str
    status: ScanStatus
    pipeline_stage: Optional[PipelineStageEnum] = None
    progress_pct: Optional[float] = None
    started_at: Optional[datetime] = None
    updated_at: datetime
    error_detail: Optional[str] = None

    # =========================================================================
    # SCORE FIELD EXCLUSION — explicit by absence:
    # display_acif_score, tier_counts, system_status, gate_results,
    # threshold_policy, component scores — ALL absent by design.
    # =========================================================================

    model_config = {"frozen": True}


class ScanStatusResponse(BaseModel):
    """
    Unified status response that cleanly separates running vs completed state.

    - If running: job_status is populated, canonical_summary is None.
    - If completed: canonical_summary is populated, job_status carries minimal info.

    Clients must check status field to determine which sub-model to use.
    """

    scan_id: str
    status: ScanStatus
    job_status: Optional[ScanJobStatusResponse] = Field(
        default=None,
        description="Present when status is PENDING, RUNNING, or FAILED"
    )
    canonical_summary: Optional[CanonicalScanSummary] = Field(
        default=None,
        description="Present when status is COMPLETED"
    )

    @model_validator(mode="after")
    def validate_state_separation(self) -> "ScanStatusResponse":
        if self.status == ScanStatus.COMPLETED:
            if self.canonical_summary is None:
                raise ValueError(
                    "ScanStatusResponse with status=COMPLETED must provide canonical_summary."
                )
        else:
            if self.job_status is None:
                raise ValueError(
                    f"ScanStatusResponse with status={self.status} must provide job_status."
                )
        return self

    model_config = {"frozen": True}