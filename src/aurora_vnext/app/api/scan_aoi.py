"""
Aurora OSI vNext — Scan AOI API
Phase AA §AA.4

REST endpoints for AOI creation, validation, workload estimation, and scan initiation.

Endpoints:
  POST   /api/v1/aoi/validate              — validate geometry, return errors/warnings
  POST   /api/v1/aoi                       — save validated AOI as immutable ScanAOI
  GET    /api/v1/aoi/{aoi_id}              — retrieve AOI with integrity check
  GET    /api/v1/aoi/{aoi_id}/estimate     — workload estimate for all resolutions
  POST   /api/v1/aoi/{aoi_id}/submit-scan  — initiate scan from AOI
  GET    /api/v1/aoi/{aoi_id}/verify       — re-verify geometry hash integrity

CONSTITUTIONAL RULES:
  Rule 1: AOI records are never overwritten. Geometry changes require new AOI.
  Rule 2: geometry_hash verified on every retrieval.
  Rule 3: Submitted scans carry both aoi_id and geometry_hash — immutable reference.
  Rule 4: No ACIF, no tier computation in this layer.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.models.scan_aoi_model import (
    ScanAOI, GeometryType, SourceType, ValidationStatus,
    new_aoi, compute_geometry_hash,
)
from app.services.aoi_validator import validate_aoi_geometry
from app.services.aoi_tiling import estimate_workload, ResolutionTier
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/aoi", tags=["scan_aoi"])

# In-memory AOI store (replaced by DB in production)
_aoi_store: dict[str, ScanAOI] = {}

# Scan submissions registry: aoi_id → list of {scan_id, geometry_hash, commodity, resolution}
_scan_refs: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ValidateGeometryRequest(BaseModel):
    geometry: dict
    max_area_km2: Optional[float] = None

    class Config:
        extra = "forbid"


class SaveAOIRequest(BaseModel):
    geometry:     dict
    geometry_type: str = "polygon"
    source_type:  str  = "drawn"
    source_file_hash: Optional[str] = None

    class Config:
        extra = "forbid"


class SubmitScanRequest(BaseModel):
    commodity:  str
    resolution: str = "medium"
    notes:      Optional[str] = None

    class Config:
        extra = "forbid"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_geometry(body: ValidateGeometryRequest):
    """Validate geometry without persisting. Returns errors, warnings, area estimate."""
    result = validate_aoi_geometry(
        body.geometry,
        max_area_km2=body.max_area_km2 or 500_000.0,
    )
    return {
        "valid":              result.valid,
        "errors":             result.errors,
        "warnings":           result.warnings,
        "area_km2":           result.area_km2,
        "centroid":           result.centroid,
        "bbox":               result.bbox,
        "environment":        result.environment.value if result.environment else None,
        "anti_meridian_risk": result.anti_meridian_risk,
        "geometry_hash":      compute_geometry_hash(body.geometry) if result.valid else None,
    }


@router.post("", status_code=201)
async def save_aoi(
    body: SaveAOIRequest,
    x_actor_id: Optional[str] = Header(default="anonymous"),
):
    """
    Validate and persist an AOI as an immutable ScanAOI.

    Returns aoi_id + geometry_hash. Geometry is never mutated after this point.
    If geometry is invalid, returns 422 with validation errors.
    """
    result = validate_aoi_geometry(body.geometry)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={"validation_errors": result.errors, "warnings": result.warnings},
        )

    try:
        geo_type    = GeometryType(body.geometry_type)
        source_type = SourceType(body.source_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    aoi = new_aoi(
        geometry_type     = geo_type,
        geometry          = body.geometry,
        centroid          = result.centroid,
        bbox              = result.bbox,
        area_km2          = result.area_km2,
        created_by        = x_actor_id,
        source_type       = source_type,
        validation_status = ValidationStatus.VALID,
        environment       = result.environment,
        validation_errors = tuple(result.errors),
        source_file_hash  = body.source_file_hash,
    )

    _aoi_store[aoi.aoi_id] = aoi
    _scan_refs[aoi.aoi_id] = []

    logger.info("aoi_created", extra={
        "aoi_id": aoi.aoi_id, "area_km2": aoi.area_km2,
        "geometry_hash": aoi.geometry_hash, "created_by": x_actor_id,
    })

    return {
        "aoi_id":        aoi.aoi_id,
        "geometry_hash": aoi.geometry_hash,
        "area_km2":      aoi.area_km2,
        "aoi_version":   aoi.aoi_version,
        "environment":   aoi.environment.value,
        "warnings":      result.warnings,
        "map_projection": aoi.map_projection,
    }


@router.get("/{aoi_id}")
async def get_aoi(aoi_id: str):
    """
    Retrieve AOI and verify geometry hash integrity on every retrieval.
    Returns 409 if geometry hash mismatch detected (silent mutation).
    """
    aoi = _aoi_store.get(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    # Rule 2: verify integrity on every retrieval
    if not aoi.verify_geometry_integrity():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "geometry_integrity_failure",
                "message": (
                    f"AOI {aoi_id}: geometry hash mismatch. "
                    f"Stored hash does not match recomputed hash. "
                    f"This AOI cannot be used for scan submission."
                ),
                "stored_hash": aoi.geometry_hash,
            },
        )

    return {
        "aoi_id":            aoi.aoi_id,
        "geometry_type":     aoi.geometry_type.value,
        "geometry":          aoi.geometry,
        "geometry_hash":     aoi.geometry_hash,
        "aoi_version":       aoi.aoi_version,
        "centroid":          aoi.centroid,
        "bbox":              aoi.bbox,
        "area_km2":          aoi.area_km2,
        "created_by":        aoi.created_by,
        "created_at":        aoi.created_at,
        "source_type":       aoi.source_type.value,
        "map_projection":    aoi.map_projection,
        "validation_status": aoi.validation_status.value,
        "environment":       aoi.environment.value,
        "scan_refs":         _scan_refs.get(aoi_id, []),
    }


@router.get("/{aoi_id}/estimate")
async def workload_estimate(aoi_id: str):
    """Return workload estimates for all resolution tiers."""
    aoi = _aoi_store.get(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    aoi.assert_geometry_integrity()

    offshore_fraction = 1.0 if aoi.environment.value == "offshore" else (
        0.5 if aoi.environment.value == "mixed" else 0.0
    )
    preview = estimate_workload(aoi.area_km2, offshore_fraction=offshore_fraction)
    return {
        "aoi_id":             aoi_id,
        "area_km2":           preview.area_km2,
        "default_resolution": preview.default_resolution.value,
        "options": [
            {
                "resolution":               o.resolution.value,
                "cell_size_km2":            o.cell_size_km2,
                "estimated_cells":          o.estimated_cells,
                "cost_tier":                o.cost_tier.value,
                "estimated_onshore_cells":  o.estimated_onshore_cells,
                "estimated_offshore_cells": o.estimated_offshore_cells,
            }
            for o in preview.options
        ],
    }


@router.post("/{aoi_id}/submit-scan", status_code=201)
async def submit_scan(
    aoi_id: str,
    body: SubmitScanRequest,
    x_actor_id: Optional[str] = Header(default="anonymous"),
):
    """
    Initiate a scan from a validated AOI.

    The scan record references both aoi_id and geometry_hash — these references
    are immutable and guarantee reproducibility.
    """
    import uuid
    aoi = _aoi_store.get(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    if aoi.validation_status != ValidationStatus.VALID:
        raise HTTPException(status_code=409, detail="AOI has not passed validation.")

    # Integrity check before scan submission
    aoi.assert_geometry_integrity()

    try:
        ResolutionTier(body.resolution)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown resolution: {body.resolution!r}")

    scan_id = str(uuid.uuid4())

    # Immutable scan reference — both aoi_id and geometry_hash stored
    scan_ref = {
        "scan_id":       scan_id,
        "aoi_id":        aoi_id,
        "geometry_hash": aoi.geometry_hash,   # immutable reference
        "commodity":     body.commodity,
        "resolution":    body.resolution,
        "submitted_by":  x_actor_id,
        "area_km2":      aoi.area_km2,
        "environment":   aoi.environment.value,
    }
    _scan_refs.setdefault(aoi_id, []).append(scan_ref)

    logger.info("scan_submitted_from_aoi", extra={
        "scan_id": scan_id, "aoi_id": aoi_id,
        "geometry_hash": aoi.geometry_hash, "commodity": body.commodity,
    })

    return {
        "scan_id":       scan_id,
        "aoi_id":        aoi_id,
        "geometry_hash": aoi.geometry_hash,   # returned to caller for verification
        "commodity":     body.commodity,
        "resolution":    body.resolution,
        "status":        "queued",
    }


@router.get("/{aoi_id}/verify")
async def verify_aoi_integrity(aoi_id: str):
    """
    Explicit geometry hash re-verification endpoint.
    Returns pass/fail + stored hash vs recomputed hash for audit.
    """
    from app.models.scan_aoi_model import compute_geometry_hash
    aoi = _aoi_store.get(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    recomputed = compute_geometry_hash(aoi.geometry)
    passed = recomputed == aoi.geometry_hash

    return {
        "aoi_id":          aoi_id,
        "integrity_pass":  passed,
        "stored_hash":     aoi.geometry_hash,
        "recomputed_hash": recomputed,
        "match":           passed,
        "message": "Geometry intact." if passed else
                   "INTEGRITY FAILURE: geometry_hash mismatch. Silent mutation detected.",
    }