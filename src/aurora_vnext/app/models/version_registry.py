"""
Aurora OSI vNext — Version Registry Model
Phase F §F.2

Every completed CanonicalScan persists a full VersionRegistry snapshot.
This makes every historical scan result fully reproducible — you know
exactly which model versions, graph versions, and pipeline versions
were used to produce it.

CONSTITUTIONAL RULE: Version fields are IMMUTABLE after canonical freeze.
If any version bumps, a new scan or reprocess event is required.
The VersionRegistry in a historical CanonicalScan must never be updated
in place — it is a frozen record of the scientific state at scan time.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Semantic versioning pattern: MAJOR.MINOR.PATCH
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _validate_semver(v: str, field_name: str) -> str:
    if not _SEMVER_PATTERN.match(v):
        raise ValueError(
            f"Version field '{field_name}' must be semantic version (X.Y.Z), got '{v}'"
        )
    return v


class VersionRegistry(BaseModel):
    """
    Locked version snapshot persisted with every completed CanonicalScan.

    All 8 fields are required. Defaults are sourced from config/versions.py
    and overridden by environment variable pins at scan-freeze time.
    """

    score_version: str = Field(
        description="Version of the ACIF scoring formula and weights (core/scoring.py)"
    )
    tier_version: str = Field(
        description="Version of the tiering engine and default thresholds (core/tiering.py)"
    )
    causal_graph_version: str = Field(
        description="Version of the causal DAG definition for the scanned commodity"
    )
    physics_model_version: str = Field(
        description="Version of the physics residual model (gravity, Poisson, Darcy)"
    )
    temporal_model_version: str = Field(
        description="Version of the temporal coherence model and decay weights"
    )
    province_prior_version: str = Field(
        description="Version of the tectono-stratigraphic province prior database"
    )
    commodity_library_version: str = Field(
        description="Version of the 40-commodity Θ_c parameter library"
    )
    scan_pipeline_version: str = Field(
        description="Version of the 21-step scan execution pipeline"
    )

    @field_validator(
        "score_version", "tier_version", "causal_graph_version",
        "physics_model_version", "temporal_model_version",
        "province_prior_version", "commodity_library_version",
        "scan_pipeline_version",
        mode="before",
    )
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not _SEMVER_PATTERN.match(str(v)):
            raise ValueError(
                f"Version must be semantic version (X.Y.Z), got '{v}'"
            )
        return v

    def as_dict(self) -> dict[str, str]:
        return self.model_dump()

    model_config = {"frozen": True}