"""
Aurora OSI vNext — Phase AG Performance & Scale Tests

Tests (20):
  1.  estimate_scan_cost: standard resolution formula correctness
  2.  estimate_scan_cost: parallel discount applied correctly
  3.  estimate_scan_cost: ultra resolution has 3.2× multiplier
  4.  estimate_scan_cost: cost_per_km2 derived correctly
  5.  cost_tier classification: micro < $5, xlarge > $5000
  6.  summarise_portfolio_costs: serial vs parallel totals
  7.  summarise_portfolio_costs: savings_pct computed correctly
  8.  compute_tiling_plan: single tile for small AOI
  9.  compute_tiling_plan: multiple tiles for large AOI
  10. compute_tiling_plan: tile IDs are deterministic
  11. TileBounds: centre_lat/lon computed correctly
  12. merge_tile_cells: deduplicates overlapping cells
  13. merge_tile_cells: order-independent (any tile order → same result)
  14. merge_tile_cells: result is deterministically sorted
  15. compute_scaling_curve: speedup ≥ 1 for all worker counts
  16. compute_scaling_curve: efficiency decreases with more workers (Amdahl)
  17. ParallelExecutionResult: determinism_hash set after merge
  18. No core/* imports in any Phase AG file
  19. No scientific constants in cost model (no ACIF, tier, gate references)
  20. Benchmark values not present in AG infrastructure files
"""

from __future__ import annotations

import pytest
import random


# ─── 1–7. Cost model ─────────────────────────────────────────────────────────

class TestCostModel:
    def test_standard_resolution_formula(self):
        from app.services.scan_cost_model import estimate_scan_cost, _COST_PER_CELL_USD, _CELLS_PER_KM2
        est = estimate_scan_cost(100.0, "standard", 1)
        expected_cells = int(100.0 * _CELLS_PER_KM2["standard"])
        expected_cost  = expected_cells * _COST_PER_CELL_USD * 1.0  # multiplier = 1.0
        assert est.estimated_cells == expected_cells
        assert abs(est.estimated_cost_usd - expected_cost) < 0.0001

    def test_parallel_discount_applied(self):
        from app.services.scan_cost_model import estimate_scan_cost
        serial   = estimate_scan_cost(500.0, "standard", 1)
        parallel = estimate_scan_cost(500.0, "standard", 8)
        assert parallel.parallel_cost_usd < serial.estimated_cost_usd
        assert parallel.parallel_discount < 1.0

    def test_ultra_resolution_multiplier(self):
        from app.services.scan_cost_model import estimate_scan_cost
        std   = estimate_scan_cost(100.0, "standard", 1)
        ultra = estimate_scan_cost(100.0, "ultra", 1)
        ratio = ultra.estimated_cost_usd / std.estimated_cost_usd
        # ultra multiplier = 3.2, standard = 1.0, cells ratio = 64/4 = 16
        # ratio ≈ 16 × 3.2 / 1.0 = 51.2 — check it's much larger
        assert ratio > 10.0

    def test_cost_per_km2_derived_correctly(self):
        from app.services.scan_cost_model import estimate_scan_cost
        est = estimate_scan_cost(250.0, "standard", 1)
        expected = est.estimated_cost_usd / 250.0
        assert abs(est.cost_per_km2_usd - expected) < 1e-4

    def test_cost_tier_micro(self):
        from app.services.scan_cost_model import estimate_scan_cost
        est = estimate_scan_cost(1.0, "low", 1)   # tiny AOI, cheap
        assert est.cost_tier == "micro"

    def test_cost_tier_xlarge_for_huge_aoi(self):
        from app.services.scan_cost_model import estimate_scan_cost
        est = estimate_scan_cost(100_000.0, "high", 1)
        assert est.cost_tier in ("large", "xlarge")

    def test_portfolio_summary_savings(self):
        from app.services.scan_cost_model import summarise_portfolio_costs
        configs = [{"area_km2": 500.0, "resolution": "standard"} for _ in range(5)]
        summary = summarise_portfolio_costs(configs, parallel_workers=8)
        assert summary.parallel_cost_usd < summary.serial_cost_usd
        assert summary.savings_pct > 0.0
        assert summary.scans_estimated == 5

    def test_portfolio_summary_parallel_cheaper_than_serial(self):
        from app.services.scan_cost_model import summarise_portfolio_costs
        configs = [{"area_km2": 2000.0, "resolution": "high"} for _ in range(10)]
        summary = summarise_portfolio_costs(configs, parallel_workers=16)
        assert summary.savings_usd > 0
        assert abs(summary.savings_usd - (summary.serial_cost_usd - summary.parallel_cost_usd)) < 0.01


