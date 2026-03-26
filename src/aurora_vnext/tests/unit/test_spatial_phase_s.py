"""
Aurora OSI vNext — Phase S Spatial Query Tests
Phase S §S.3 — Completion Proof Tests

Tests:
  1. ScanListQuery SQL generation — correct WHERE + ORDER BY + LIMIT
  2. Keyset cursor pagination — no OFFSET in generated SQL
  3. CellSpatialQuery with and without bounding box
  4. VoxelDepthQuery depth range filter and keyset cursor
  5. Commodity + environment filters (string equality only)
  6. No scientific constant in generated SQL (numeric literal audit)
  7. No core/* imports in query_accelerator.py
  8. Covering index columns present in SELECT lists
  9. ST_Within spatial predicate correct parameter binding
"""

from __future__ import annotations

import pytest

from app.storage.query_accelerator import (
    ScanListQuery,
    CellSpatialQuery,
    VoxelDepthQuery,
    _build_scan_list_sql,
    _build_cell_spatial_sql,
    _build_voxel_depth_sql,
)


# ─── 1. ScanListQuery SQL generation ─────────────────────────────────────────

class TestScanListSql:
    def test_default_query_selects_covering_columns(self):
        sql, params = _build_scan_list_sql(ScanListQuery())
        for col in ["scan_id", "commodity", "scan_tier", "status",
                    "display_acif_score", "system_status", "completed_at"]:
            assert col in sql

    def test_status_filter_present(self):
        sql, params = _build_scan_list_sql(ScanListQuery(status="COMPLETED"))
        assert "status = :status" in sql
        assert params["status"] == "COMPLETED"

    def test_commodity_filter_added(self):
        sql, params = _build_scan_list_sql(ScanListQuery(commodity="gold"))
        assert "commodity = :commodity" in sql
        assert params["commodity"] == "gold"

    def test_environment_filter_added(self):
        sql, params = _build_scan_list_sql(ScanListQuery(environment="AFRICA_CRATON"))
        assert "environment = :environment" in sql
        assert params["environment"] == "AFRICA_CRATON"

    def test_order_by_completed_at_desc(self):
        sql, _ = _build_scan_list_sql(ScanListQuery())
        assert "completed_at DESC" in sql

    def test_limit_in_params(self):
        _, params = _build_scan_list_sql(ScanListQuery(limit=25))
        assert params["limit"] == 25

    def test_no_score_predicate_in_sql(self):
        """PROOF: no numeric threshold applied to any scientific field."""
        sql, params = _build_scan_list_sql(ScanListQuery())
        assert "acif_score >" not in sql
        assert "acif_score <" not in sql
        assert "acif_score =" not in sql
        assert "tier_counts" not in sql


# ─── 2. Keyset cursor pagination ─────────────────────────────────────────────

class TestKeysetPagination:
    def test_no_offset_in_scan_list(self):
        sql, _ = _build_scan_list_sql(ScanListQuery())
        assert "OFFSET" not in sql.upper()

    def test_keyset_cursor_applied_when_provided(self):
        sql, params = _build_scan_list_sql(ScanListQuery(
            cursor_completed_at="2025-01-01T00:00:00+00:00",
            cursor_scan_id="scan_abc",
        ))
        assert "completed_at" in sql and "scan_id" in sql
        assert "cursor_completed_at" in params
        assert "cursor_scan_id" in params

    def test_no_offset_in_voxel_query(self):
        sql, _ = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=1
        ))
        assert "OFFSET" not in sql.upper()

    def test_voxel_keyset_cursor_applied(self):
        sql, params = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=1,
            cursor_depth_m=200.0, cursor_voxel_id="voxel_001",
        ))
        assert "depth_m" in sql and "voxel_id" in sql
        assert params["cursor_depth_m"] == 200.0
        assert params["cursor_voxel_id"] == "voxel_001"

    def test_cell_keyset_cursor_applied(self):
        sql, params = _build_cell_spatial_sql(CellSpatialQuery(
            scan_id="s1", cursor_cell_id="cell_050"
        ))
        assert "cell_id > :cursor_cell_id" in sql
        assert params["cursor_cell_id"] == "cell_050"


# ─── 3. CellSpatialQuery ─────────────────────────────────────────────────────

