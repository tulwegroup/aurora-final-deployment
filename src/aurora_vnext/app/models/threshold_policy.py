"""
Aurora OSI vNext — Threshold Policy Models
Phase F §F.3

ThresholdSet: three ACIF cut-points {t1 > t2 > t3} defining the tier boundaries.
ThresholdPolicy: ThresholdSet + provenance metadata.

CONSTITUTIONAL RULE (Phase 0 v1.1, Rule 6):
  Thresholds are FROZEN at canonical freeze.
  Provenance (ThresholdSourceEnum) is a REQUIRED field — never optional.
  No router, service, or API endpoint may derive or substitute thresholds
  after a scan is COMPLETED. That is exclusively core/tiering.py's domain.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ThresholdSourceEnum

BoundedScore = Annotated[float, Field(ge=0.0, le=1.0)]


class ThresholdSet(BaseModel):
    """
    Three ACIF score cut-points defining tier boundaries for one scan.

    Tier assignment (§13.2):
      ACIF >= t1  → TIER_1
      t2 <= ACIF < t1 → TIER_2
      t3 <= ACIF < t2 → TIER_3
      ACIF < t3   → BELOW

    Ordering invariant: t1 > t2 > t3 > 0
    All values in (0, 1].
    """

    t1: BoundedScore = Field(gt=0.0, description="Tier 1 lower bound (highest confidence)")
    t2: BoundedScore = Field(gt=0.0, description="Tier 2 lower bound")
    t3: BoundedScore = Field(gt=0.0, description="Tier 3 lower bound")

    @model_validator(mode="after")
    def validate_ordering(self) -> "ThresholdSet":
        if not (self.t1 > self.t2 > self.t3 > 0.0):
            raise ValueError(
                f"Threshold ordering violated: t1={self.t1} > t2={self.t2} > t3={self.t3} > 0 "
                f"must hold. Got t1={self.t1}, t2={self.t2}, t3={self.t3}."
            )
        return self

    model_config = {"frozen": True}


class ThresholdPolicy(BaseModel):
    """
    Complete threshold policy: values + provenance + commodity context.
    Persisted verbatim in every completed CanonicalScan.
    """

    thresholds: ThresholdSet
    source: ThresholdSourceEnum = Field(
        description="How these thresholds were derived — required, never inferred post-freeze"
    )
    commodity: str = Field(
        min_length=1,
        description="Commodity name for which these thresholds apply"
    )
    source_version: Optional[str] = Field(
        default=None,
        description="Version of the source (e.g. commodity_library_version for frozen defaults, "
                    "ground_truth_dataset_id for calibrated thresholds)"
    )
    aoi_percentile_p1: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="AOI percentile used for t1 (only set when source=aoi_percentile)"
    )
    aoi_percentile_p2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="AOI percentile used for t2 (only set when source=aoi_percentile)"
    )
    aoi_percentile_p3: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="AOI percentile used for t3 (only set when source=aoi_percentile)"
    )

    @model_validator(mode="after")
    def validate_aoi_percentile_fields(self) -> "ThresholdPolicy":
        if self.source == ThresholdSourceEnum.AOI_PERCENTILE:
            missing = [
                f for f, v in [
                    ("aoi_percentile_p1", self.aoi_percentile_p1),
                    ("aoi_percentile_p2", self.aoi_percentile_p2),
                    ("aoi_percentile_p3", self.aoi_percentile_p3),
                ] if v is None
            ]
            if missing:
                raise ValueError(
                    f"ThresholdPolicy with source=aoi_percentile must provide "
                    f"all three percentile fields. Missing: {missing}"
                )
        return self

    model_config = {"frozen": True}