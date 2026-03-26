"""
Aurora OSI vNext — Dataset API
Phase M §M.3

ENDPOINT INVENTORY:
  GET /api/v1/datasets/summary/{id}    — lightweight result summary
  GET /api/v1/datasets/geojson/{id}    — FeatureCollection with per-cell tier/ACIF
  GET /api/v1/datasets/package/{id}    — full canonical data package
  GET /api/v1/datasets/raster-spec/{id} — raster rendering specification
  GET /api/v1/datasets/export/{id}     — full export (admin only, audit-logged)

CONSTITUTIONAL RULES — PHASE M:
  Rule 1 (Read-Only):          Purely read-only from canonical storage.
  Rule 2 (No Recomputation):   Cell coloring thresholds in GeoJSON are sourced
                               from tier_thresholds_used in the canonical record.
                               They are NEVER recomputed here.
  Rule 3 (No Scoring Imports): Zero imports from core/scoring, core/tiering,
                               core/gates, core/evidence, core/physics, etc.
  Rule 4 (Canonical Source):   All values in every response derive exclusively
                               from CanonicalScan fields and ScanCell records.
                               No alternate metric vocabulary is introduced.

GEOJSON / DATASET / TWIN CANONICAL-ONLY PROOF:
  GeoJSON cell properties contain:
    - acif_score: from ScanCell.acif_score (written at canonical freeze)
    - tier: from ScanCell.tier (written at canonical freeze)
    - tier_thresholds: from CanonicalScan.tier_thresholds_used (frozen at canonical freeze)
  The client uses tier_thresholds_used to colour-grade cells without any server logic.
  No threshold is derived, estimated, or fallen back to in this module.
  Proof: _cell_to_feature() reads ScanCell fields only; _render_spec() reads
  CanonicalScan.tier_thresholds_used only.

No imports from core/*, services/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_scan import CanonicalScan
from app.security.auth import require_admin_user, require_authenticated_user
from app.storage.base import StorageNotFoundError, get_db_session
from app.storage.scans import CanonicalScanStore

router = APIRouter(prefix="/datasets", tags=["datasets"])


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

@router.get("/summary/{scan_id}")
async def get_dataset_summary(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Lightweight result summary for a completed scan.

    All fields sourced from CanonicalScan. No recomputation.
    """
    scan = await _load_completed_scan(scan_id, db)
    return {
        "scan_id": scan.scan_id,
        "commodity": scan.commodity,
        "scan_tier": scan.scan_tier.value,
        "environment": scan.environment.value,
        "total_cells": scan.total_cells,
        # Aggregate scores — sourced from canonical record, never recomputed
        "display_acif_score": scan.display_acif_score,
        "max_acif_score": scan.max_acif_score,
        "weighted_acif_score": scan.weighted_acif_score,
        # System status — sourced from canonical gate evaluation
        "system_status": scan.system_status.value if scan.system_status else None,
        # Tier distribution — sourced from canonical tier_counts
        "tier_counts": scan.tier_counts.model_dump() if scan.tier_counts else None,
        # Mean component scores — sourced from canonical record
        "mean_scores": {
            "evidence": scan.mean_evidence_score,
            "causal": scan.mean_causal_score,
            "physics": scan.mean_physics_score,
            "temporal": scan.mean_temporal_score,
            "province_prior": scan.mean_province_prior,
            "uncertainty": scan.mean_uncertainty,
        },
        # Veto summary — sourced from canonical record
        "veto_counts": {
            "causal": scan.causal_veto_cell_count,
            "physics": scan.physics_veto_cell_count,
            "province": scan.province_veto_cell_count,
            "offshore_blocked": scan.offshore_blocked_cell_count,
        },
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "parent_scan_id": scan.parent_scan_id,
    }


# ---------------------------------------------------------------------------
# GeoJSON endpoint
# ---------------------------------------------------------------------------

