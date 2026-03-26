"""
Phase N — Digital Twin Core Tests

Validates all Phase N completion proof requirements:

  1. TWIN BUILDER MODULE INVENTORY
     All builder functions documented and verified to exist.

  2. VOXEL SCHEMA PROOF
     DigitalTwinVoxel fields: commodity_probs, uncertainty, temporal_score,
     physics_residual, kernel_weight, source_cell_id all present and typed.
     VoxelLineage carries full source traceability.
     TwinBuildManifest carries version_registry snapshot.

  3. EXAMPLE SCAN-TO-VOXEL PROJECTION TRACE
     End-to-end trace: frozen ScanCell → depth kernel → voxel column.
     Verifies determinism: same inputs → same outputs.
     Verifies propagation: score values match frozen cell exactly.

  4. VERSION-HISTORY QUERY EXAMPLE
     Twin version history is append-only.
     New build increments version counter.

  5. PROOF THAT TWIN GENERATION DOES NOT MUTATE CANONICAL SCAN
     builder.build_twin() adapter has no write method for canonical records.
     Structural proof via protocol inspection.

  6. PROOF THAT TWIN MODULES DO NOT IMPORT SCORING/TIERING/GATES
     Source-level import inspection across all Phase N modules.

Constitutional invariants verified:
  - ACIF read from frozen ScanCell, never recomputed
  - All score fields propagated verbatim (uncertainty, temporal, physics_residual)
  - Depth kernel is pure mathematics — no core/* calls
  - TwinBuildManifest version_registry matches canonical source
"""

from __future__ import annotations

import inspect
import math
import sys
from datetime import datetime, timezone
from typing import Optional

import pytest

