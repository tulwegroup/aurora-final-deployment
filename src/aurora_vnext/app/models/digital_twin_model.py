"""
Aurora OSI vNext — Digital Twin Models
Phase F §F.6 | Phase N (DepthKernelConfig, VoxelLineage added)

DigitalTwinVoxel: 3D volumetric representation of one depth column
built by projecting 2D scan cell outputs through a depth kernel D^(c)(z) (§15.2).

All voxel values are deterministic projections from a frozen CanonicalScan.
No voxel value may be computed independently of its parent canonical scan.

Phase N additions:
  DepthKernelConfig: commodity-specific depth kernel parameters.
  VoxelLineage:      per-voxel audit record linking every field value back
                     to the canonical scan_id, cell_id, and version_registry.

CONSTITUTIONAL RULE: No scientific logic, no scoring formulas.
No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.observable_vector import NormalisedFloat


# ---------------------------------------------------------------------------
# Depth kernel configuration — sourced from Θ_c (commodity config)
# ---------------------------------------------------------------------------

class DepthKernelConfig(BaseModel):
    """
    Depth kernel D^(c)(z) parameters for one commodity.

    The depth kernel maps a 2D cell's ACIF score to a probability-vs-depth
    profile, modelling how likely the anomaly is to correspond to a mineral
    system at each depth slice.

    Formula (§15.2):
      D^(c)(z) = exp(−(z − z_expected)² / (2 × σ_z²))
      p(z) = ACIF_i × D^(c)(z)   [clamped to [0, 1]]

    Parameters:
      z_expected_m:  Expected target depth (metres) for this commodity.
                     Sourced from Θ_c.family depth range mid-point.
      sigma_z_m:     Depth uncertainty (metres). Controls kernel width.
                     Wider σ_z → shallower certainty about depth.
      depth_slices_m: Ordered list of depth slice centres to generate.
                     e.g. [100, 200, 300, 500, 750, 1000] metres.
      density_gradient: dρ/dz (kg/m³ per metre) — how density increases
                     with depth (crustal gradient for this family).

    All parameters are sourced from Θ_c — never hard-coded per-scan.
    """
    commodity: str
    z_expected_m: float = Field(gt=0.0, description="Expected target depth (m)")
    sigma_z_m: float = Field(gt=0.0, description="Depth kernel width σ_z (m)")
    depth_slices_m: list[float] = Field(
        min_length=1,
        description="Ordered depth slice centres in metres"
    )
    density_gradient_kg_m3_per_m: float = Field(
        default=0.3,
        description="Crustal density gradient dρ/dz (kg/m³/m)"
    )
    background_density_kg_m3: float = Field(
        default=2670.0,
        description="Surface reference density (kg/m³)"
    )

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Voxel lineage — per-voxel traceback to canonical source
# ---------------------------------------------------------------------------

class VoxelLineage(BaseModel):
    """
    Audit record linking every voxel field value to its canonical source.

    PHASE N REQUIREMENT: Every voxel must be traceable back to the canonical
    scan_id, source cell_id, and the version_registry active at build time.

    Proof of no re-scoring: all score fields in lineage carry the value
    read from the frozen ScanCell record — not recomputed.
    """
    voxel_id: str
    scan_id: str
    cell_id: str                   # Source ScanCell.cell_id
    twin_version: int
    # Version registry snapshot active when this voxel was generated
    scan_pipeline_version: str
    score_version: str
    physics_model_version: str
    # Source field values read from the frozen ScanCell record
    source_acif_score: Optional[float]
    source_uncertainty: Optional[float]
    source_temporal_score: Optional[float]
    source_physics_residual: Optional[float]
    # Depth kernel parameters used for projection
    z_expected_m: float
    sigma_z_m: float
    depth_slice_m: float           # Depth of this specific voxel
    kernel_weight: float           # D^(c)(z) value at this depth — [0, 1]
    built_at: str                  # ISO timestamp

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# DigitalTwinVoxel — unchanged schema, docstring extended for Phase N
# ---------------------------------------------------------------------------

class DigitalTwinVoxel(BaseModel):
    """
    One 3D voxel in the sovereign digital twin (§15).

    A voxel represents a depth column at a specific (lat, lon) cell location.
    Multiple voxels exist per cell — one per depth slice in DepthKernelConfig.

    PHASE N CONSTITUTIONAL RULES:
      1. commodity_probs: derived from cell ACIF via D^(c)(z) only.
         No probability is recomputed at query time.
      2. uncertainty, temporal_score, physics_residual: read directly from
         the frozen ScanCell record — propagated, not recomputed.
      3. expected_density: computed from depth kernel parameters and the
         inversion result (rho_mean from ScanCell) — not from raw gravity.
      4. Every voxel carries scan_id linking it to the frozen CanonicalScan.
      5. twin_version is monotonically increasing; old versions are immutable.
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

    # Commodity probability at this depth (from depth kernel projection only)
    commodity_probs: dict[str, NormalisedFloat] = Field(
        description=(
            "Commodity name → probability at this depth. "
            "Derived from cell ACIF × depth kernel D^(c)(z, z_expected) (§15.2). "
            "NEVER recomputed at query time — written once at twin build."
        )
    )

    # Physical properties at this depth
    expected_density: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Expected bulk density at this depth (kg/m³) from depth gradient model"
    )
    density_uncertainty: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Density estimate uncertainty (kg/m³) — propagated from ScanCell inversion"
    )

    # Propagated scores — read from frozen ScanCell, never recomputed
    temporal_score: Optional[NormalisedFloat] = Field(
        default=None,
        description="T_i from parent ScanCell — temporal stability. Read-only propagation."
    )
    physics_residual: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="R_phys from parent ScanCell — physics residual context. Read-only propagation."
    )
    uncertainty: Optional[NormalisedFloat] = Field(
        default=None,
        description="U_i from parent ScanCell — total uncertainty. Read-only propagation."
    )

    # Phase N: depth kernel weight stored for audit traceability
    kernel_weight: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="D^(c)(z) kernel weight at this depth. Stored for full projection traceability."
    )

    # Phase N: source cell reference for lineage
    source_cell_id: Optional[str] = Field(
        default=None,
        description="ScanCell.cell_id from which this voxel was projected"
    )

    # PostGIS geometry reference (populated by storage layer)
    geometry_wkt: Optional[str] = Field(
        default=None,
        description="WKT geometry for this voxel (stored as PostGIS geometry in DB)"
    )

    created_at: datetime = Field(description="When this voxel was written")

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# TwinBuildManifest — scan-level audit of twin construction
# ---------------------------------------------------------------------------

