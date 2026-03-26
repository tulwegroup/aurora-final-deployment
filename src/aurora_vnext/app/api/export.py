"""
Aurora OSI vNext — Canonical Data Export API
Phase X §X.1

Provides authenticated export of frozen canonical scan data in multiple formats:
  - JSON:    Full CanonicalScan record (verbatim from storage)
  - GeoJSON: Cell-level spatial export (lat/lon + verbatim scores)
  - CSV:     Flat cell table (verbatim fields, no derived columns)

All exports are READ-ONLY projections of frozen canonical records.
No scientific transformation is applied at export time.

CONSTITUTIONAL RULES — Phase X:
  Rule 1: All exported field values are sourced verbatim from the frozen
          CanonicalScan or ScanCell records in storage. No arithmetic,
          normalisation, or derivation is applied at export time.
  Rule 2: Export format (JSON/GeoJSON/CSV) is a serialisation choice only.
          It does not alter numeric precision beyond json.dumps default (IEEE 754).
  Rule 3: GeoJSON Feature properties contain only verbatim stored fields.
          No computed property (e.g. tier_rank, acif_percentile) is added.
  Rule 4: CSV column names map directly to canonical field names.
          No alias that implies derivation (e.g. "normalised_score") is used.
  Rule 5: Export audit records are appended to the audit log on every download.
          The audit record includes scan_id, format, user_id — no scientific fields.
  Rule 6: No import from core/*.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.config.observability import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ---------------------------------------------------------------------------
# GeoJSON export helpers
# ---------------------------------------------------------------------------

def cell_to_geojson_feature(cell: dict[str, Any]) -> dict:
    """
    Convert a ScanCell dict to a GeoJSON Feature.

    RULE 3: Properties contain only verbatim stored fields.
    Coordinates: [lon_center, lat_center] from stored cell record.

    No computed properties are added. No score is recomputed or re-ranked.
    """
    lat = cell.get("lat_center")
    lon = cell.get("lon_center")

    # Coordinates from stored spatial fields — verbatim
    geometry = None
    if lat is not None and lon is not None:
        geometry = {"type": "Point", "coordinates": [lon, lat]}

    # Properties: all verbatim stored fields except spatial coordinates
    # (which are encoded in geometry above)
    properties = {
        k: v for k, v in cell.items()
        if k not in ("lat_center", "lon_center")
    }

    return {
        "type":       "Feature",
        "geometry":   geometry,
        "properties": properties,   # RULE 3: verbatim stored fields only
    }


def cells_to_geojson(scan_id: str, cells: list[dict[str, Any]]) -> dict:
    """
    Build a GeoJSON FeatureCollection from a list of ScanCell dicts.
    RULE 3: No computed property is introduced.
    """
    return {
        "type":     "FeatureCollection",
        "scan_id":  scan_id,
        "features": [cell_to_geojson_feature(c) for c in cells],
    }


# ---------------------------------------------------------------------------
# CSV export helpers
# ---------------------------------------------------------------------------

# Canonical column order for CSV export — verbatim field names (RULE 4)
CSV_COLUMNS = [
    "cell_id", "scan_id", "lat_center", "lon_center",
    "acif_score",
    "evidence_score", "causal_score", "physics_score", "temporal_score",
    "province_prior", "total_uncertainty",
    "tier", "any_veto_fired",
    "physics_residual", "gravity_residual",
]


def cells_to_csv(cells: list[dict[str, Any]]) -> str:
    """
    Serialise ScanCell list to CSV with canonical column order.

    RULE 4: Column names are canonical field names — no aliasing.
    RULE 1: Values are verbatim from stored records — no derivation.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=CSV_COLUMNS,
        extrasaction="ignore",   # extra cell fields omitted — not computed
        restval="",              # missing fields → empty string (not a fallback value)
    )
    writer.writeheader()
    for cell in cells:
        writer.writerow(cell)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Export audit helper
# ---------------------------------------------------------------------------

def _log_export_audit(scan_id: str, export_format: str, user_id: str) -> None:
    """
    Append export event to structured audit log.
    RULE 5: audit record contains only infrastructure metadata — no scientific fields.
    """
    logger.info(
        "export_downloaded",
        extra={
            "scan_id":       scan_id,
            "export_format": export_format,
            "user_id":       user_id,
        },
    )


# ---------------------------------------------------------------------------
# Export routes
# ---------------------------------------------------------------------------

@router.get("/{scan_id}/json")
async def export_scan_json(scan_id: str, request: Request):
    """
    Export the full frozen CanonicalScan record as JSON.

    RULE 1: Returns the stored record verbatim — json.dumps(record, default=str).
    RULE 2: Numeric precision is IEEE 754 default — no rounding applied.
    """
    scan = await _fetch_scan(scan_id, request)
    user_id = getattr(request.state, "user_id", "anonymous")
    _log_export_audit(scan_id, "json", user_id)

    payload = json.dumps(scan, default=str, sort_keys=False)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}.json"'},
    )


@router.get("/{scan_id}/geojson")
async def export_scan_geojson(scan_id: str, request: Request):
    """
    Export cell-level data as GeoJSON FeatureCollection.

    RULE 3: Feature properties are verbatim ScanCell fields.
    No computed property (acif_percentile, tier_rank) is added.
    """
    cells = await _fetch_cells(scan_id, request)
    user_id = getattr(request.state, "user_id", "anonymous")
    _log_export_audit(scan_id, "geojson", user_id)

    geojson = cells_to_geojson(scan_id, cells)
    payload = json.dumps(geojson, default=str)
    return Response(
        content=payload,
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}.geojson"'},
    )


@router.get("/{scan_id}/csv")
async def export_scan_csv(scan_id: str, request: Request):
    """
    Export cell-level data as CSV.

    RULE 4: Column names are canonical field names — no derived aliases.
    RULE 1: Values are verbatim from stored ScanCell records.
    """
    cells = await _fetch_cells(scan_id, request)
    user_id = getattr(request.state, "user_id", "anonymous")
    _log_export_audit(scan_id, "csv", user_id)

    csv_content = cells_to_csv(cells)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}.csv"'},
    )


# ---------------------------------------------------------------------------
# Storage fetch helpers (injected in production via Depends)
# ---------------------------------------------------------------------------

async def _fetch_scan(scan_id: str, request: Request) -> dict:
    """Fetch frozen CanonicalScan from storage. Returns verbatim stored dict."""
    storage = getattr(request.app.state, "scan_storage", None)
    if storage:
        record = await storage.get(scan_id)
    else:
        record = None
    if record is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id!r} not found")
    return record


async def _fetch_cells(scan_id: str, request: Request) -> list[dict]:
    """Fetch ScanCell list for a scan. Returns verbatim stored dicts."""
    storage = getattr(request.app.state, "cell_storage", None)
    if storage:
        cells = await storage.list_for_scan(scan_id)
    else:
        cells = []
    return cells