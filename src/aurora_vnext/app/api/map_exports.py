"""
Aurora OSI vNext — Map Export API
Phase AA §AA.8

REST endpoints for KML/KMZ and GeoJSON export of canonical scan layers.

Endpoints:
  POST /api/v1/exports/{scan_id}/kml      — download KML file
  POST /api/v1/exports/{scan_id}/kmz      — download KMZ archive
  POST /api/v1/exports/{scan_id}/geojson  — download GeoJSON overlay
  GET  /api/v1/exports/layers             — layer registry (field mapping audit)

CONSTITUTIONAL RULES:
  Rule 1: All layers sourced from stored canonical fields per LAYER_REGISTRY.
  Rule 2: No tier derivation, ACIF evaluation, or anomaly computation at export.
  Rule 3: Coordinate precision preserved — no smoothing or simplification.
  Rule 4: geometry_hash embedded in every export for reproducibility verification.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.map_export_model import LayerType, LAYER_REGISTRY
from app.services.kml_builder import build_kml, build_kmz
from app.services.geojson_overlay_builder import build_geojson_overlay
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/exports", tags=["map_exports"])


class ExportLayerRequest(BaseModel):
    layers: list[str]   # LayerType values
    geometry_hash: Optional[str] = None
    include_hash: bool = True

    class Config:
        extra = "forbid"


def _parse_layers(layer_strs: list[str]) -> list[LayerType]:
    out = []
    for s in layer_strs:
        try:
            out.append(LayerType(s))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown layer type: {s!r}")
    return out


def _stub_layer_data(scan_id: str, layers: list[LayerType]) -> dict:
    """
    Stub: returns empty feature lists per layer.
    Production: replaced by queries to canonical storage adapter.
    All data must come from stored canonical fields — never recomputed.
    """
    return {layer: [] for layer in layers}


@router.get("/layers")
async def list_layers():
    """Return the full layer registry — source field mapping for every layer."""
    return [
        {
            "layer_type":   k.value,
            "display_name": v.display_name,
            "source_field": v.source_field,
            "filter_field": v.filter_field,
            "filter_value": v.filter_value,
            "description":  v.description,
        }
        for k, v in LAYER_REGISTRY.items()
    ]


@router.post("/{scan_id}/kml")
async def export_kml(scan_id: str, body: ExportLayerRequest):
    """Export canonical scan layers as KML. Geometry verbatim from storage."""
    layers     = _parse_layers(body.layers)
    layer_data = _stub_layer_data(scan_id, layers)
    kml_str    = build_kml(
        scan_id, layers, layer_data,
        geometry_hash=body.geometry_hash,
        include_hash=body.include_hash,
    )
    logger.info("kml_exported", extra={"scan_id": scan_id, "layers": [l.value for l in layers]})
    return Response(
        content=kml_str.encode("utf-8"),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="aurora_{scan_id}.kml"'},
    )


@router.post("/{scan_id}/kmz")
async def export_kmz(scan_id: str, body: ExportLayerRequest):
    """Export canonical scan layers as KMZ (zipped KML)."""
    layers     = _parse_layers(body.layers)
    layer_data = _stub_layer_data(scan_id, layers)
    kmz_bytes  = build_kmz(
        scan_id, layers, layer_data,
        geometry_hash=body.geometry_hash,
        include_hash=body.include_hash,
    )
    logger.info("kmz_exported", extra={"scan_id": scan_id, "layers": [l.value for l in layers]})
    return Response(
        content=kmz_bytes,
        media_type="application/vnd.google-earth.kmz",
        headers={"Content-Disposition": f'attachment; filename="aurora_{scan_id}.kmz"'},
    )


@router.post("/{scan_id}/geojson")
async def export_geojson(scan_id: str, body: ExportLayerRequest):
    """Export canonical scan layers as GeoJSON FeatureCollection for Google Maps overlay."""
    import json
    layers     = _parse_layers(body.layers)
    layer_data = _stub_layer_data(scan_id, layers)
    geojson    = build_geojson_overlay(
        scan_id, layers, layer_data,
        geometry_hash=body.geometry_hash,
    )
    logger.info("geojson_exported", extra={"scan_id": scan_id, "layers": [l.value for l in layers]})
    return Response(
        content=json.dumps(geojson, separators=(",", ":")).encode("utf-8"),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="aurora_{scan_id}.geojson"'},
    )