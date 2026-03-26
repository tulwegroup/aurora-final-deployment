"""
Aurora OSI vNext — Digital Twin Models
Phase F §F.6

DigitalTwinVoxel: 3D volumetric representation of one depth column
built by projecting 2D scan cell outputs through a depth kernel D^(c)(z) (§15.2).

All voxel values are deterministic projections from a frozen CanonicalScan.
No voxel value may be computed independently of its parent canonical scan.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.observable_vector import NormalisedFloat


class DigitalTwinVoxel(BaseModel):
    """
    One 3D voxel in the sovereign digital twin (§15).

    A voxel represents a depth column at a specific (lat, lon) cell location.
    Multiple voxels exist per cell — one per depth slice.

    All probability and score values are projections from the parent CanonicalScan
    via the depth kernel. They must not be recomputed at query time.
    """

    voxel_id: str = Field(min_length=1)
    scan_id: str = Field(min_length=1, description="Parent CanonicalScan.scan_id")
    twin_version: int = Field(ge=1, description="Monotonic version index for this scan's twin")

    # Spatial identity
    lat_center: float = Field(ge=-90.0, le=90.0)
    lon_center: float = Field(ge=-180.0, le=180.0)
    depth_m: float = Field(ge=0.0, description="Centre depth of this voxel in metres")
    depth_range_m: tuple[float, float] = Field(
        description="(depth_min, depth_max) bounds of this depth slice in metres"
    )

    # Commodity probability at this depth (from depth kernel projection)
    commodity_probs: dict[str, NormalisedFloat] = Field(
        description="Commodity name → probability at this depth. "
                    "Derived from cell ACIF via depth kernel D^(c)(z, z_expected) (§15.2)."
    )

    # Physical properties at this depth
    expected_density: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Expected bulk density at this depth (kg/m³) from inversion model"
    )
    density_uncertainty: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Density estimate uncertainty (kg/m³)"
    )

    # Propagated scores at this depth (from parent cell)
    temporal_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="T_i from parent cell — temporal stability at this location"
    )
    physics_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_phys from parent cell — physics consistency at this location"
    )
    uncertainty: Optional[NormalisedFloat] = Field(
        default=None,
        description="U_i from parent cell — total uncertainty at this location"
    )

    # PostGIS geometry reference (populated by storage layer)
    geometry_wkt: Optional[str] = Field(
        default=None,
        description="WKT geometry for this voxel (stored as PostGIS geometry in DB)"
    )

    created_at: datetime = Field(description="When this voxel was written")

    model_config = {"frozen": True}


class TwinMetadata(BaseModel):
    """Summary metadata for a digital twin associated with one CanonicalScan."""

    scan_id: str
    current_version: int = Field(ge=1)
    total_voxels: int = Field(ge=0)
    depth_range_m: tuple[float, float]
    commodity: str
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}


class TwinQuery(BaseModel):
    """
    Query parameters for voxel filtering.
    Used by POST /twin/{id}/query.
    """

    scan_id: str = Field(min_length=1)
    commodity: Optional[str] = Field(default=None)
    min_probability: Optional[NormalisedFloat] = Field(
        default=None,
        description="Minimum commodity probability filter"
    )
    depth_min_m: Optional[float] = Field(default=None, ge=0.0)
    depth_max_m: Optional[float] = Field(default=None, ge=0.0)
    bounds: Optional[dict] = Field(
        default=None,
        description="GeoJSON bounding box for spatial filter"
    )
    version: Optional[int] = Field(
        default=None,
        ge=1,
        description="Specific twin version to query. Defaults to current."
    )
    limit: int = Field(default=500, ge=1, le=10000)


class TwinQueryResult(BaseModel):
    """Result of a TwinQuery."""

    scan_id: str
    twin_version: int
    voxels: list[DigitalTwinVoxel]
    total_matching: int = Field(ge=0)
    query: TwinQuery

    model_config = {"frozen": True}


class TwinVersion(BaseModel):
    """A historical version entry in the twin's version history."""

    scan_id: str
    version: int = Field(ge=1)
    voxel_count: int = Field(ge=0)
    created_at: datetime
    trigger: str = Field(description="What triggered this version: 'initial' | 'reprocess'")
    parent_version: Optional[int] = Field(default=None, ge=1)

    model_config = {"frozen": True}