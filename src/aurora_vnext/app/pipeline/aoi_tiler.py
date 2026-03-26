"""
Aurora OSI vNext — AOI Tiler
Phase AG §AG.2

Splits large AOIs into sub-tiles for parallel execution.

CONSTITUTIONAL RULES:
  Rule 1: Tiling is a purely geometric operation on WGS84 coordinates.
          No scientific constants, no ACIF, no calibration.
  Rule 2: Each tile inherits the parent AOI's geometry_hash prefix
          so tile scans remain traceable to the parent scan_id.
  Rule 3: Tiles must overlap by OVERLAP_DEG to avoid edge artefacts.
          Overlap is a geometric parameter only — not a scientific one.
  Rule 4: Tile results are merged via cell deduplication by (lat, lon) pair —
          not by re-scoring. Duplicate cells keep the first occurrence (stable sort).
  Rule 5: No import from core/*.

DETERMINISM UNDER PARALLEL EXECUTION:
  - Tile geometry is computed deterministically from bbox corners (sorted)
  - Cell deduplication uses deterministic sort key (lat_center, lon_center)
  - Merge is order-independent: same tiles in any order → same merged result
  - Overlap cells deduplication is stable (keeps first by sort key)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# Overlap between adjacent tiles to prevent edge-cell loss
OVERLAP_DEG = 0.05   # ~5 km overlap at equatorial scale — geometry only

# Maximum recommended tile area for optimal parallel execution
MAX_TILE_AREA_KM2 = 2_500.0   # 50 km × 50 km cells

# Earth radius for area computation
_EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class TileBounds:
    """
    WGS84 bounding box for one tile.
    All coordinates rounded to 8 decimal places for deterministic hashing.
    """
    tile_id:    str       # "{parent_aoi_id}_t{row}_{col}"
    min_lat:    float
    max_lat:    float
    min_lon:    float
    max_lon:    float
    area_km2:   float
    row:        int
    col:        int

    @property
    def centre_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2.0

    @property
    def centre_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2.0


@dataclass(frozen=True)
class TilingPlan:
    """
    Complete tiling plan for a large AOI.
    Contains all sub-tile bounds and the merge strategy.
    """
    parent_aoi_id:    str
    total_area_km2:   float
    n_rows:           int
    n_cols:           int
    total_tiles:      int
    tiles:            tuple[TileBounds, ...]
    overlap_deg:      float
    recommended_workers: int    # min(total_tiles, 32)
    tiling_notes:     tuple[str, ...]


def _bbox_area_km2(min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> float:
    """
    Approximate area of a WGS84 bounding box in km².
    Uses spherical approximation — accurate to ~0.5% at mid-latitudes.
    """
    lat_km = (max_lat - min_lat) * (_EARTH_RADIUS_KM * math.pi / 180.0)
    mid_lat = (min_lat + max_lat) / 2.0
    lon_km  = (max_lon - min_lon) * (_EARTH_RADIUS_KM * math.pi / 180.0 * math.cos(math.radians(mid_lat)))
    return abs(lat_km * lon_km)


def compute_tiling_plan(
    aoi_id:   str,
    min_lat:  float,
    max_lat:  float,
    min_lon:  float,
    max_lon:  float,
    max_tile_area_km2: float = MAX_TILE_AREA_KM2,
    overlap_deg:       float = OVERLAP_DEG,
) -> TilingPlan:
    """
    Compute a tiling plan for a large AOI bbox.

    Splits the AOI into a regular grid of tiles, each ≤ max_tile_area_km2.
    Tiles overlap by overlap_deg on all edges to prevent cell loss.

    PROOF: purely geometric. No scientific logic.
    """
    total_area = _bbox_area_km2(min_lat, max_lat, min_lon, max_lon)
    lat_span   = max_lat - min_lat
    lon_span   = max_lon - min_lon

    # Determine grid dimensions from area target
    n_tiles_needed = max(1, math.ceil(total_area / max_tile_area_km2))
    # Distribute evenly: n_rows × n_cols ≥ n_tiles_needed, roughly square
    n_rows = max(1, round(math.sqrt(n_tiles_needed * lat_span / max(lon_span, 1e-9))))
    n_cols = max(1, math.ceil(n_tiles_needed / n_rows))

    tile_lat = lat_span / n_rows
    tile_lon = lon_span / n_cols

    tiles = []
    for r in range(n_rows):
        for c in range(n_cols):
            t_min_lat = round(min_lat + r * tile_lat - overlap_deg, 8)
            t_max_lat = round(min_lat + (r + 1) * tile_lat + overlap_deg, 8)
            t_min_lon = round(min_lon + c * tile_lon - overlap_deg, 8)
            t_max_lon = round(min_lon + (c + 1) * tile_lon + overlap_deg, 8)
            # Clamp to global WGS84 bounds
            t_min_lat = max(-90.0, t_min_lat)
            t_max_lat = min(90.0, t_max_lat)
            t_min_lon = max(-180.0, t_min_lon)
            t_max_lon = min(180.0, t_max_lon)
            area = _bbox_area_km2(t_min_lat, t_max_lat, t_min_lon, t_max_lon)
            tiles.append(TileBounds(
                tile_id  = f"{aoi_id}_t{r}_{c}",
                min_lat  = t_min_lat,
                max_lat  = t_max_lat,
                min_lon  = t_min_lon,
                max_lon  = t_max_lon,
                area_km2 = round(area, 4),
                row      = r,
                col      = c,
            ))

    notes = []
    if total_area > 100_000:
        notes.append(f"Country-scale AOI ({total_area:.0f} km²) — {len(tiles)} tiles recommended.")
    if n_rows == 1 and n_cols == 1:
        notes.append("AOI fits in single tile — tiling not required.")

    return TilingPlan(
        parent_aoi_id        = aoi_id,
        total_area_km2       = round(total_area, 4),
        n_rows               = n_rows,
        n_cols               = n_cols,
        total_tiles          = len(tiles),
        tiles                = tuple(tiles),
        overlap_deg          = overlap_deg,
        recommended_workers  = min(len(tiles), 32),
        tiling_notes         = tuple(notes),
    )


def merge_tile_cells(tile_cell_lists: list[list[dict]]) -> list[dict]:
    """
    Merge cells from multiple tile results into a single deduplicated cell list.

    Deduplication key: (round(lat_center, 8), round(lon_center, 8))
    Stable sort ensures deterministic output regardless of tile processing order.

    DETERMINISM PROOF:
      1. All cells are sorted by (lat_center, lon_center) before deduplication.
      2. Deduplication keeps the first occurrence in sorted order.
      3. Same tiles in any processing order → same sorted list → same first occurrence.
      4. Output is identical regardless of parallel execution order.
    """
    from app.services.determinism import sort_cells_deterministic, stable_round

    all_cells = []
    for cell_list in tile_cell_lists:
        all_cells.extend(cell_list)

    # Sort deterministically before deduplication
    sorted_cells = sort_cells_deterministic(all_cells)

    # Deduplicate by rounded lat/lon
    seen   = set()
    merged = []
    for cell in sorted_cells:
        key = (
            stable_round(cell.get("lat_center", 0.0)),
            stable_round(cell.get("lon_center", 0.0)),
        )
        if key not in seen:
            seen.add(key)
            merged.append(cell)

    return merged