class TwinBuildManifest(BaseModel):
    """
    Audit manifest produced by the twin builder for one twin version.

    Records exactly which CanonicalScan fields were read, which depth kernel
    was used, and how many voxels were produced. Stored alongside the voxel
    records as a non-mutable audit artifact.

    PHASE N PROOF: presence of this manifest (with scan_id, version_registry,
    and cell_count matching canonical.total_cells) is the build-time proof
    that twin construction read from canonical storage and no other source.
    """
    scan_id: str
    twin_version: int
    cells_projected: int
    voxels_produced: int
    commodity: str
    depth_kernel: DepthKernelConfig
    # Version registry snapshot at build time (copied from CanonicalScan.version_registry)
    score_version: str
    tier_version: str
    physics_model_version: str
    scan_pipeline_version: str
    # Build metadata
    canonical_completed_at: Optional[str]
    built_at: str
    builder_version: str = "1.0.0"

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Unchanged existing models
# ---------------------------------------------------------------------------

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
    """Query parameters for voxel filtering. Used by POST /twin/{id}/query."""
    scan_id: str = Field(min_length=1)
    commodity: Optional[str] = Field(default=None)
    min_probability: Optional[NormalisedFloat] = Field(default=None)
    depth_min_m: Optional[float] = Field(default=None, ge=0.0)
    depth_max_m: Optional[float] = Field(default=None, ge=0.0)
    bounds: Optional[dict] = Field(default=None)
    version: Optional[int] = Field(default=None, ge=1)
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
    trigger: str = Field(description="'initial' | 'reprocess'")
    parent_version: Optional[int] = Field(default=None, ge=1)
    model_config = {"frozen": True}