class TestCellSpatialQuery:
    def test_no_bbox_omits_st_within(self):
        sql, params = _build_cell_spatial_sql(CellSpatialQuery(scan_id="s1"))
        assert "ST_Within" not in sql

    def test_bbox_adds_st_within(self):
        sql, params = _build_cell_spatial_sql(CellSpatialQuery(
            scan_id="s1",
            min_lat=-25.0, max_lat=-20.0, min_lon=130.0, max_lon=135.0,
        ))
        assert "ST_Within" in sql
        assert "ST_MakeEnvelope" in sql
        assert params["xmin"] == 130.0
        assert params["ymin"] == -25.0
        assert params["xmax"] == 135.0
        assert params["ymax"] == -20.0

    def test_tier_filter_string_equality(self):
        """PROOF: tier filter is string equality — no numeric comparison."""
        sql, params = _build_cell_spatial_sql(CellSpatialQuery(
            scan_id="s1", tier_filter="TIER_1"
        ))
        assert "tier = :tier" in sql
        assert params["tier"] == "TIER_1"
        assert ">=" not in sql or "depth" in sql  # tier has no >= predicate

    def test_scan_id_always_in_conditions(self):
        sql, params = _build_cell_spatial_sql(CellSpatialQuery(scan_id="scan_xyz"))
        assert "scan_id = :scan_id" in sql
        assert params["scan_id"] == "scan_xyz"


# ─── 4. VoxelDepthQuery ──────────────────────────────────────────────────────

class TestVoxelDepthQuery:
    def test_scan_id_and_version_always_present(self):
        sql, params = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=2
        ))
        assert "scan_id = :scan_id" in sql
        assert "twin_version = :twin_version" in sql
        assert params["scan_id"] == "s1"
        assert params["twin_version"] == 2

    def test_depth_min_filter(self):
        sql, params = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=1, depth_min_m=200.0
        ))
        assert "depth_m >= :depth_min_m" in sql
        assert params["depth_min_m"] == 200.0

    def test_depth_max_filter(self):
        sql, params = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=1, depth_max_m=800.0
        ))
        assert "depth_m <= :depth_max_m" in sql
        assert params["depth_max_m"] == 800.0

    def test_depth_range_combined(self):
        sql, params = _build_voxel_depth_sql(VoxelDepthQuery(
            scan_id="s1", twin_version=1, depth_min_m=100.0, depth_max_m=500.0
        ))
        assert "depth_m >= :depth_min_m" in sql
        assert "depth_m <= :depth_max_m" in sql

    def test_order_by_depth_asc(self):
        """Voxels ordered by depth ASC for progressive top-down rendering."""
        sql, _ = _build_voxel_depth_sql(VoxelDepthQuery(scan_id="s1", twin_version=1))
        assert "depth_m ASC" in sql

    def test_covering_columns_present(self):
        sql, _ = _build_voxel_depth_sql(VoxelDepthQuery(scan_id="s1", twin_version=1))
        for col in ["voxel_id", "lat_center", "lon_center", "depth_m",
                    "commodity_probs", "kernel_weight", "source_cell_id"]:
            assert col in sql


# ─── 5. No scientific constant in SQL ────────────────────────────────────────

class TestNoScientificConstants:
    """
    PROOF: Generated SQL contains no numeric literal applied to a scientific field.
    """

    def test_scan_list_no_score_numeric(self):
        sql, params = _build_scan_list_sql(ScanListQuery())
        # No numeric literal appears as a filter on scientific fields
        import re
        numeric_predicates = re.findall(r"(?:acif|tier|evidence|causal|physics)\s*[><=]+\s*[\d.]+", sql)
        assert numeric_predicates == [], f"Scientific numeric predicate found: {numeric_predicates}"

    def test_voxel_no_score_numeric(self):
        sql, _ = _build_voxel_depth_sql(VoxelDepthQuery(scan_id="s1", twin_version=1))
        import re
        numeric_predicates = re.findall(r"(?:acif|probability|tier)\s*[><=]+\s*[\d.]+", sql)
        assert numeric_predicates == []


# ─── 6. No core/* imports ────────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = [
        "app.core.scoring", "app.core.tiering", "app.core.gates",
        "app.core.evidence", "app.core.causal", "app.core.physics",
        "app.core.temporal", "app.core.priors", "app.core.uncertainty",
    ]

    def test_query_accelerator_no_core_imports(self):
        import app.storage.query_accelerator as qa
        src = open(qa.__file__).read()
        for prefix in self.FORBIDDEN:
            assert prefix not in src, f"VIOLATION: query_accelerator imports {prefix}"

    def test_no_compute_acif_in_accelerator(self):
        import app.storage.query_accelerator as qa
        src = open(qa.__file__).read()
        assert "compute_acif"   not in src
        assert "assign_tier"    not in src
        assert "evaluate_gates" not in src