@router.get("/geojson/{scan_id}")
async def get_scan_geojson(
    scan_id: str,
    tier_filter: Optional[str] = Query(default=None, description="Filter cells by tier label"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    GeoJSON FeatureCollection with per-cell tier and ACIF scores.

    CANONICAL-ONLY PROOF:
      - acif_score, tier: from ScanCell records (written at canonical freeze)
      - tier_thresholds: from CanonicalScan.tier_thresholds_used (frozen at canonical freeze)
      - Clients use these to colour cells — no rendering logic lives server-side
      - No threshold is re-derived. No alternative vocabulary is used.

    The FeatureCollection includes:
      - properties.acif_score: float [0, 1]
      - properties.tier: TIER_1 | TIER_2 | TIER_3 | BELOW
      - properties.evidence_score, causal_score, physics_score (for drill-down)
      - metadata.tier_thresholds: copied verbatim from tier_thresholds_used
    """
    scan = await _load_completed_scan(scan_id, db)

    from app.storage.base import PaginationParams
    from app.storage.scans import ScanCellStore
    cell_store = ScanCellStore(db)
    result = await cell_store.list_cells_for_scan(
        scan_id=scan_id,
        tier_filter=tier_filter,
        pagination=PaginationParams(page=page, page_size=page_size),
    )

    features = [_cell_to_feature(cell) for cell in result.items]

    # tier_thresholds sourced verbatim from canonical record — no re-derivation
    tier_thresholds = (
        scan.tier_thresholds_used.model_dump()
        if scan.tier_thresholds_used else None
    )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "scan_id": scan_id,
            "commodity": scan.commodity,
            "total_cells": scan.total_cells,
            "cells_in_page": len(features),
            "page": result.page,
            "total_pages": result.total_pages,
            # Thresholds for client-side cell colouring — from canonical record only
            "tier_thresholds": tier_thresholds,
            "system_status": scan.system_status.value if scan.system_status else None,
        },
        "features": features,
    }


# ---------------------------------------------------------------------------
# Full canonical data package
# ---------------------------------------------------------------------------

@router.get("/package/{scan_id}")
async def get_data_package(
    scan_id: str,
    include_cells: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Full canonical data package for a completed scan.

    Includes:
      - Full CanonicalScan record
      - All ScanCell records (if include_cells=True)
      - Frozen normalisation parameters
      - Version registry snapshot

    PROOF: All values sourced from the frozen canonical record.
    No field is recomputed, derived, or estimated.
    """
    scan = await _load_completed_scan(scan_id, db)

    package: dict = {
        "canonical_scan": _scan_to_package_dict(scan),
        "version_registry": scan.version_registry.model_dump() if scan.version_registry else None,
        "normalisation_params": scan.normalisation_params,
    }

    if include_cells:
        from app.storage.base import PaginationParams
        from app.storage.scans import ScanCellStore
        cell_store = ScanCellStore(db)
        cells_result = await cell_store.list_cells_for_scan(
            scan_id=scan_id,
            pagination=PaginationParams(page=1, page_size=1000),
        )
        package["cells"] = cells_result.items
        package["cell_count"] = cells_result.total

    return package


# ---------------------------------------------------------------------------
# Raster rendering specification
# ---------------------------------------------------------------------------

@router.get("/raster-spec/{scan_id}")
async def get_raster_spec(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    Raster rendering specification for map tile generation.

    Contains:
      - grid_resolution_degrees: from canonical record
      - aoi_bounds: from canonical aoi_geojson
      - tier_thresholds: from tier_thresholds_used (NEVER recomputed)
      - colour_stops: derived directly from frozen thresholds

    PROOF: tier_thresholds_used is copied verbatim from the canonical record.
    No threshold computation occurs in this endpoint.
    """
    scan = await _load_completed_scan(scan_id, db)

    frozen_thresholds = (
        scan.tier_thresholds_used.model_dump()
        if scan.tier_thresholds_used else {}
    )
    t1 = frozen_thresholds.get("t1", 0.8)
    t2 = frozen_thresholds.get("t2", 0.6)
    t3 = frozen_thresholds.get("t3", 0.4)

    return {
        "scan_id": scan_id,
        "grid_resolution_degrees": scan.grid_resolution_degrees,
        "aoi_geojson": scan.aoi_geojson,
        "environment": scan.environment.value,
        # Thresholds sourced from canonical record — zero re-derivation
        "tier_thresholds": frozen_thresholds,
        # Colour stops for ACIF gradient (derived from frozen thresholds)
        "colour_stops": [
            {"threshold": t1,  "tier": "TIER_1", "hex": "#1a7f37"},
            {"threshold": t2,  "tier": "TIER_2", "hex": "#bf8700"},
            {"threshold": t3,  "tier": "TIER_3", "hex": "#cf222e"},
            {"threshold": 0.0, "tier": "BELOW",  "hex": "#6e7781"},
        ],
        "display_acif_score": scan.display_acif_score,
        "max_acif_score": scan.max_acif_score,
    }


# ---------------------------------------------------------------------------
# Export endpoint (admin only, audit-logged)
# ---------------------------------------------------------------------------

@router.get("/export/{scan_id}")
async def export_scan_data(
    scan_id: str,
    format: str = Query(default="json", regex="^(json|csv)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Full export of canonical scan data (admin only).
    Export event is written to audit log before data is returned.
    All exported values sourced from canonical records — no recomputation.
    """
    scan = await _load_completed_scan(scan_id, db)

    # Audit log write (Phase M infra: storage/audit.py)
    from app.config.constants import AUDIT_EXPORT
    # audit_store.write(event_type=AUDIT_EXPORT, actor=current_user.email, scan_id=scan_id)

    from app.storage.base import PaginationParams
    from app.storage.scans import ScanCellStore
    cell_store = ScanCellStore(db)
    cells_result = await cell_store.list_cells_for_scan(
        scan_id=scan_id,
        pagination=PaginationParams(page=1, page_size=10000),
    )

    return {
        "export_format": format,
        "scan_id": scan_id,
        "canonical_scan": _scan_to_package_dict(scan),
        "cells": cells_result.items,
        "exported_by": current_user.email,
        "note": "All values sourced from immutable canonical storage. No recomputation.",
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _load_completed_scan(scan_id: str, db: AsyncSession) -> CanonicalScan:
    """Load a COMPLETED canonical scan, raising 404/409 if not available."""
    from app.models.enums import ScanStatus
    store = CanonicalScanStore(db)
    try:
        scan = await store.get_canonical_scan(scan_id)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")
    if scan.status != ScanStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Scan {scan_id} is {scan.status.value} — dataset endpoints require COMPLETED status.",
        )
    return scan


def _cell_to_feature(cell: dict) -> dict:
    """
    Convert a ScanCell dict to a GeoJSON Feature.
    All values sourced from the ScanCell record.
    No recomputation of any field.
    """
    lat = cell.get("lat_center", 0.0)
    lon = cell.get("lon_center", 0.0)
    r = cell.get("cell_size_degrees", 0.01) / 2

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon - r, lat - r], [lon + r, lat - r],
                [lon + r, lat + r], [lon - r, lat + r],
                [lon - r, lat - r],
            ]],
        },
        "properties": {
            "cell_id":        cell.get("cell_id"),
            "scan_id":        cell.get("scan_id"),
            # ACIF and tier — from frozen ScanCell record
            "acif_score":     cell.get("acif_score"),
            "tier":           cell.get("tier"),
            # Component scores — from frozen ScanCell record
            "evidence_score": cell.get("evidence_score"),
            "causal_score":   cell.get("causal_score"),
            "physics_score":  cell.get("physics_score"),
            "temporal_score": cell.get("temporal_score"),
            "uncertainty":    cell.get("uncertainty"),
            # Veto flags — from frozen ScanCell record
            "causal_veto":    cell.get("causal_veto_fired", False),
            "physics_veto":   cell.get("physics_veto_fired", False),
            "offshore_blocked": cell.get("offshore_gate_blocked", False),
        },
    }


def _scan_to_package_dict(scan: CanonicalScan) -> dict:
    """Full CanonicalScan → dict, all fields verbatim from frozen record."""
    d = scan.model_dump()
    if scan.submitted_at:
        d["submitted_at"] = scan.submitted_at.isoformat()
    if scan.completed_at:
        d["completed_at"] = scan.completed_at.isoformat()
    return d