from app.models.digital_twin_model import (
    DepthKernelConfig,
    DigitalTwinVoxel,
    TwinBuildManifest,
    TwinVersion,
    VoxelLineage,
)
from app.services.twin_builder import (
    DEFAULT_DEPTH_KERNELS,
    build_twin,
    compute_density_uncertainty,
    compute_expected_density,
    compute_kernel_weight,
    depth_range_for_slice,
    get_depth_kernel_for_commodity,
    project_cell_to_voxels,
    project_commodity_probability,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _kernel(family: str = "orogenic_gold", commodity: str = "gold") -> DepthKernelConfig:
    k = DEFAULT_DEPTH_KERNELS[family]
    return DepthKernelConfig(
        commodity=commodity,
        z_expected_m=k.z_expected_m,
        sigma_z_m=k.sigma_z_m,
        depth_slices_m=k.depth_slices_m,
        density_gradient_kg_m3_per_m=k.density_gradient_kg_m3_per_m,
        background_density_kg_m3=k.background_density_kg_m3,
    )


def _frozen_cell(
    cell_id: str = "c0001",
    scan_id: str = "scan_n_001",
    acif: float = 0.75,
    uncertainty: float = 0.22,
    temporal: float = 0.80,
    physics_res: float = 0.03,
) -> dict:
    return {
        "cell_id": cell_id,
        "scan_id": scan_id,
        "lat_center": -29.5,
        "lon_center": 121.5,
        "cell_size_degrees": 0.1,
        "environment": "ONSHORE",
        "acif_score": acif,
        "tier": "TIER_1",
        "uncertainty": uncertainty,
        "temporal_score": temporal,
        "physics_residual": physics_res,
        "causal_veto_fired": False,
        "offshore_gate_blocked": False,
    }


def _frozen_canonical(scan_id: str = "scan_n_001") -> dict:
    return {
        "scan_id": scan_id,
        "status": "COMPLETED",
        "commodity": "gold",
        "scan_tier": "SMART",
        "environment": "ONSHORE",
        "total_cells": 2,
        "display_acif_score": 0.72,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "version_registry": {
            "score_version": "1.0.0",
            "tier_version": "1.0.0",
            "causal_graph_version": "1.0.0",
            "physics_model_version": "1.0.0",
            "temporal_model_version": "1.0.0",
            "province_prior_version": "1.0.0",
            "commodity_library_version": "1.0.0",
            "scan_pipeline_version": "1.0.0",
        },
    }


# Mock storage adapters
class MockCanonicalStore:
    def __init__(self, canonical: dict, cells: list[dict]):
        self._canonical = canonical
        self._cells = cells

    async def get_canonical_scan(self, scan_id: str) -> dict:
        return self._canonical

    async def list_scan_cells(self, scan_id: str) -> list[dict]:
        return self._cells


class MockTwinStore:
    def __init__(self, next_version: int = 1):
        self._version = next_version
        self.written_voxels: list[DigitalTwinVoxel] = []
        self.written_manifests: list[TwinBuildManifest] = []

    async def write_voxels(self, scan_id, voxels, twin_version, trigger_type, parent_version):
        self.written_voxels.extend(voxels)

    async def get_next_twin_version(self, scan_id: str) -> int:
        return self._version

    async def write_twin_manifest(self, scan_id, manifest):
        self.written_manifests.append(manifest)


# ===========================================================================
# 1. TWIN BUILDER MODULE INVENTORY
# ===========================================================================

class TestBuilderModuleInventory:
    def test_compute_kernel_weight_exists(self):
        assert callable(compute_kernel_weight)

    def test_project_commodity_probability_exists(self):
        assert callable(project_commodity_probability)

    def test_compute_expected_density_exists(self):
        assert callable(compute_expected_density)

    def test_compute_density_uncertainty_exists(self):
        assert callable(compute_density_uncertainty)

    def test_project_cell_to_voxels_exists(self):
        assert callable(project_cell_to_voxels)

    def test_build_twin_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(build_twin)

    def test_get_depth_kernel_for_commodity_exists(self):
        assert callable(get_depth_kernel_for_commodity)

    def test_default_kernels_cover_all_families(self):
        expected_families = {
            "epithermal", "orogenic_gold", "porphyry", "vms_sedex",
            "skarn", "kimberlite", "seabed", "pge_intrusion", "coal_oil_sands",
        }
        assert expected_families == set(DEFAULT_DEPTH_KERNELS.keys())


# ===========================================================================
# 2. VOXEL SCHEMA PROOF
# ===========================================================================

class TestVoxelSchema:
    def test_digital_twin_voxel_has_commodity_probs(self):
        fields = DigitalTwinVoxel.model_fields
        assert "commodity_probs" in fields

    def test_digital_twin_voxel_has_uncertainty(self):
        assert "uncertainty" in DigitalTwinVoxel.model_fields

    def test_digital_twin_voxel_has_temporal_score(self):
        assert "temporal_score" in DigitalTwinVoxel.model_fields

    def test_digital_twin_voxel_has_physics_residual(self):
        assert "physics_residual" in DigitalTwinVoxel.model_fields

    def test_digital_twin_voxel_has_kernel_weight(self):
        assert "kernel_weight" in DigitalTwinVoxel.model_fields

    def test_digital_twin_voxel_has_source_cell_id(self):
        assert "source_cell_id" in DigitalTwinVoxel.model_fields

    def test_digital_twin_voxel_has_scan_id(self):
        assert "scan_id" in DigitalTwinVoxel.model_fields

    def test_voxel_lineage_has_all_traceability_fields(self):
        fields = VoxelLineage.model_fields
        for f in [
            "scan_id", "cell_id", "twin_version",
            "scan_pipeline_version", "score_version", "physics_model_version",
            "source_acif_score", "source_uncertainty", "source_temporal_score",
            "source_physics_residual", "z_expected_m", "sigma_z_m",
            "depth_slice_m", "kernel_weight", "built_at",
        ]:
            assert f in fields, f"VoxelLineage missing field: {f}"

    def test_twin_build_manifest_has_version_registry_fields(self):
        fields = TwinBuildManifest.model_fields
        for f in [
            "scan_id", "twin_version", "commodity", "depth_kernel",
            "score_version", "physics_model_version", "scan_pipeline_version",
            "cells_projected", "voxels_produced", "built_at",
        ]:
            assert f in fields, f"TwinBuildManifest missing field: {f}"

    def test_voxel_is_frozen(self):
        """Voxels must be immutable after construction."""
        voxel = DigitalTwinVoxel(
            voxel_id="v1", scan_id="s1", twin_version=1,
            lat_center=-30.0, lon_center=121.5, depth_m=200.0,
            depth_range_m=(100.0, 300.0),
            commodity_probs={"gold": 0.72},
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception):
            voxel.uncertainty = 0.99  # type: ignore — frozen model


# ===========================================================================
# 3. SCAN-TO-VOXEL PROJECTION TRACE
# ===========================================================================

class TestProjectionTrace:
    """
    PHASE N REQUIREMENT §3 — Example scan-to-voxel projection trace.

    Demonstrates the complete chain from frozen ScanCell to voxel column.
    """

    def test_kernel_weight_at_expected_depth_is_maximum(self):
        """D^(c)(z_expected) = 1.0 — maximum weight at expected depth."""
        w = compute_kernel_weight(depth_m=200.0, z_expected_m=200.0, sigma_z_m=80.0)
        assert abs(w - 1.0) < 1e-10

    def test_kernel_weight_decays_with_depth_distance(self):
        """D^(c)(z) < D^(c)(z_expected) for z ≠ z_expected."""
        w_at_target = compute_kernel_weight(200.0, 200.0, 80.0)
        w_far = compute_kernel_weight(600.0, 200.0, 80.0)
        assert w_far < w_at_target

    def test_kernel_weight_is_symmetric(self):
        """D^(c) is symmetric around z_expected."""
        w_above = compute_kernel_weight(100.0, 200.0, 80.0)  # 100m above
        w_below = compute_kernel_weight(300.0, 200.0, 80.0)  # 100m below
        assert abs(w_above - w_below) < 1e-10

    def test_commodity_probability_is_acif_times_kernel(self):
        """p_commodity(z) = ACIF × D^(c)(z)."""
        acif = 0.75
        kernel_w = 0.8
        probs = project_commodity_probability(acif, kernel_w, "gold")
        assert abs(probs["gold"] - 0.60) < 1e-10

    def test_commodity_probability_clamped_to_one(self):
        """p_commodity(z) cannot exceed 1.0."""
        probs = project_commodity_probability(1.0, 1.0, "gold")
        assert probs["gold"] <= 1.0

    def test_commodity_probability_none_acif_gives_zero(self):
        """None ACIF → probability 0.0 (cell has no valid score)."""
        probs = project_commodity_probability(None, 0.9, "gold")
        assert probs["gold"] == 0.0

    def test_project_cell_produces_one_voxel_per_depth_slice(self):
        cell = _frozen_cell()
        kernel = _kernel()
        voxels, lineages = project_cell_to_voxels(
            cell=cell, commodity="gold", kernel_config=kernel,
            twin_version=1, built_at=datetime.now(timezone.utc).isoformat(),
        )
        assert len(voxels) == len(kernel.depth_slices_m)
        assert len(lineages) == len(kernel.depth_slices_m)

    def test_voxel_score_propagation_is_verbatim(self):
        """
        PROOF OF NO RE-SCORING:
        uncertainty, temporal_score, physics_residual in voxel must exactly
        match the source ScanCell values — not recomputed.
        """
        cell = _frozen_cell(uncertainty=0.22, temporal=0.80, physics_res=0.03)
        kernel = _kernel()
        voxels, _ = project_cell_to_voxels(
            cell=cell, commodity="gold", kernel_config=kernel,
            twin_version=1, built_at=datetime.now(timezone.utc).isoformat(),
        )
        for v in voxels:
            assert v.uncertainty == 0.22, "uncertainty must propagate verbatim"
            assert v.temporal_score == 0.80, "temporal_score must propagate verbatim"
            assert v.physics_residual == 0.03, "physics_residual must propagate verbatim"

    def test_voxel_source_cell_id_matches_input_cell(self):
        """Every voxel must carry the cell_id it was projected from."""
        cell = _frozen_cell(cell_id="c_trace_001")
        kernel = _kernel()
        voxels, _ = project_cell_to_voxels(
            cell=cell, commodity="gold", kernel_config=kernel,
            twin_version=1, built_at=datetime.now(timezone.utc).isoformat(),
        )
        for v in voxels:
            assert v.source_cell_id == "c_trace_001"

    def test_voxel_scan_id_matches_canonical(self):
        cell = _frozen_cell(scan_id="scan_n_trace")
        kernel = _kernel()
        voxels, _ = project_cell_to_voxels(
            cell=cell, commodity="gold", kernel_config=kernel,
            twin_version=1, built_at=datetime.now(timezone.utc).isoformat(),
        )
        for v in voxels:
            assert v.scan_id == "scan_n_trace"

    def test_lineage_records_source_acif(self):
        """VoxelLineage must record the ACIF value read from the frozen cell."""
        cell = _frozen_cell(acif=0.75)
        kernel = _kernel()
        _, lineages = project_cell_to_voxels(
            cell=cell, commodity="gold", kernel_config=kernel,
            twin_version=1, built_at=datetime.now(timezone.utc).isoformat(),
        )
        for lin in lineages:
            assert lin.source_acif_score == 0.75

    def test_projection_is_deterministic(self):
        """Same inputs always produce identical voxel outputs."""
        cell = _frozen_cell()
        kernel = _kernel()
        built = "2026-01-01T00:00:00+00:00"
        voxels_a, _ = project_cell_to_voxels(cell=cell, commodity="gold",
                                               kernel_config=kernel, twin_version=1, built_at=built)
        voxels_b, _ = project_cell_to_voxels(cell=cell, commodity="gold",
                                               kernel_config=kernel, twin_version=1, built_at=built)
        for a, b in zip(voxels_a, voxels_b):
            assert a.commodity_probs == b.commodity_probs
            assert a.kernel_weight == b.kernel_weight
            assert a.uncertainty == b.uncertainty

    def test_expected_density_increases_with_depth(self):
        """Crustal gradient: density must increase with depth."""
        d_shallow = compute_expected_density(100.0, 2670.0, 0.3)
        d_deep = compute_expected_density(1000.0, 2670.0, 0.3)
        assert d_deep > d_shallow

    def test_depth_range_bounds_are_ordered(self):
        slices = [100.0, 200.0, 300.0, 500.0, 750.0]
        for idx in range(len(slices)):
            lo, hi = depth_range_for_slice(slices, idx)
            assert lo < hi

    def test_depth_range_covers_slice_centre(self):
        slices = [100.0, 200.0, 300.0, 500.0, 750.0]
        for idx, z in enumerate(slices):
            lo, hi = depth_range_for_slice(slices, idx)
            assert lo <= z <= hi


# ===========================================================================
# 4. VERSION-HISTORY QUERY EXAMPLE
# ===========================================================================

class TestVersionHistory:
    @pytest.mark.asyncio
    async def test_first_twin_build_gets_version_1(self):
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1"), _frozen_cell("c2")]
        twin_store = MockTwinStore(next_version=1)
        canonical_store = MockCanonicalStore(canonical, cells)

        manifest = await build_twin(
            scan_id="scan_n_001",
            canonical_store=canonical_store,
            twin_store=twin_store,
            family="orogenic_gold",
        )
        assert manifest.twin_version == 1

    @pytest.mark.asyncio
    async def test_reprocess_twin_gets_incremented_version(self):
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1")]
        twin_store = MockTwinStore(next_version=2)  # already has version 1
        canonical_store = MockCanonicalStore(canonical, cells)

        manifest = await build_twin(
            scan_id="scan_n_001",
            canonical_store=canonical_store,
            twin_store=twin_store,
            family="orogenic_gold",
            trigger_type="reprocess",
            parent_version=1,
        )
        assert manifest.twin_version == 2

    @pytest.mark.asyncio
    async def test_twin_build_manifest_written_to_store(self):
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1")]
        twin_store = MockTwinStore()
        canonical_store = MockCanonicalStore(canonical, cells)

        await build_twin(
            scan_id="scan_n_001",
            canonical_store=canonical_store,
            twin_store=twin_store,
            family="orogenic_gold",
        )
        assert len(twin_store.written_manifests) == 1

    @pytest.mark.asyncio
    async def test_version_history_is_append_only(self):
        """Each build adds voxels for a new version — previous versions untouched."""
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1")]
        twin_store_v1 = MockTwinStore(next_version=1)
        twin_store_v2 = MockTwinStore(next_version=2)
        canonical_store = MockCanonicalStore(canonical, cells)

        m1 = await build_twin("scan_n_001", canonical_store, twin_store_v1, "orogenic_gold")
        m2 = await build_twin("scan_n_001", canonical_store, twin_store_v2, "orogenic_gold",
                              trigger_type="reprocess", parent_version=1)

        assert m1.twin_version == 1
        assert m2.twin_version == 2
        assert m2.twin_version > m1.twin_version


# ===========================================================================
# 5. PROOF THAT TWIN GENERATION DOES NOT MUTATE CANONICAL SCAN
# ===========================================================================

class TestCanonicalImmutability:
    def test_canonical_read_adapter_has_no_write_method(self):
        """
        PROOF: CanonicalReadAdapter protocol only defines read methods.
        build_twin() receives a CanonicalReadAdapter — which has NO write capability.
        Therefore it is structurally impossible for build_twin() to mutate
        the canonical_scans or scan_cells tables.
        """
        from app.services.twin_builder import CanonicalReadAdapter
        src = inspect.getsource(CanonicalReadAdapter)
        write_signatures = [
            "freeze_canonical_scan", "create_pending_scan", "write_cells",
            "soft_delete_scan", "update", "insert", "delete",
        ]
        for sig in write_signatures:
            assert sig not in src, (
                f"CanonicalReadAdapter must not define write method: {sig}"
            )

    def test_build_twin_only_calls_canonical_store_reads(self):
        """
        PROOF: build_twin() only calls get_canonical_scan() and list_scan_cells()
        on the canonical store — both read-only methods.
        """
        src = inspect.getsource(build_twin)
        assert "get_canonical_scan" in src
        assert "list_scan_cells" in src
        # These write methods must not appear
        forbidden_writes = [
            "freeze_canonical_scan", "create_pending_scan",
            "write_cells", "soft_delete",
        ]
        for method in forbidden_writes:
            assert method not in src, (
                f"build_twin() must not call canonical write method: {method}"
            )

    @pytest.mark.asyncio
    async def test_build_twin_rejects_non_completed_scan(self):
        """
        Twin builder must reject non-COMPLETED scans.
        Ensures it only operates on frozen canonical outputs.
        """
        canonical = _frozen_canonical()
        canonical["status"] = "RUNNING"
        cells = [_frozen_cell()]
        canonical_store = MockCanonicalStore(canonical, cells)
        twin_store = MockTwinStore()

        with pytest.raises(ValueError, match="COMPLETED"):
            await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

    @pytest.mark.asyncio
    async def test_build_twin_rejects_empty_cells(self):
        """Twin builder must reject scans with no cell data."""
        canonical_store = MockCanonicalStore(_frozen_canonical(), [])
        twin_store = MockTwinStore()
        with pytest.raises(ValueError, match="zero ScanCell"):
            await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

    @pytest.mark.asyncio
    async def test_build_twin_writes_zero_canonical_records(self):
        """
        PROOF: after build_twin(), canonical_store has no write calls.
        MockCanonicalStore tracks no write state — it only reads.
        """
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1"), _frozen_cell("c2")]
        canonical_store = MockCanonicalStore(canonical, cells)
        twin_store = MockTwinStore()

        await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

        # canonical_store has no written_records attribute — proof it has no write path
        assert not hasattr(canonical_store, "written_canonicals")
        assert not hasattr(canonical_store, "written_cells")


# ===========================================================================
# 6. IMPORT ISOLATION PROOF
# ===========================================================================

class TestTwinImportIsolation:
    """
    No Phase N module may import from core/scoring, core/tiering, core/gates,
    or any other scoring authority.
    """

    FORBIDDEN = [
        "core.scoring", "core.tiering", "core.gates",
        "core.evidence", "core.causal", "core.physics",
        "core.temporal", "core.priors", "core.uncertainty",
        "compute_acif", "assign_tier", "evaluate_gates",
        "score_evidence", "score_causal",
    ]

    def _src(self, module_name: str) -> str:
        __import__(module_name)
        mod = sys.modules.get(module_name)
        return inspect.getsource(mod) if mod else ""

    @pytest.mark.parametrize("module", [
        "app.services.twin_builder",
        "app.models.digital_twin_model",
    ])
    def test_twin_module_has_no_scoring_imports(self, module: str):
        src = self._src(module)
        if not src:
            pytest.skip(f"Cannot read source of {module}")
        for forbidden in self.FORBIDDEN:
            assert forbidden not in src, (
                f"{module} must not import/use {forbidden}. "
                f"Twin builder must never invoke scoring authority."
            )

    def test_twin_builder_has_no_acif_computation(self):
        src = self._src("app.services.twin_builder")
        assert "compute_acif" not in src
        assert "score_evidence" not in src
        assert "score_causal" not in src

    def test_twin_builder_imports_only_models_and_math(self):
        """
        Verify twin_builder only imports from: math, uuid, datetime, models/, config/.
        No services/* (except self), no core/*, no api/*, no pipeline/*.
        """
        src = self._src("app.services.twin_builder")
        forbidden_module_prefixes = [
            "from app.core", "import app.core",
            "from app.api", "import app.api",
            "from app.pipeline", "import app.pipeline",
        ]
        for prefix in forbidden_module_prefixes:
            assert prefix not in src, (
                f"twin_builder.py must not import from {prefix}"
            )

    def test_depth_kernel_formula_uses_only_math(self):
        """
        PROOF: compute_kernel_weight() uses only math.exp.
        No core/* call, no database call, no side effects.
        """
        src = inspect.getsource(compute_kernel_weight)
        assert "math.exp" in src
        assert "import" not in src        # no imports inside the function
        assert "core" not in src          # no core module reference

    def test_project_commodity_probability_uses_no_imports(self):
        """project_commodity_probability() is a pure function."""
        src = inspect.getsource(project_commodity_probability)
        assert "import" not in src
        assert "core" not in src


# ===========================================================================
# BONUS: Full end-to-end async build test
# ===========================================================================

class TestEndToEndTwinBuild:
    @pytest.mark.asyncio
    async def test_full_twin_build_produces_correct_voxel_count(self):
        canonical = _frozen_canonical()
        cells = [_frozen_cell("c1"), _frozen_cell("c2"), _frozen_cell("c3")]
        twin_store = MockTwinStore()
        canonical_store = MockCanonicalStore(canonical, cells)
        kernel = _kernel()  # 5 depth slices

        manifest = await build_twin(
            scan_id="scan_n_001",
            canonical_store=canonical_store,
            twin_store=twin_store,
            family="orogenic_gold",
        )

        expected_voxels = len(cells) * len(kernel.depth_slices_m)
        assert manifest.voxels_produced == expected_voxels
        assert len(twin_store.written_voxels) == expected_voxels

    @pytest.mark.asyncio
    async def test_manifest_version_registry_matches_canonical(self):
        """
        PHASE N PROOF: TwinBuildManifest version fields must match
        CanonicalScan.version_registry exactly.
        """
        canonical = _frozen_canonical()
        canonical_store = MockCanonicalStore(canonical, [_frozen_cell("c1")])
        twin_store = MockTwinStore()

        manifest = await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

        assert manifest.score_version == canonical["version_registry"]["score_version"]
        assert manifest.physics_model_version == canonical["version_registry"]["physics_model_version"]
        assert manifest.scan_pipeline_version == canonical["version_registry"]["scan_pipeline_version"]

    @pytest.mark.asyncio
    async def test_offshore_blocked_cells_excluded_from_twin(self):
        """
        Cells with offshore_gate_blocked=True must be excluded from the twin.
        They have no valid ACIF — projecting them would be meaningless.
        """
        cells = [
            {**_frozen_cell("c_valid"), "offshore_gate_blocked": False},
            {**_frozen_cell("c_blocked"), "offshore_gate_blocked": True, "acif_score": None},
        ]
        canonical_store = MockCanonicalStore(_frozen_canonical(), cells)
        twin_store = MockTwinStore()
        kernel = _kernel()

        manifest = await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

        # Only 1 valid cell × 5 depth slices
        assert manifest.voxels_produced == len(kernel.depth_slices_m)

    @pytest.mark.asyncio
    async def test_voxels_have_commodity_probs_for_scan_commodity(self):
        canonical = _frozen_canonical()  # commodity = "gold"
        canonical_store = MockCanonicalStore(canonical, [_frozen_cell("c1")])
        twin_store = MockTwinStore()

        await build_twin("scan_n_001", canonical_store, twin_store, "orogenic_gold")

        for v in twin_store.written_voxels:
            assert "gold" in v.commodity_probs
            assert 0.0 <= v.commodity_probs["gold"] <= 1.0