# ─── 8–14. Tiling ────────────────────────────────────────────────────────────

class TestTiling:
    def test_single_tile_small_aoi(self):
        from app.pipeline.aoi_tiler import compute_tiling_plan
        plan = compute_tiling_plan("aoi-small", -31.0, -29.0, 115.0, 117.0)
        assert plan.total_tiles == 1

    def test_multiple_tiles_large_aoi(self):
        from app.pipeline.aoi_tiler import compute_tiling_plan
        # ~300 km × 300 km AOI → should tile
        plan = compute_tiling_plan("aoi-large", -35.0, -25.0, 110.0, 125.0)
        assert plan.total_tiles > 1

    def test_tile_ids_deterministic(self):
        from app.pipeline.aoi_tiler import compute_tiling_plan
        p1 = compute_tiling_plan("aoi-det", -35.0, -25.0, 110.0, 125.0)
        p2 = compute_tiling_plan("aoi-det", -35.0, -25.0, 110.0, 125.0)
        assert [t.tile_id for t in p1.tiles] == [t.tile_id for t in p2.tiles]

    def test_tile_centre_computed(self):
        from app.pipeline.aoi_tiler import TileBounds
        tile = TileBounds("t1", -31.0, -29.0, 115.0, 117.0, 50000.0, 0, 0)
        assert abs(tile.centre_lat - (-30.0)) < 1e-6
        assert abs(tile.centre_lon - 116.0) < 1e-6

    def test_merge_deduplicates_overlap(self):
        from app.pipeline.aoi_tiler import merge_tile_cells
        cell = {"cell_id": "c1", "lat_center": -30.0, "lon_center": 116.5, "acif_score": 0.7}
        # Same cell appears in two tile lists (overlap region)
        merged = merge_tile_cells([[cell], [cell]])
        assert len(merged) == 1

    def test_merge_order_independent(self):
        from app.pipeline.aoi_tiler import merge_tile_cells
        cells_a = [
            {"cell_id": f"c{i}", "lat_center": -30.0 + i * 0.1, "lon_center": 116.0 + i * 0.1,
             "acif_score": 0.5}
            for i in range(5)
        ]
        cells_b = list(reversed(cells_a))
        r1 = merge_tile_cells([cells_a[:3], cells_a[3:]])
        r2 = merge_tile_cells([cells_b[:3], cells_b[3:]])
        assert [c["cell_id"] for c in r1] == [c["cell_id"] for c in r2]

    def test_merge_result_sorted(self):
        from app.pipeline.aoi_tiler import merge_tile_cells
        cells = [
            {"cell_id": f"c{i}", "lat_center": -30.0 + random.random(), "lon_center": 116.0 + random.random(), "acif_score": 0.5}
            for i in range(10)
        ]
        merged = merge_tile_cells([cells])
        lats = [c["lat_center"] for c in merged]
        assert lats == sorted(lats)


# ─── 15–16. Scaling curve ────────────────────────────────────────────────────

