"""
Aurora OSI vNext — Digital Twin API
Phase M §M.4 (basic) | Phase Q (full 3D binding)

ENDPOINT INVENTORY:
  GET  /api/v1/twin/{id}             — twin metadata (latest version)
  GET  /api/v1/twin/{id}/slice       — horizontal depth slice
  GET  /api/v1/twin/{id}/voxel/{vid} — single voxel record
  POST /api/v1/twin/{id}/query       — filtered voxel query
  GET  /api/v1/twin/{id}/history     — version history

CONSTITUTIONAL RULES — PHASE M:
  Rule 1 (Read-Only):         Twin endpoints read from storage/twin.py only.
  Rule 2 (No Re-scoring):     No twin endpoint re-scores, re-aggregates, or re-tiers.
                              Voxel values are deterministic projections stored at
                              twin_builder write time (services/twin_builder.py).
  Rule 3 (No Scoring Imports):Zero imports from core/scoring, core/tiering,
                              core/gates, or any core/* module.
  Rule 4 (Canonical Source):  Twin voxels are derived from frozen CanonicalScan outputs.
                              services/twin_builder.py reads canonical storage (read-only)
                              and writes voxels once. Twin endpoints read those voxels.
                              No twin endpoint reads CanonicalScan and recomputes anything.

TWIN CANONICAL-SOURCE PROOF:
  Derivation chain:
    1. CanonicalScan (frozen) → read-only by services/twin_builder.py
    2. twin_builder writes DigitalTwinVoxel records → storage/twin.py
    3. This API reads voxel records from storage/twin.py only
    4. No step in this chain re-scores, re-tiers, or re-gates
  Repeated reads: twin voxel records are append-only and never modified.
  GET /twin/{id} returns the same values on every call for a given version.

No imports from core/*, services/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digital_twin_model import TwinQuery
from app.security.auth import require_authenticated_user
from app.storage.base import StorageNotFoundError, get_db_session
from app.storage.twin import DigitalTwinStore

router = APIRouter(prefix="/twin", tags=["twin"])


# ---------------------------------------------------------------------------
# Twin metadata
# ---------------------------------------------------------------------------

@router.get("/{scan_id}")
async def get_twin_metadata(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Retrieve digital twin metadata for the latest version.
    All fields sourced from storage/twin.py — no recomputation.
    """
    store = DigitalTwinStore(db)
    try:
        meta = await store.get_twin_metadata(scan_id)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"No twin found for scan_id={scan_id}")
    return {
        "scan_id": meta.scan_id,
        "current_version": meta.current_version,
        "total_voxels": meta.total_voxels,
        "depth_range_m": list(meta.depth_range_m),
        "commodity": meta.commodity,
        "created_at": meta.created_at.isoformat() if meta.created_at else None,
    }


# ---------------------------------------------------------------------------
# Voxel query
# ---------------------------------------------------------------------------

@router.post("/{scan_id}/query")
async def query_twin_voxels(
    scan_id: str,
    query: TwinQuery,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Filtered voxel query for a digital twin.

    All returned voxel values are sourced from stored records.
    No score is recomputed. No tier is reassigned.

    PROOF: DigitalTwinStore.query_voxels() reads from digital_twin_voxels table.
    Each voxel's commodity_probs, uncertainty, physics_residual were written
    once by services/twin_builder.py from frozen CanonicalScan outputs.
    """
    query.scan_id = scan_id
    store = DigitalTwinStore(db)
    try:
        result = await store.query_voxels(query)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"No twin found for scan_id={scan_id}")
    return {
        "scan_id": scan_id,
        "twin_version": result.twin_version,
        "total_matching": result.total_matching,
        "voxels": [_voxel_to_dict(v) for v in result.voxels],
    }


# ---------------------------------------------------------------------------
# Depth slice
# ---------------------------------------------------------------------------

@router.get("/{scan_id}/slice")
async def get_twin_depth_slice(
    scan_id: str,
    depth_m: float = Query(..., ge=0.0, description="Target depth in metres"),
    depth_tolerance_m: float = Query(default=50.0, ge=1.0),
    version: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Horizontal depth slice through the twin at a specified depth.
    Returns all voxels within ±depth_tolerance_m of depth_m.
    All values from frozen voxel records.
    """
    store = DigitalTwinStore(db)
    query = TwinQuery(
        scan_id=scan_id,
        depth_min_m=depth_m - depth_tolerance_m,
        depth_max_m=depth_m + depth_tolerance_m,
        version=version,
        limit=2000,
    )
    try:
        result = await store.query_voxels(query)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"No twin found for scan_id={scan_id}")
    return {
        "scan_id": scan_id,
        "target_depth_m": depth_m,
        "depth_tolerance_m": depth_tolerance_m,
        "twin_version": result.twin_version,
        "voxel_count": result.total_matching,
        "voxels": [_voxel_to_dict(v) for v in result.voxels],
    }


# ---------------------------------------------------------------------------
# Single voxel
# ---------------------------------------------------------------------------

@router.get("/{scan_id}/voxel/{voxel_id}")
async def get_twin_voxel(
    scan_id: str,
    voxel_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """Single voxel record lookup. All values from frozen voxel storage."""
    store = DigitalTwinStore(db)
    query = TwinQuery(scan_id=scan_id, limit=1)
    try:
        result = await store.query_voxels(query)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"No twin found for scan_id={scan_id}")
    match = next((v for v in result.voxels if v.voxel_id == voxel_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Voxel {voxel_id} not found in twin {scan_id}")
    return _voxel_to_dict(match)


# ---------------------------------------------------------------------------
# Twin version history
# ---------------------------------------------------------------------------

@router.get("/{scan_id}/history")
async def get_twin_history(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    All twin versions for a scan.
    Twins are append-only — previous versions are always available.
    """
    store = DigitalTwinStore(db)
    try:
        versions = await store.get_twin_history(scan_id)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"No twin history for scan_id={scan_id}")
    return {
        "scan_id": scan_id,
        "versions": [
            {
                "version": v.version,
                "voxel_count": v.voxel_count,
                "trigger": v.trigger,
                "parent_version": v.parent_version,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "total_versions": len(versions),
    }


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------

def _voxel_to_dict(v) -> dict:
    return {
        "voxel_id":           v.voxel_id,
        "scan_id":            v.scan_id,
        "twin_version":       v.twin_version,
        "lat_center":         v.lat_center,
        "lon_center":         v.lon_center,
        "depth_m":            v.depth_m,
        "depth_range_m":      list(v.depth_range_m),
        "commodity_probs":    v.commodity_probs,
        "expected_density":   v.expected_density,
        "density_uncertainty": v.density_uncertainty,
        "temporal_score":     v.temporal_score,
        "physics_residual":   v.physics_residual,
        "uncertainty":        v.uncertainty,
    }