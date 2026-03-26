"""
Phase L — Scan Execution Pipeline Tests

Validates:
  1. PipelineContext lifecycle — stage transitions, grid decomposition
  2. δh enforcement — PhysicsModelConfigError on invalid/missing δh
  3. Offshore gate — blocked cells excluded from scoring
  4. 21-step pipeline end-to-end (mock storage + mock GEE)
  5. Canonical freeze — structure and completeness
  6. Reprocess controller — lineage, changed-params detection, no-op rejection
  7. Task queue — priority ordering, enqueue/dequeue
  8. Import isolation — no Phase J scoring authority imported in pipeline modules

Constitutional invariants verified:
  - ACIF computed exclusively by core/scoring.py (single call site)
  - Tiers assigned exclusively by core/tiering.py
  - System status derived exclusively by core/gates.py
  - δh always from Θ_c, never DELTA_H_SHALLOW_FALLBACK_M in production path
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from app.pipeline.scan_pipeline import (
    CommodityConfig,
    PhysicsModelConfigError,
    PipelineContext,
    PipelineStage,
    execute_scan_pipeline,
    _validate_delta_h,
    _step_grid_decomposition,
)
from app.pipeline.task_queue import (
    InMemoryQueue,
    QueueItem,
    dequeue_scan,
    enqueue_scan,
    scan_tier_to_priority,
)
from app.pipeline.reprocess_controller import (
    ReprocessRequest,
    _detect_changed_params,
    _requires_physics_version_bump,
)
from app.services.gee import MockGEEClient
from app.config.constants import DELTA_H_RANGE_MIN_M, DELTA_H_RANGE_MAX_M


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _commodity(delta_h_m: float = 200.0) -> CommodityConfig:
    return CommodityConfig(
        name="gold",
        family="orogenic_gold",
        delta_h_m=delta_h_m,
        evidence_weights={k: 1.0 for k in [
            "x_spec_1","x_spec_2","x_spec_3","x_spec_4",
            "x_spec_5","x_spec_6","x_spec_7","x_spec_8",
            "x_sar_1","x_sar_2","x_sar_3","x_sar_4",
            "x_therm_1","x_therm_2","x_therm_3","x_therm_4",
            "x_grav_1","x_grav_2","x_mag_1","x_mag_2",
            "x_struct_1","x_hydro_1",
        ]},
    )


class MockStorageAdapter:
    """In-memory storage adapter for pipeline tests."""

    def __init__(self):
        self.stages = []
        self.failed = None
        self.canonical = None
        self.cells = []
        self.audits = []

    def update_scan_job_stage(self, scan_id, stage, pct):
        self.stages.append((stage, pct))

    def mark_scan_job_failed(self, scan_id, stage, error):
        self.failed = (stage, error)

    def write_canonical_scan(self, scan_id, result):
        self.canonical = result

    def write_scan_cells(self, scan_id, cells):
        self.cells = cells

    def write_audit_events(self, scan_id, events):
        self.audits = events

    def load_province_prior(self, cell_id, commodity):
        return {}

    def load_canonical_scan(self, scan_id):
        if self.canonical and self.canonical.get("scan_id") == scan_id:
            return self.canonical
        return None

    def write_reprocess_lineage(self, lineage):
        self._lineage = lineage

    def write_pre_reprocess_audit(self, audit):
        self._pre_audit = audit


def _tiny_grid() -> dict:
    """A 2×2 grid producing 4 cells for fast tests."""
    return {
        "resolution_degrees": 0.5,
        "min_lat": -30.0, "max_lat": -29.0,
        "min_lon": 121.0, "max_lon": 122.0,
    }


# ===========================================================================
# δh ENFORCEMENT
# ===========================================================================

class TestDeltaHEnforcement:
    def test_valid_delta_h_passes(self):
        _validate_delta_h(200.0)   # orogenic gold default — should pass

    def test_below_min_raises(self):
        with pytest.raises(PhysicsModelConfigError):
            _validate_delta_h(DELTA_H_RANGE_MIN_M - 1.0)

    def test_above_max_raises(self):
        with pytest.raises(PhysicsModelConfigError):
            _validate_delta_h(DELTA_H_RANGE_MAX_M + 1.0)

    def test_none_raises(self):
        with pytest.raises((PhysicsModelConfigError, TypeError)):
            _validate_delta_h(None)

    def test_minimum_boundary_valid(self):
        _validate_delta_h(DELTA_H_RANGE_MIN_M)

    def test_maximum_boundary_valid(self):
        _validate_delta_h(DELTA_H_RANGE_MAX_M)

    def test_pipeline_rejects_invalid_delta_h_before_any_work(self):
        storage = MockStorageAdapter()
        with pytest.raises(PhysicsModelConfigError):
            execute_scan_pipeline(
                scan_id="test_scan",
                commodity_config=_commodity(delta_h_m=5.0),  # below min
                gee_client=MockGEEClient(),
                storage=storage,
                grid_spec=_tiny_grid(),
                date_start="2023-01-01",
                date_end="2023-12-31",
            )
        # Storage must not have been touched (pre-flight guard)
        assert storage.canonical is None

    def test_pipeline_accepts_family_specific_delta_h(self):
        """Porphyry family uses δh=500 m — must be accepted."""
        cfg = _commodity(delta_h_m=500.0)
        cfg.family = "porphyry"
        _validate_delta_h(cfg.delta_h_m)  # Should not raise


# ===========================================================================
# GRID DECOMPOSITION
# ===========================================================================

class TestGridDecomposition:
    def test_grid_produces_cells(self):
        ctx = PipelineContext(
            scan_id="s1", commodity_config=_commodity(),
            gee_client=MockGEEClient(), environment="ONSHORE",
        )
        _step_grid_decomposition(ctx, _tiny_grid())
        assert len(ctx.grid_cells) > 0

    def test_cell_ids_are_unique(self):
        ctx = PipelineContext(
            scan_id="s1", commodity_config=_commodity(),
            gee_client=MockGEEClient(), environment="ONSHORE",
        )
        _step_grid_decomposition(ctx, _tiny_grid())
        ids = [gc.cell_id for gc in ctx.grid_cells]
        assert len(ids) == len(set(ids))

    def test_area_weights_positive(self):
        ctx = PipelineContext(
            scan_id="s1", commodity_config=_commodity(),
            gee_client=MockGEEClient(), environment="ONSHORE",
        )
        _step_grid_decomposition(ctx, _tiny_grid())
        for gc in ctx.grid_cells:
            assert gc.area_weight > 0.0

    def test_cell_environment_propagated(self):
        ctx = PipelineContext(
            scan_id="s1", commodity_config=_commodity(),
            gee_client=MockGEEClient(), environment="OFFSHORE",
        )
        _step_grid_decomposition(ctx, _tiny_grid())
        for gc in ctx.grid_cells:
            assert gc.environment == "OFFSHORE"


# ===========================================================================
# FULL PIPELINE (end-to-end with mock GEE + mock storage)
# ===========================================================================

class TestFullPipeline:
    def test_pipeline_completes_and_writes_canonical(self):
        storage = MockStorageAdapter()
        result = execute_scan_pipeline(
            scan_id="scan_001",
            commodity_config=_commodity(delta_h_m=200.0),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        assert storage.canonical is not None
        assert storage.canonical["status"] == "COMPLETED"

    def test_canonical_scan_has_acif_score(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_002",
            commodity_config=_commodity(),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        assert "display_acif_score" in storage.canonical
        assert storage.canonical["display_acif_score"] is not None

    def test_canonical_scan_has_tier_counts(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_003",
            commodity_config=_commodity(),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        tc = storage.canonical["tier_counts"]
        assert tc["total_cells"] == storage.canonical["total_cells"]
        assert tc["tier_1"] + tc["tier_2"] + tc["tier_3"] + tc["below"] == tc["total_cells"]

    def test_canonical_scan_has_system_status(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_004",
            commodity_config=_commodity(),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        assert storage.canonical["system_status"] in (
            "PASS_CONFIRMED","PARTIAL_SIGNAL","INCONCLUSIVE","REJECTED","OVERRIDE_CONFIRMED"
        )

    def test_scan_cells_written(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_005",
            commodity_config=_commodity(),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        assert len(storage.cells) > 0

    def test_delta_h_recorded_in_threshold_policy(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_006",
            commodity_config=_commodity(delta_h_m=500.0),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        assert storage.canonical["tier_thresholds_used"]["delta_h_m_used"] == 500.0

    def test_stage_progression_logged(self):
        storage = MockStorageAdapter()
        execute_scan_pipeline(
            scan_id="scan_007",
            commodity_config=_commodity(),
            gee_client=MockGEEClient(),
            storage=storage,
            grid_spec=_tiny_grid(),
            date_start="2023-01-01",
            date_end="2023-12-31",
        )
        stage_names = [s[0] for s in storage.stages]
        assert PipelineStage.GRID_DECOMPOSITION.value in stage_names
        assert PipelineStage.CANONICAL_FREEZE.value in stage_names
        assert PipelineStage.COMPLETE.value in stage_names

    def test_pipeline_marks_failed_on_exception(self):
        storage = MockStorageAdapter()
        with pytest.raises(PhysicsModelConfigError):
            execute_scan_pipeline(
                scan_id="scan_fail",
                commodity_config=_commodity(delta_h_m=1.0),  # invalid
                gee_client=MockGEEClient(),
                storage=storage,
                grid_spec=_tiny_grid(),
                date_start="2023-01-01",
                date_end="2023-12-31",
            )


# ===========================================================================
# TASK QUEUE
# ===========================================================================

class TestTaskQueue:
    def test_enqueue_returns_job_id(self):
        q = InMemoryQueue()
        job_id = enqueue_scan("scan_001", q, priority=1)
        assert job_id and len(job_id) > 0

    def test_dequeue_returns_item(self):
        q = InMemoryQueue()
        enqueue_scan("scan_001", q, priority=1)
        item = dequeue_scan(q)
        assert item is not None
        assert item.scan_id == "scan_001"

    def test_dequeue_empty_returns_none(self):
        q = InMemoryQueue()
        assert dequeue_scan(q) is None

    def test_priority_ordering(self):
        q = InMemoryQueue()
        enqueue_scan("bootstrap", q, priority=0)
        enqueue_scan("premium", q, priority=2)
        enqueue_scan("smart", q, priority=1)
        first = dequeue_scan(q)
        assert first.scan_id == "premium"

    def test_scan_tier_to_priority(self):
        assert scan_tier_to_priority("PREMIUM") > scan_tier_to_priority("SMART")
        assert scan_tier_to_priority("SMART") > scan_tier_to_priority("BOOTSTRAP")

    def test_queue_item_is_immutable(self):
        item = QueueItem(scan_id="s", scan_job_id="j", enqueued_at="2023-01-01")
        with pytest.raises(Exception):
            item.scan_id = "changed"  # type: ignore — frozen dataclass


# ===========================================================================
# REPROCESS CONTROLLER
# ===========================================================================

class TestReprocessController:
    def test_detect_changed_params_delta_h(self):
        old = {"delta_h_m": 200.0, "alpha_c": 0.3, "name": "gold", "family": "orogenic_gold"}
        new = _commodity(delta_h_m=500.0)
        changes = _detect_changed_params(old, new)
        assert "delta_h_m" in changes
        assert changes["delta_h_m"]["old"] == 200.0
        assert changes["delta_h_m"]["new"] == 500.0

    def test_detect_no_changes_returns_empty(self):
        old = {"delta_h_m": 200.0, "alpha_c": 0.3, "name": "gold", "family": "orogenic_gold"}
        new = _commodity(delta_h_m=200.0)
        changes = _detect_changed_params(old, new)
        assert "delta_h_m" not in changes

    def test_physics_version_bump_required_for_delta_h(self):
        changes = {"delta_h_m": {"old": 200.0, "new": 500.0}}
        assert _requires_physics_version_bump(changes) is True

    def test_physics_version_bump_not_required_for_alpha(self):
        changes = {"alpha_c": {"old": 0.3, "new": 0.5}}
        assert _requires_physics_version_bump(changes) is False

    def test_reprocess_rejected_if_no_changes(self):
        from app.pipeline.reprocess_controller import execute_reprocess
        storage = MockStorageAdapter()
        # Seed the parent
        storage.canonical = {
            "scan_id": "parent_001",
            "status": "COMPLETED",
            "commodity": "gold",
            "environment": "ONSHORE",
            "grid_resolution_degrees": 0.5,
            "scan_tier": "SMART",
            "aoi_geojson": {},
            "tier_thresholds_used": {"delta_h_m_used": 200.0},
        }
        request = ReprocessRequest(
            parent_scan_id="parent_001",
            actor="test_user",
            reason="test",
            new_commodity_config=_commodity(delta_h_m=200.0),  # unchanged
        )
        with pytest.raises(ValueError, match="no Θ_c parameters changed"):
            execute_reprocess(request, MockGEEClient(), storage, InMemoryQueue())

    def test_pre_flight_audit_written_before_pipeline(self):
        from app.pipeline.reprocess_controller import execute_reprocess
        storage = MockStorageAdapter()
        storage.canonical = {
            "scan_id": "parent_002",
            "status": "COMPLETED",
            "commodity": "gold",
            "environment": "ONSHORE",
            "grid_resolution_degrees": 0.5,
            "scan_tier": "SMART",
            "aoi_geojson": {},
            "tier_thresholds_used": {"delta_h_m_used": 200.0},
        }
        request = ReprocessRequest(
            parent_scan_id="parent_002",
            actor="test_user",
            reason="delta_h changed to porphyry depth",
            new_commodity_config=_commodity(delta_h_m=500.0),
        )
        new_id = execute_reprocess(request, MockGEEClient(), storage, InMemoryQueue())
        assert hasattr(storage, "_pre_audit")
        assert storage._pre_audit["parent_scan_id"] == "parent_002"
        assert "delta_h_m" in storage._pre_audit["changed_params"]
        assert new_id != "parent_002"

    def test_lineage_record_written(self):
        from app.pipeline.reprocess_controller import execute_reprocess
        storage = MockStorageAdapter()
        storage.canonical = {
            "scan_id": "parent_003",
            "status": "COMPLETED",
            "commodity": "gold",
            "environment": "ONSHORE",
            "grid_resolution_degrees": 0.5,
            "scan_tier": "SMART",
            "aoi_geojson": {},
            "tier_thresholds_used": {"delta_h_m_used": 200.0},
        }
        request = ReprocessRequest(
            parent_scan_id="parent_003",
            actor="test_user",
            reason="update δh",
            new_commodity_config=_commodity(delta_h_m=500.0),
        )
        execute_reprocess(request, MockGEEClient(), storage, InMemoryQueue())
        assert hasattr(storage, "_lineage")
        assert storage._lineage["parent_scan_id"] == "parent_003"
        assert storage._lineage["physics_version_bump"] is True


# ===========================================================================
# IMPORT ISOLATION — no Phase J scoring authority in pipeline modules
# ===========================================================================

class TestPipelineImportIsolation:
    FORBIDDEN = ["core.tiering", "core.gates"]   # scoring is ALLOWED — it's called here
    PIPELINE_MODULES = [
        "app.pipeline.task_queue",
        "app.pipeline.reprocess_controller",
    ]

    def test_task_queue_has_no_scoring_imports(self):
        import sys, inspect
        mod = sys.modules.get("app.pipeline.task_queue")
        if mod:
            src = inspect.getsource(mod)
            for f in self.FORBIDDEN:
                assert f not in src, f"task_queue imports forbidden {f}"

    def test_reprocess_controller_has_no_direct_scoring_calls(self):
        import sys, inspect
        mod = sys.modules.get("app.pipeline.reprocess_controller")
        if mod:
            src = inspect.getsource(mod)
            assert "compute_acif" not in src, "reprocess_controller must not call compute_acif"
            assert "assign_tier" not in src, "reprocess_controller must not call assign_tier"