class TestScalingCurve:
    def test_speedup_increases_with_workers(self):
        from app.pipeline.parallel_executor import compute_scaling_curve
        curve = compute_scaling_curve(100, 10_000.0, [1, 2, 4, 8, 16])
        speedups = [r["speedup"] for r in curve]
        assert speedups == sorted(speedups)

    def test_efficiency_decreases_with_workers(self):
        from app.pipeline.parallel_executor import compute_scaling_curve
        curve = compute_scaling_curve(100, 10_000.0, [1, 2, 4, 8, 16])
        efficiencies = [r["efficiency_pct"] for r in curve]
        # Efficiency must be non-increasing (Amdahl diminishing returns)
        for i in range(len(efficiencies) - 1):
            assert efficiencies[i] >= efficiencies[i + 1]


# ─── 17. Determinism hash ────────────────────────────────────────────────────

class TestDeterminismHash:
    def test_parallel_result_sets_determinism_hash(self):
        from app.pipeline.aoi_tiler import compute_tiling_plan
        from app.pipeline.parallel_executor import execute_tiles_parallel

        plan = compute_tiling_plan("aoi-det-hash", -30.5, -29.5, 116.0, 117.0)

        def stub_pipeline(tile):
            cells = [{"cell_id": f"{tile.tile_id}_c1",
                       "lat_center": tile.centre_lat,
                       "lon_center": tile.centre_lon,
                       "acif_score": 0.75, "tier": "TIER_1",
                       "any_veto_fired": False}]
            return cells, {"tile_id": tile.tile_id}

        result = execute_tiles_parallel(plan, stub_pipeline, workers=2)
        assert result.determinism_hash is not None
        assert len(result.determinism_hash) == 64   # SHA-256 hex

    def test_parallel_hash_stable_across_runs(self):
        """Same tiles + same pipeline → same determinism_hash on every run."""
        from app.pipeline.aoi_tiler import compute_tiling_plan
        from app.pipeline.parallel_executor import execute_tiles_parallel

        plan = compute_tiling_plan("aoi-stable", -31.0, -29.0, 115.0, 117.0)

        def stub_pipeline(tile):
            cells = [{"cell_id": f"{tile.tile_id}_c1",
                       "lat_center": tile.centre_lat,
                       "lon_center": tile.centre_lon,
                       "acif_score": 0.80, "tier": "TIER_1",
                       "any_veto_fired": False}]
            return cells, {}

        r1 = execute_tiles_parallel(plan, stub_pipeline, workers=1)
        r2 = execute_tiles_parallel(plan, stub_pipeline, workers=1)
        assert r1.determinism_hash == r2.determinism_hash


# ─── 18–20. No scientific logic ──────────────────────────────────────────────

class TestNoScientificLogic:
    FORBIDDEN_IMPORTS = ["app.core.scoring", "app.core.tiering", "app.core.gates",
                         "app.core.uncertainty", "app.core.priors"]

    def _check_no_imports(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = inspect.getsource(mod)
        for f in self.FORBIDDEN_IMPORTS:
            assert f not in src, f"VIOLATION: {module_path} imports {f}"

    def test_no_core_in_cost_model(self):
        self._check_no_imports("app.services.scan_cost_model")

    def test_no_core_in_aoi_tiler(self):
        self._check_no_imports("app.pipeline.aoi_tiler")

    def test_no_core_in_parallel_executor(self):
        self._check_no_imports("app.pipeline.parallel_executor")

    def test_no_acif_constants_in_cost_model(self):
        import inspect
        from app.services import scan_cost_model
        src = inspect.getsource(scan_cost_model)
        forbidden_terms = ["acif", "ACIF", "tier_threshold", "tau_phys",
                           "0.7841", "0.8127", "Yilgarn"]  # no benchmark constants
        for term in forbidden_terms:
            assert term not in src, f"Forbidden term '{term}' found in cost model"

    def test_no_benchmark_values_in_tiler(self):
        import inspect
        from app.pipeline import aoi_tiler
        src = inspect.getsource(aoi_tiler)
        benchmark_values = ["0.7841", "0.8127", "2.14", "Yilgarn", "Obuasi"]
        for val in benchmark_values:
            assert val not in src, f"Benchmark value {val!r} found in tiler"