"""
Aurora OSI vNext — Map Export Model
Phase AA §AA.5

Defines the layer registry and export request types for KML/KMZ and GeoJSON exports.

CONSTITUTIONAL RULES:
  Rule 1: Every layer sources its data from a specific stored canonical field.
          The field mapping is declared in LayerDefinition.source_field.
          No layer derives tier membership, ACIF, or anomaly status at export time.
  Rule 2: Coordinate precision is preserved verbatim — no smoothing, rounding,
          or simplification unless an explicit simplification_version is set.
  Rule 3: Export is always read-only. No write to canonical storage occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExportFormat(str, Enum):
    KML     = "kml"
    KMZ     = "kmz"
    GEOJSON = "geojson"


class LayerType(str, Enum):
    AOI_POLYGON          = "aoi_polygon"
    SCAN_CELL_GRID       = "scan_cell_grid"
    TIER_1_CELLS         = "tier_1_cells"
    TIER_2_CELLS         = "tier_2_cells"
    TIER_3_CELLS         = "tier_3_cells"
    VETOED_CELLS         = "vetoed_cells"
    ANOMALY_POLYGONS     = "anomaly_polygons"
    TARGET_CLUSTERS      = "target_clusters"
    VOXEL_SURFACE        = "voxel_surface"
    DRILL_CANDIDATES     = "drill_candidates"
    GROUND_TRUTH_POINTS  = "ground_truth_points"
    CONCESSION_BOUNDARIES = "concession_boundaries"


@dataclass(frozen=True)
class LayerDefinition:
    """
    Canonical definition of a map layer.

    source_field: the stored canonical field that provides this layer's geometry.
    filter_field: optional stored field used to filter features (e.g., tier).
    filter_value: the exact stored value to match (no derivation allowed).

    PROOF: every layer is fully defined by its source_field. No derivation
    from scores or probabilities occurs at export time.
    """
    layer_type:         LayerType
    display_name:       str
    source_field:       str          # canonical field path
    filter_field:       Optional[str] = None
    filter_value:       Optional[str] = None
    kml_style_id:       Optional[str] = None
    description:        str = ""


# ---------------------------------------------------------------------------
# Layer registry — canonical source field mapping
# ---------------------------------------------------------------------------

LAYER_REGISTRY: dict[LayerType, LayerDefinition] = {
    LayerType.AOI_POLYGON: LayerDefinition(
        layer_type   = LayerType.AOI_POLYGON,
        display_name = "Area of Interest",
        source_field = "scan.aoi_polygon",
        kml_style_id = "aoi_style",
        description  = "AOI boundary polygon as stored in canonical scan record.",
    ),
    LayerType.SCAN_CELL_GRID: LayerDefinition(
        layer_type   = LayerType.SCAN_CELL_GRID,
        display_name = "Scan Cell Grid",
        source_field = "cell.lat_center, cell.lon_center",
        kml_style_id = "grid_style",
        description  = "Cell centroids as stored in ScanCell records.",
    ),
    LayerType.TIER_1_CELLS: LayerDefinition(
        layer_type   = LayerType.TIER_1_CELLS,
        display_name = "Tier 1 Cells",
        source_field = "cell.lat_center, cell.lon_center",
        filter_field = "cell.tier",
        filter_value = "TIER_1",
        kml_style_id = "tier1_style",
        description  = "Cells with stored tier=TIER_1. Not derived at export time.",
    ),
    LayerType.TIER_2_CELLS: LayerDefinition(
        layer_type   = LayerType.TIER_2_CELLS,
        display_name = "Tier 2 Cells",
        source_field = "cell.lat_center, cell.lon_center",
        filter_field = "cell.tier",
        filter_value = "TIER_2",
        kml_style_id = "tier2_style",
        description  = "Cells with stored tier=TIER_2. Not derived at export time.",
    ),
    LayerType.TIER_3_CELLS: LayerDefinition(
        layer_type   = LayerType.TIER_3_CELLS,
        display_name = "Tier 3 Cells",
        source_field = "cell.lat_center, cell.lon_center",
        filter_field = "cell.tier",
        filter_value = "TIER_3",
        kml_style_id = "tier3_style",
        description  = "Cells with stored tier=TIER_3. Not derived at export time.",
    ),
    LayerType.VETOED_CELLS: LayerDefinition(
        layer_type   = LayerType.VETOED_CELLS,
        display_name = "Vetoed / Blocked Cells",
        source_field = "cell.lat_center, cell.lon_center",
        filter_field = "cell.any_veto_fired",
        filter_value = "True",
        kml_style_id = "veto_style",
        description  = "Cells where stored any_veto_fired=True. Veto reason from cell.veto_explanation.",
    ),
    LayerType.GROUND_TRUTH_POINTS: LayerDefinition(
        layer_type   = LayerType.GROUND_TRUTH_POINTS,
        display_name = "Ground Truth Points",
        source_field = "ground_truth_record.lat, ground_truth_record.lon",
        filter_field = "ground_truth_record.status",
        filter_value = "approved",
        kml_style_id = "gt_style",
        description  = "Approved ground-truth record locations. Approved only.",
    ),
    LayerType.VOXEL_SURFACE: LayerDefinition(
        layer_type   = LayerType.VOXEL_SURFACE,
        display_name = "Voxel Surface Projection",
        source_field = "voxel.lat_center, voxel.lon_center, voxel.depth_m",
        kml_style_id = "voxel_style",
        description  = "Shallowest voxel layer per cell, projected to surface.",
    ),
    LayerType.DRILL_CANDIDATES: LayerDefinition(
        layer_type   = LayerType.DRILL_CANDIDATES,
        display_name = "Drill Candidate Pins",
        source_field = "drill_candidate.lat, drill_candidate.lon",
        kml_style_id = "drill_style",
        description  = "Stored drill candidate points.",
    ),
}


@dataclass(frozen=True)
class MapExportRequest:
    scan_id:       str
    format:        ExportFormat
    layers:        tuple[LayerType, ...]
    include_hash:  bool = True   # embed geometry_hash in KML ExtendedData
    simplification_version: Optional[str] = None  # None = no simplification