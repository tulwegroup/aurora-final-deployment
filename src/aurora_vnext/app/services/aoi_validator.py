"""
Aurora OSI vNext — AOI Validator
Phase AA §AA.2

Validates ScanAOI geometry before persistence.

Validation rules:
  1. Closed polygon: first and last coordinate must be identical
  2. Minimum ring length: ≥ 4 coordinate pairs (3 unique + 1 closing)
  3. No self-intersections: edges must not cross each other
  4. Minimum area: ≥ MIN_AREA_KM2 (default 0.1 km²)
  5. Maximum area: ≤ MAX_AREA_KM2 (configurable per resolution tier)
  6. WGS84 coordinate range: lat ∈ [-90, 90], lon ∈ [-180, 180]
  7. Anti-meridian detection: warns if bbox spans > 180° longitude
  8. Offshore/onshore classification: coarse heuristic; definitive
     classification done server-side against stored boundary layer.

CONSTITUTIONAL RULE: This layer validates geometry only. No ACIF,
no tier, no scoring. All outputs are geometry metadata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from app.models.scan_aoi_model import EnvironmentClassification

# Area limits
MIN_AREA_KM2 = 0.1
MAX_AREA_KM2_DEFAULT = 500_000.0  # ~500k km² — continental-scale upper bound

# Earth radius for approximate area calculation
EARTH_RADIUS_KM = 6371.0


@dataclass
class ValidationResult:
    valid:              bool
    errors:             list[str]
    warnings:           list[str]
    area_km2:           Optional[float]
    centroid:           Optional[dict]          # {"lat": float, "lon": float}
    bbox:               Optional[dict]          # {min_lat, max_lat, min_lon, max_lon}
    environment:        EnvironmentClassification
    anti_meridian_risk: bool


def _coords_from_geojson(geometry: dict) -> list[tuple[float, float]]:
    """
    Extract exterior ring coordinates from a GeoJSON geometry dict.
    Supports Polygon and MultiPolygon (uses first polygon only).
    Returns list of (lon, lat) tuples.
    """
    gtype = geometry.get("type", "")
    if gtype == "Polygon":
        ring = geometry["coordinates"][0]
    elif gtype == "MultiPolygon":
        ring = geometry["coordinates"][0][0]
    elif gtype == "Feature":
        return _coords_from_geojson(geometry["geometry"])
    else:
        raise ValueError(f"Unsupported geometry type: {gtype!r}")
    return [(float(c[0]), float(c[1])) for c in ring]


def _approx_area_km2(coords: list[tuple[float, float]]) -> float:
    """
    Shoelace formula on spherical Earth (approximation).
    Sufficient for area-limit validation — not used for scientific output.
    coords: list of (lon, lat) in degrees.
    """
    if len(coords) < 3:
        return 0.0
    # Convert to radians
    rads = [(math.radians(lon), math.radians(lat)) for lon, lat in coords]
    n = len(rads)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += (rads[j][0] - rads[i][0]) * (rads[j][1] + rads[i][1])
    area = abs(area) / 2.0
    # Convert steradians to km²
    return area * EARTH_RADIUS_KM ** 2


def _centroid(coords: list[tuple[float, float]]) -> dict:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return {"lat": round(sum(lats) / len(lats), 8), "lon": round(sum(lons) / len(lons), 8)}


def _bbox(coords: list[tuple[float, float]]) -> dict:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    }


def _segments_intersect(
    p1: tuple, p2: tuple, p3: tuple, p4: tuple
) -> bool:
    """
    Test if line segment p1-p2 intersects p3-p4 (excluding shared endpoints).
    Uses cross-product method.
    """
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def on_segment(p, q, r):
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    if d1 == 0 and on_segment(p3, p1, p4): return True
    if d2 == 0 and on_segment(p3, p2, p4): return True
    if d3 == 0 and on_segment(p1, p3, p2): return True
    if d4 == 0 and on_segment(p1, p4, p2): return True

    return False


def _has_self_intersection(coords: list[tuple[float, float]]) -> bool:
    """
    Check for self-intersections in the polygon ring.
    O(n²) — acceptable for typical AOI polygons (< 10,000 vertices).
    """
    n = len(coords)
    segments = [(coords[i], coords[(i + 1) % n]) for i in range(n - 1)]
    for i in range(len(segments)):
        for j in range(i + 2, len(segments)):
            if i == 0 and j == len(segments) - 1:
                continue  # skip adjacent edges that share endpoint
            if _segments_intersect(segments[i][0], segments[i][1],
                                   segments[j][0], segments[j][1]):
                return True
    return False


def _classify_environment(centroid: dict) -> EnvironmentClassification:
    """
    Coarse heuristic classification: ocean centroid vs land.
    Production: replaced by spatial join against stored boundary layer.
    """
    lat, lon = centroid["lat"], centroid["lon"]
    # Very coarse: if centroid is within major ocean bounding boxes → OFFSHORE
    pacific_1  = (-60 < lat < 65)  and (150 < lon <= 180)
    pacific_2  = (-60 < lat < 65)  and (-180 <= lon < -70)
    atlantic   = (-60 < lat < 70)  and (-70 < lon < -10)
    indian     = (-60 < lat < 30)  and (20 < lon < 100)
    arctic     = (lat > 70)
    if pacific_1 or pacific_2 or atlantic or indian or arctic:
        return EnvironmentClassification.OFFSHORE
    return EnvironmentClassification.ONSHORE


def validate_aoi_geometry(
    geometry: dict,
    max_area_km2: float = MAX_AREA_KM2_DEFAULT,
) -> ValidationResult:
    """
    Validate a GeoJSON geometry dict for AOI suitability.
    Returns a ValidationResult — never raises.
    """
    errors:   list[str] = []
    warnings: list[str] = []

    try:
        coords = _coords_from_geojson(geometry)
    except Exception as e:
        return ValidationResult(
            valid=False, errors=[f"Cannot parse geometry: {e}"],
            warnings=[], area_km2=None, centroid=None, bbox=None,
            environment=EnvironmentClassification.UNKNOWN,
            anti_meridian_risk=False,
        )

    # Rule 1: closed ring
    if coords[0] != coords[-1]:
        errors.append("Polygon ring is not closed: first and last coordinate must be identical.")

    # Rule 2: minimum ring length
    if len(coords) < 4:
        errors.append(f"Polygon ring must have at least 4 coordinate pairs (got {len(coords)}).")

    # Rule 3: coordinate range
    for lon, lat in coords:
        if not (-90 <= lat <= 90):
            errors.append(f"Latitude {lat} out of range [-90, 90].")
            break
    for lon, lat in coords:
        if not (-180 <= lon <= 180):
            errors.append(f"Longitude {lon} out of range [-180, 180].")
            break

    # Rule 4: self-intersections (only if ring is otherwise valid)
    if not errors and _has_self_intersection(coords):
        errors.append("Polygon has self-intersecting edges.")

    # Derived geometry
    area_km2 = _approx_area_km2(coords) if not errors else None
    centroid  = _centroid(coords)
    box       = _bbox(coords)

    # Rule 5: area limits
    if area_km2 is not None:
        if area_km2 < MIN_AREA_KM2:
            errors.append(f"AOI area {area_km2:.4f} km² is below minimum {MIN_AREA_KM2} km².")
        if area_km2 > max_area_km2:
            errors.append(f"AOI area {area_km2:.1f} km² exceeds maximum {max_area_km2:.0f} km².")

    # Rule 6: anti-meridian detection
    lon_span = box["max_lon"] - box["min_lon"] if box else 0
    anti_meridian = lon_span > 180
    if anti_meridian:
        warnings.append(
            f"AOI bounding box spans {lon_span:.1f}° longitude (> 180°). "
            f"Anti-meridian crossing detected — geometry should be split before scan submission."
        )

    # Rule 7: environment classification
    environment = _classify_environment(centroid)

    return ValidationResult(
        valid             = len(errors) == 0,
        errors            = errors,
        warnings          = warnings,
        area_km2          = area_km2,
        centroid          = centroid,
        bbox              = box,
        environment       = environment,
        anti_meridian_risk = anti_meridian,
    )