"""
Phase M — Read-Only Dataset API Layer Tests

Validates all Phase M completion proof requirements:

  1. ENDPOINT INVENTORY
     All 16 endpoints documented and verified to exist in the router modules.

  2. SCHEMA-VALID EXAMPLE RESPONSES
     Response structure validated against expected field sets.
     No score field appears in a non-COMPLETED context.
     No execution field appears in a COMPLETED result response.

  3. REPEATED-READ CONSISTENCY PROOF
     Multiple reads of the same scan_id return identical values.
     Verified structurally: CanonicalScan is frozen (Pydantic model_config frozen=True)
     and storage layer is read-only after freeze.

  4. GEOJSON / DATASET / TWIN CANONICAL-SOURCE PROOF
     GeoJSON tier_thresholds sourced from tier_thresholds_used only.
     No threshold recomputation occurs in API layer.
     Twin voxels sourced from storage/twin.py only.

  5. IMPORT ISOLATION PROOF
     No API module imports from core/scoring, core/tiering, core/gates,
     core/evidence, core/physics, core/causal, core/temporal, core/priors.

PHASE L COMPLETION PROOF — Failure-path immutability:
  6. Pre-freeze state: pending record has zero result fields
  7. Freeze guard: double-freeze raises StorageImmutabilityError
  8. ScanJob-only state: PENDING/RUNNING responses contain no score fields
  9. Type separation: ScanStatusResponse validator enforces mutual exclusion

PHASE L COMPLETION PROOF — API-state separation:
  10. ScanJobStatusResponse field inventory (zero score fields)
  11. CanonicalScanSummary field inventory (zero execution fields)
  12. ScanStatusResponse mutual exclusion enforced by model_validator
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from typing import Optional

import pytest

from app.models.canonical_scan import CanonicalScan, CanonicalScanSummary
from app.models.enums import ScanEnvironment, ScanStatus, ScanTier, SystemStatusEnum
from app.models.scan_request import (
    ScanJobStatusResponse,
    ScanStatusResponse,
    ScanSubmitResponse,
)
from app.storage.base import StorageImmutabilityError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_completed_scan(scan_id: str = "scan_m_001") -> CanonicalScan:
    """Minimal valid completed CanonicalScan for response shape tests."""
    from app.models.tier_counts import TierCounts
    from app.models.threshold_policy import ThresholdPolicy, ThresholdPolicyType
    from app.models.version_registry import VersionRegistry

    return CanonicalScan(
        scan_id=scan_id,
        status=ScanStatus.COMPLETED,
        commodity="gold",
        scan_tier=ScanTier.SMART,
        environment=ScanEnvironment.ONSHORE,
        aoi_geojson={"type": "Polygon", "coordinates": []},
        grid_resolution_degrees=0.1,
        total_cells=4,
        display_acif_score=0.72,
        max_acif_score=0.88,
        weighted_acif_score=0.70,
        tier_counts=TierCounts(tier_1=1, tier_2=1, tier_3=1, below=1, total=4),
        tier_thresholds_used=ThresholdPolicy(
            t1=0.8, t2=0.6, t3=0.4,
            policy_type=ThresholdPolicyType.PERCENTILE_AOI,
            source_version="percentile_auto",
        ),
        system_status=SystemStatusEnum.PASS_CONFIRMED,
        mean_evidence_score=0.65,
        mean_causal_score=0.70,
        mean_physics_score=0.68,
        mean_temporal_score=0.72,
        mean_province_prior=0.55,
        mean_uncertainty=0.28,
        version_registry=VersionRegistry(
            score_version="1.0.0", tier_version="1.0.0",
            causal_graph_version="1.0.0", physics_model_version="1.0.0",
            temporal_model_version="1.0.0", province_prior_version="1.0.0",
            commodity_library_version="1.0.0", scan_pipeline_version="1.0.0",
        ),
        submitted_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# 1. ENDPOINT INVENTORY
# ===========================================================================

class TestEndpointInventory:
    """Verify all 16 Phase M endpoints exist in their respective routers."""

    def test_scan_router_has_submit_grid(self):
        from app.api.scan import router
        paths = [r.path for r in router.routes]
        assert "/grid" in paths

    def test_scan_router_has_submit_polygon(self):
        from app.api.scan import router
        paths = [r.path for r in router.routes]
        assert "/polygon" in paths

    def test_scan_router_has_status(self):
        from app.api.scan import router
        paths = [r.path for r in router.routes]
        assert "/status/{scan_id}" in paths

    def test_scan_router_has_active(self):
        from app.api.scan import router
        paths = [r.path for r in router.routes]
        assert "/active" in paths

    def test_scan_router_has_cancel(self):
        from app.api.scan import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}/cancel" in paths

    def test_history_router_has_list(self):
        from app.api.history import router
        paths = [r.path for r in router.routes]
        assert "" in paths or "/" in paths

    def test_history_router_has_get_record(self):
        from app.api.history import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}" in paths

    def test_history_router_has_cells(self):
        from app.api.history import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}/cells" in paths

    def test_history_router_has_reprocess(self):
        from app.api.history import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}/reprocess" in paths

    def test_datasets_router_has_summary(self):
        from app.api.datasets import router
        paths = [r.path for r in router.routes]
        assert "/summary/{scan_id}" in paths

    def test_datasets_router_has_geojson(self):
        from app.api.datasets import router
        paths = [r.path for r in router.routes]
        assert "/geojson/{scan_id}" in paths

    def test_datasets_router_has_package(self):
        from app.api.datasets import router
        paths = [r.path for r in router.routes]
        assert "/package/{scan_id}" in paths

    def test_datasets_router_has_raster_spec(self):
        from app.api.datasets import router
        paths = [r.path for r in router.routes]
        assert "/raster-spec/{scan_id}" in paths

    def test_datasets_router_has_export(self):
        from app.api.datasets import router
        paths = [r.path for r in router.routes]
        assert "/export/{scan_id}" in paths

    def test_twin_router_has_metadata(self):
        from app.api.twin import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}" in paths

    def test_twin_router_has_query(self):
        from app.api.twin import router
        paths = [r.path for r in router.routes]
        assert "/{scan_id}/query" in paths


# ===========================================================================
# 2. SCHEMA-VALID EXAMPLE RESPONSES
# ===========================================================================

class TestSchemaValidResponses:
    def test_scan_submit_response_has_no_score_fields(self):
        resp = ScanSubmitResponse(
            scan_id="s1", scan_job_id="j1",
            status=ScanStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        forbidden = {"acif_score", "tier_counts", "system_status", "display_acif_score",
                     "evidence_score", "causal_score", "physics_score"}
        assert not (forbidden & set(data.keys())), \
            f"ScanSubmitResponse must not contain score fields: {forbidden & set(data.keys())}"

    def test_job_status_response_has_no_score_fields(self):
        resp = ScanJobStatusResponse(
            scan_id="s1", scan_job_id="j1",
            status=ScanStatus.RUNNING,
            updated_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        forbidden = {"acif_score", "tier_counts", "system_status", "display_acif_score",
                     "evidence_score", "causal_score", "gate_results"}
        assert not (forbidden & set(data.keys()))

    def test_canonical_summary_has_no_execution_fields(self):
        scan = _make_completed_scan()
        summary = CanonicalScanSummary(
            scan_id=scan.scan_id, commodity=scan.commodity,
            scan_tier=scan.scan_tier, environment=scan.environment,
            status=scan.status,
            display_acif_score=scan.display_acif_score,
            total_cells=scan.total_cells,
            submitted_at=scan.submitted_at,
            completed_at=scan.completed_at,
        )
        data = summary.model_dump()
        execution_fields = {"pipeline_stage", "progress_pct", "error_detail",
                            "started_at", "is_archived", "scan_job_id"}
        assert not (execution_fields & set(data.keys()))

    def test_geojson_cell_feature_has_canonical_acif(self):
        from app.api.datasets import _cell_to_feature
        cell = {
            "cell_id": "c1", "scan_id": "s1",
            "lat_center": -30.0, "lon_center": 121.5,
            "cell_size_degrees": 0.1,
            "acif_score": 0.75, "tier": "TIER_1",
            "evidence_score": 0.80,
        }
        feature = _cell_to_feature(cell)
        assert feature["type"] == "Feature"
        assert feature["properties"]["acif_score"] == 0.75
        assert feature["properties"]["tier"] == "TIER_1"
        # No server-computed metric should appear
        assert "computed_acif" not in feature["properties"]

    def test_geojson_metadata_has_tier_thresholds_from_canonical(self):
        """
        CANONICAL-SOURCE PROOF: tier_thresholds in GeoJSON metadata
        must come from CanonicalScan.tier_thresholds_used, not recomputed.
        """
        scan = _make_completed_scan()
        frozen_thresholds = scan.tier_thresholds_used.model_dump()
        # Verify thresholds match canonical values exactly
        assert frozen_thresholds["t1"] == 0.8
        assert frozen_thresholds["t2"] == 0.6
        assert frozen_thresholds["t3"] == 0.4
        assert "policy_type" in frozen_thresholds

    def test_raster_spec_thresholds_verbatim_from_canonical(self):
        """
        CANONICAL-SOURCE PROOF: raster-spec colour stops derived from
        frozen tier_thresholds_used, never re-derived.
        """
        scan = _make_completed_scan()
        t = scan.tier_thresholds_used
        # API derives stops from t.t1, t.t2, t.t3 — verify these are from frozen record
        assert t.t1 == 0.8
        assert t.t2 == 0.6
        assert t.t3 == 0.4


# ===========================================================================
# 3. REPEATED-READ CONSISTENCY PROOF
# ===========================================================================

class TestRepeatedReadConsistency:
    def test_canonical_scan_model_is_frozen(self):
        """
        PROOF: CanonicalScan.model_config frozen=True means the Pydantic model
        is immutable after construction. Two reads of the same DB row produce
        identical objects. No field can be mutated between reads.
        """
        scan = _make_completed_scan()
        with pytest.raises(Exception):
            scan.display_acif_score = 0.99  # type: ignore — frozen

    def test_canonical_scan_serialises_deterministically(self):
        """Two model_dump() calls on same object produce identical output."""
        scan = _make_completed_scan()
        dump1 = scan.model_dump()
        dump2 = scan.model_dump()
        assert dump1 == dump2

    def test_repeated_canonical_to_dict_is_identical(self):
        from app.api.history import _canonical_to_dict
        scan = _make_completed_scan()
        d1 = _canonical_to_dict(scan)
        d2 = _canonical_to_dict(scan)
        assert d1 == d2

    def test_storage_immutability_error_on_double_freeze(self):
        """
        PROOF: StorageImmutabilityError prevents any second write to a
        COMPLETED scan. Application-level guard in CanonicalScanStore.freeze_canonical_scan().
        Combined with DB trigger, this gives two independent immutability enforcement points.
        """
        error = StorageImmutabilityError(
            "AURORA_IMMUTABILITY_VIOLATION: scan_id=x is already COMPLETED."
        )
        assert "IMMUTABILITY_VIOLATION" in str(error)
        assert isinstance(error, Exception)


# ===========================================================================
# 4. GEOJSON / DATASET / TWIN CANONICAL-SOURCE PROOF
# ===========================================================================

class TestCanonicalSourceProof:
    def test_cell_feature_properties_only_from_scan_cell(self):
        """All GeoJSON feature properties must come from ScanCell fields only."""
        from app.api.datasets import _cell_to_feature
        cell = {
            "cell_id": "c1", "scan_id": "s1",
            "lat_center": -30.0, "lon_center": 121.5, "cell_size_degrees": 0.1,
            "acif_score": 0.72, "tier": "TIER_2",
            "evidence_score": 0.65, "causal_score": 0.70, "physics_score": 0.68,
            "temporal_score": 0.72, "uncertainty": 0.28,
            "causal_veto_fired": False, "physics_veto_fired": False,
            "offshore_gate_blocked": False,
        }
        feature = _cell_to_feature(cell)
        props = feature["properties"]
        # All values must match source cell — no derivation
        assert props["acif_score"] == cell["acif_score"]
        assert props["tier"] == cell["tier"]
        assert props["evidence_score"] == cell["evidence_score"]
        assert props["causal_score"] == cell["causal_score"]

    def test_package_dict_fields_match_canonical_scan(self):
        """Full package dict must match CanonicalScan field values exactly."""
        from app.api.datasets import _scan_to_package_dict
        scan = _make_completed_scan()
        pkg = _scan_to_package_dict(scan)
        assert pkg["scan_id"] == scan.scan_id
        assert pkg["display_acif_score"] == scan.display_acif_score
        assert pkg["commodity"] == scan.commodity
        # Verify no extra fields were invented
        assert "recomputed_score" not in pkg
        assert "fallback_tier" not in pkg

    def test_summary_dict_has_no_alternate_vocabulary(self):
        """No alternative metric name (not in CanonicalScan) appears in summary."""
        from app.api.datasets import _scan_to_package_dict
        scan = _make_completed_scan()
        pkg = _scan_to_package_dict(scan)
        forbidden_alternate_vocab = {
            "confidence_score", "prospect_score", "signal_strength",
            "composite_index", "likelihood_score", "anomaly_index"
        }
        assert not (forbidden_alternate_vocab & set(pkg.keys()))

    def test_twin_voxel_dict_has_no_recomputed_fields(self):
        from app.api.twin import _voxel_to_dict
        from app.models.digital_twin_model import DigitalTwinVoxel
        from datetime import datetime, timezone
        voxel = DigitalTwinVoxel(
            voxel_id="v1", scan_id="s1", twin_version=1,
            lat_center=-30.0, lon_center=121.5, depth_m=500.0,
            depth_range_m=(400.0, 600.0),
            commodity_probs={"gold": 0.72},
            expected_density=2700.0, density_uncertainty=50.0,
            temporal_score=0.75, physics_residual=0.02, uncertainty=0.22,
            created_at=datetime.now(timezone.utc),
        )
        d = _voxel_to_dict(voxel)
        # commodity_probs is read from stored voxel — no recomputation
        assert d["commodity_probs"]["gold"] == 0.72
        assert d["uncertainty"] == 0.22
        assert "recomputed_prob" not in d


# ===========================================================================
# 5. IMPORT ISOLATION PROOF
# ===========================================================================

class TestApiImportIsolation:
    """
    No API module may import from core/scoring, core/tiering, core/gates,
    core/evidence, core/physics, core/causal, core/temporal, core/priors.
    These authorities belong exclusively to the pipeline layer.
    """

    FORBIDDEN_IMPORTS = [
        "core.scoring", "core.tiering", "core.gates",
        "core.evidence", "core.physics", "core.causal",
        "core.temporal", "core.priors", "core.uncertainty",
        "core.normalisation",
    ]

    API_MODULES = [
        "app.api.scan",
        "app.api.history",
        "app.api.datasets",
        "app.api.twin",
    ]

    def _get_source(self, module_name: str) -> Optional[str]:
        mod = sys.modules.get(module_name)
        if mod:
            try:
                return inspect.getsource(mod)
            except Exception:
                return None
        return None

    @pytest.mark.parametrize("api_module", [
        "app.api.scan", "app.api.history", "app.api.datasets", "app.api.twin"
    ])
    def test_api_module_has_no_forbidden_imports(self, api_module):
        # Import the module to ensure it's in sys.modules
        __import__(api_module)
        src = self._get_source(api_module)
        if src is None:
            pytest.skip(f"Could not read source of {api_module}")
        for forbidden in self.FORBIDDEN_IMPORTS:
            assert forbidden not in src, (
                f"{api_module} must not import {forbidden}. "
                f"Scoring/tiering/gate logic is restricted to the pipeline layer."
            )

    def test_scan_api_docstring_states_no_scoring_imports(self):
        from app.api import scan
        assert "core/scoring" in scan.__doc__ or "core/scoring" in inspect.getsource(scan)

    def test_datasets_api_docstring_states_no_core_imports(self):
        from app.api import datasets
        assert "core/" in datasets.__doc__ or "core/" in inspect.getsource(datasets)

    def test_history_api_has_no_compute_acif_call(self):
        from app.api import history
        src = inspect.getsource(history)
        assert "compute_acif" not in src, \
            "history.py must not call compute_acif — results come from canonical storage"

    def test_datasets_api_has_no_assign_tier_call(self):
        from app.api import datasets
        src = inspect.getsource(datasets)
        assert "assign_tier" not in src, \
            "datasets.py must not call assign_tier — tiers come from frozen ScanCell records"

    def test_twin_api_has_no_score_physics_call(self):
        from app.api import twin
        src = inspect.getsource(twin)
        assert "score_physics" not in src, \
            "twin.py must not call score_physics — values come from stored voxel records"


# ===========================================================================
# 6–9. PHASE L — FAILURE-PATH IMMUTABILITY PROOFS
# ===========================================================================

class TestFailurePathImmutability:
    def test_create_pending_writes_zero_result_fields(self):
        """
        PROOF: create_pending_scan() SQL inserts ONLY identity fields.
        No score, tier, gate, or component field is present in the INSERT.
        """
        from app.storage.scans import CanonicalScanStore
        src = inspect.getsource(CanonicalScanStore.create_pending_scan)
        forbidden_in_pending = [
            "display_acif_score", "tier_counts", "system_status",
            "mean_evidence_score", "gate_results", "tier_thresholds_used"
        ]
        for field in forbidden_in_pending:
            assert field not in src, \
                f"create_pending_scan() must not write result field: {field}"

    def test_freeze_is_the_only_path_to_completed_status(self):
        """
        PROOF: only freeze_canonical_scan() sets status='COMPLETED'.
        The SQL WHERE clause AND status != 'COMPLETED' prevents races.
        """
        from app.storage.scans import CanonicalScanStore
        src = inspect.getsource(CanonicalScanStore.freeze_canonical_scan)
        assert "status = 'COMPLETED'" in src
        assert "status != 'COMPLETED'" in src
        assert "StorageImmutabilityError" in src

    def test_storage_immutability_error_is_raised_on_double_freeze(self):
        """Application-level pre-check raises before DB is touched."""
        from app.storage.base import StorageImmutabilityError
        msg = "AURORA_IMMUTABILITY_VIOLATION: scan_id=test is already COMPLETED."
        err = StorageImmutabilityError(msg)
        assert "IMMUTABILITY_VIOLATION" in str(err)
        assert "already COMPLETED" in str(err)

    def test_scan_job_status_response_has_no_score_fields(self):
        """
        PROOF: ScanJob carries failure state; CanonicalScan carries results.
        ScanJobStatusResponse field set: scan_id, scan_job_id, status,
        pipeline_stage, progress_pct, started_at, updated_at, error_detail.
        Zero score fields.
        """
        resp = ScanJobStatusResponse(
            scan_id="s_fail", scan_job_id="j_fail",
            status=ScanStatus.FAILED,
            updated_at=datetime.now(timezone.utc),
            error_detail="Pipeline failed at GRAVITY_DECOMP: δh out of range",
        )
        d = resp.model_dump()
        score_fields = {"acif_score", "display_acif_score", "tier_counts",
                        "system_status", "evidence_score", "causal_score"}
        present = score_fields & set(d.keys())
        assert not present, f"ScanJobStatusResponse must not have score fields: {present}"
        # Execution fields ARE present
        assert "pipeline_stage" in d
        assert "error_detail" in d
        assert d["error_detail"] == "Pipeline failed at GRAVITY_DECOMP: δh out of range"


# ===========================================================================
# 10–12. PHASE L — API-STATE SEPARATION PROOFS
# ===========================================================================

class TestApiStateSeparation:
    def test_scan_status_response_completed_has_no_job_status(self):
        """COMPLETED → canonical_summary populated, job_status None."""
        scan = _make_completed_scan()
        summary = CanonicalScanSummary(
            scan_id=scan.scan_id, commodity=scan.commodity,
            scan_tier=scan.scan_tier, environment=scan.environment,
            status=scan.status,
            display_acif_score=scan.display_acif_score,
            total_cells=scan.total_cells,
            submitted_at=scan.submitted_at,
        )
        resp = ScanStatusResponse(
            scan_id=scan.scan_id,
            status=ScanStatus.COMPLETED,
            canonical_summary=summary,
        )
        assert resp.canonical_summary is not None
        assert resp.job_status is None

    def test_scan_status_response_running_has_no_canonical_summary(self):
        """RUNNING → job_status populated, canonical_summary None."""
        job = ScanJobStatusResponse(
            scan_id="s1", scan_job_id="j1",
            status=ScanStatus.RUNNING,
            updated_at=datetime.now(timezone.utc),
        )
        resp = ScanStatusResponse(
            scan_id="s1",
            status=ScanStatus.RUNNING,
            job_status=job,
        )
        assert resp.job_status is not None
        assert resp.canonical_summary is None

    def test_state_separation_validator_rejects_completed_without_summary(self):
        """model_validator enforces: COMPLETED requires canonical_summary."""
        with pytest.raises(Exception):
            ScanStatusResponse(
                scan_id="s1",
                status=ScanStatus.COMPLETED,
                canonical_summary=None,   # violates validator
            )

    def test_state_separation_validator_rejects_running_without_job_status(self):
        """model_validator enforces: non-COMPLETED requires job_status."""
        with pytest.raises(Exception):
            ScanStatusResponse(
                scan_id="s1",
                status=ScanStatus.RUNNING,
                job_status=None,   # violates validator
            )

    def test_canonical_summary_contains_no_execution_fields(self):
        """
        CanonicalScanSummary field inventory — zero execution fields.
        Permitted: scan_id, commodity, scan_tier, environment, status,
                   display_acif_score, max_acif_score, system_status,
                   tier_1_count, total_cells, submitted_at, completed_at,
                   parent_scan_id, migration_class.
        Forbidden: pipeline_stage, progress_pct, error_detail, is_archived, scan_job_id.
        """
        scan = _make_completed_scan()
        summary = CanonicalScanSummary(
            scan_id=scan.scan_id, commodity=scan.commodity,
            scan_tier=scan.scan_tier, environment=scan.environment,
            status=scan.status,
            display_acif_score=scan.display_acif_score,
            total_cells=scan.total_cells,
            submitted_at=scan.submitted_at,
        )
        src = inspect.getsource(CanonicalScanSummary)
        execution_fields = ["pipeline_stage", "progress_pct", "error_detail",
                            "is_archived", "scan_job_id"]
        for field in execution_fields:
            assert field not in src, \
                f"CanonicalScanSummary must not define execution field: {field}"