"""
Aurora OSI vNext — GeoJSON Overlay Builder
Phase AA §AA.7

Builds GeoJSON FeatureCollections for Google Maps overlays.

CONSTITUTIONAL RULES:
  Rule 1: All geometry and properties sourced verbatim from stored canonical records.
  Rule 2: Coordinate precision preserved — no rounding below 8 decimal places.
  Rule 3: No tier derivation, no ACIF evaluation at build time.
          Tier membership sourced from stored cell.tier only.
  Rule 4: Each Feature includes aurora_source_field and aurora_layer properties
          for full field-mapping auditability.
"""

from __future__ import annotations

from typing import Any

from app.models.map_export_model import LayerType, LAYER_REGISTRY


def _feature_point(
    lat: float, lon: float,
    properties: dict[str, Any],
    layer_type: LayerType,
) -> dict:
    """GeoJSON Point Feature. Coordinates verbatim — no rounding."""
    defn = LAYER_REGISTRY.get(layer_type)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],  # GeoJSON: [lon, lat]
        },
        "properties": {
            **properties,
            "aurora_layer":        layer_type.value,
            "aurora_source_field": defn.source_field if defn else "",
        },
    }


def _feature_polygon(
    coords: list[tuple[float, float]],
    properties: dict[str, Any],
    layer_type: LayerType,
) -> dict:
    """
    GeoJSON Polygon Feature.
    coords: list of (lon, lat) pairs — verbatim from stored geometry.
    Coordinate precision preserved to full float64 (no simplification).
    """
    defn = LAYER_REGISTRY.get(layer_type)
    # GeoJSON: [[lon, lat], ...]
    ring = [[c[0], c[1]] for c in coords]
    # Ensure closed ring
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
        "properties": {
            **properties,
            "aurora_layer":        layer_type.value,
            "aurora_source_field": defn.source_field if defn else "",
        },
    }


def build_geojson_overlay(
    scan_id: str,
    layers: list[LayerType],
    layer_data: dict[LayerType, list[dict[str, Any]]],
    geometry_hash: str | None = None,
) -> dict:
    """
    Build a GeoJSON FeatureCollection for the requested layers.

    Returns a single FeatureCollection suitable for Google Maps overlay.
    aurora_geometry_hash is embedded in each feature's properties for
    field verification.
    """
    features: list[dict] = []

    for layer_type in layers:
        for feature in layer_data.get(layer_type, []):
            base_props = {k: v for k, v in feature.items()
                          if k not in ("geometry", "lat", "lon")}
            if geometry_hash:
                base_props["aurora_geometry_hash"] = geometry_hash
            base_props["aurora_scan_id"] = scan_id

            if "geometry" in feature:
                geom   = feature["geometry"]
                ring   = geom.get("coordinates", [[]])[0]
                coords = [(c[0], c[1]) for c in ring]
                features.append(_feature_polygon(coords, base_props, layer_type))
            elif "lat" in feature and "lon" in feature:
                features.append(_feature_point(
                    feature["lat"], feature["lon"], base_props, layer_type
                ))

    return {
        "type": "FeatureCollection",
        "features": features,
        "aurora_metadata": {
            "scan_id":       scan_id,
            "geometry_hash": geometry_hash,
            "layer_count":   len(layers),
            "feature_count": len(features),
        },
    }