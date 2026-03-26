"""
Phase F — Core Data Model Tests

Validates:
  - All model types instantiate correctly with valid data
  - Validation constraints are enforced
  - ScanJob and CanonicalScan are provably separate types with no score field overlap
  - Constitutional invariants (tier sum, threshold ordering, observable bounds, etc.)
  - Models have zero imports from core/, services/, storage/, api/, or pipeline/
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from typing import Any

import pytest

from app.models.canonical_scan import CanonicalScan, CanonicalScanSummary
from app.models.digital_twin_model import (
    DigitalTwinVoxel,
    TwinQuery,
    TwinQueryResult,
    TwinVersion,
)
from app.models.enums import (
    PipelineStageEnum,
    RoleEnum,
    ScanEnvironment,
    ScanStatus,
    ScanTier,
    SystemStatusEnum,
    ThresholdSourceEnum,
    TierLabel,
)
from app.models.gate_results import (
    ConfirmationReason,
    GateResult,
    GateResults,
    SystemStatus,
)
from app.models.observable_vector import ObservableVector
from app.models.scan_cell import ScanCell
from app.models.scan_job import ScanJob
from app.models.scan_request import (
    ScanGrid,
    ScanJobStatusResponse,
    ScanPolygon,
    ScanRequest,
    ScanStatusResponse,
    ScanSubmitResponse,
)
from app.models.threshold_policy import ThresholdPolicy, ThresholdSet
from app.models.tier_counts import TierCounts
from app.models.version_registry import VersionRegistry

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_version_registry() -> VersionRegistry:
    return VersionRegistry(
        score_version="0.1.0",
        tier_version="0.1.0",
        causal_graph_version="0.1.0",
        physics_model_version="0.1.0",
        temporal_model_version="0.1.0",
        province_prior_version="0.1.0",
        commodity_library_version="0.1.0",
        scan_pipeline_version="0.1.0",
    )

def make_threshold_set() -> ThresholdSet:
    return ThresholdSet(t1=0.75, t2=0.50, t3=0.25)

def make_threshold_policy(commodity: str = "gold") -> ThresholdPolicy:
    return ThresholdPolicy(
        thresholds=make_threshold_set(),
        source=ThresholdSourceEnum.COMMODITY_FROZEN_DEFAULT,
        commodity=commodity,
        source_version="0.1.0",
    )

def make_tier_counts(tier_1=5, tier_2=10, tier_3=15, below=20) -> TierCounts:
    return TierCounts(
        tier_1=tier_1, tier_2=tier_2, tier_3=tier_3, below=below,
        total_cells=tier_1 + tier_2 + tier_3 + below,
    )

def make_gate_results(passed=3, total=4) -> GateResults:
    gates = [
        GateResult(gate_id=f"gate_{i}", gate_name=f"Gate {i}", passed=(i < passed))
        for i in range(total)
    ]
    return GateResults(gates=gates, gates_passed=passed, gates_total=total)

def make_confirmation_reason() -> ConfirmationReason:
    return ConfirmationReason(
        gate_ratio=0.75,
        supporting_gates=["gate_0", "gate_1", "gate_2"],
        blocking_gates=["gate_3"],
    )

def make_completed_canonical_scan() -> CanonicalScan:
    return CanonicalScan(
        scan_id="scan_001",
        status=ScanStatus.COMPLETED,
        commodity="gold",
        scan_tier=ScanTier.SMART,
        environment=ScanEnvironment.ONSHORE,
        aoi_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        grid_resolution_degrees=0.01,
        total_cells=50,
        display_acif_score=0.62,
        max_acif_score=0.89,
        weighted_acif_score=0.65,
        tier_counts=make_tier_counts(),
        tier_thresholds_used=make_threshold_policy(),
        system_status=SystemStatusEnum.PASS_CONFIRMED,
        gate_results=make_gate_results(),
        confirmation_reason=make_confirmation_reason(),
        version_registry=make_version_registry(),
        submitted_at=NOW,
        completed_at=NOW,
    )


# ---------------------------------------------------------------------------
# F.1 — Enumeration types
# ---------------------------------------------------------------------------

class TestEnums:
    def test_scan_status_values(self):
        assert ScanStatus.COMPLETED == "COMPLETED"
        assert ScanStatus.MIGRATION_STUB == "MIGRATION_STUB"

    def test_tier_label_values(self):
        assert TierLabel.TIER_1 == "TIER_1"
        assert TierLabel.BELOW == "BELOW"

    def test_system_status_values(self):
        assert SystemStatusEnum.PASS_CONFIRMED == "PASS_CONFIRMED"
        assert SystemStatusEnum.REJECTED == "REJECTED"

    def test_threshold_source_all_four_exist(self):
        sources = {s.value for s in ThresholdSourceEnum}
        assert "aoi_percentile" in sources
        assert "commodity_frozen_default" in sources
        assert "ground_truth_calibrated" in sources
        assert "reprocessed_vX" in sources

    def test_pipeline_stages_include_freeze(self):
        stage_values = {s.value for s in PipelineStageEnum}
        assert "CANONICAL_FREEZE" in stage_values

    def test_role_enum_three_levels(self):
        roles = {r.value for r in RoleEnum}
        assert roles == {"admin", "operator", "viewer"}


# ---------------------------------------------------------------------------
# F.2 — ObservableVector
# ---------------------------------------------------------------------------

class TestObservableVector:
    def test_empty_vector_instantiates(self):
        """All 42 fields default to None — valid missing-sensor state."""
        v = ObservableVector()
        assert v.missing_count() == 42
        assert v.present_count() == 0
        assert v.coverage_fraction() == 0.0

    def test_partial_vector(self):
        v = ObservableVector(x_spec_1=0.5, x_spec_2=0.8, x_grav_1=0.3)
        assert v.present_count() == 3
        assert v.missing_count() == 39

    def test_out_of_bounds_rejects(self):
        with pytest.raises(Exception):
            ObservableVector(x_spec_1=1.5)  # > 1.0

    def test_negative_rejects(self):
        with pytest.raises(Exception):
            ObservableVector(x_spec_1=-0.1)  # < 0.0

    def test_zero_is_valid(self):
        """0.0 is a valid observed value (distinct from None/missing)."""
        v = ObservableVector(x_spec_1=0.0)
        assert v.x_spec_1 == 0.0
        assert v.present_count() == 1

    def test_one_is_valid(self):
        v = ObservableVector(x_spec_1=1.0)
        assert v.x_spec_1 == 1.0

    def test_field_count_is_42(self):
        fields = list(ObservableVector.model_fields.keys())
        assert len(fields) == 42, f"ObservableVector must have 42 fields, found {len(fields)}"

    def test_offshore_fields_present(self):
        fields = ObservableVector.model_fields
        assert "x_off_1" in fields
        assert "x_off_4" in fields

    def test_frozen(self):
        v = ObservableVector(x_spec_1=0.5)
        with pytest.raises(Exception):
            v.x_spec_1 = 0.9  # type: ignore


# ---------------------------------------------------------------------------
# F.2 — VersionRegistry
# ---------------------------------------------------------------------------

class TestVersionRegistry:
    def test_valid_registry_instantiates(self):
        r = make_version_registry()
        assert r.score_version == "0.1.0"

    def test_all_eight_fields_required(self):
        with pytest.raises(Exception):
            VersionRegistry(score_version="0.1.0")  # missing 7 fields

    def test_semver_validation(self):
        with pytest.raises(Exception):
            VersionRegistry(
                score_version="not-semver",
                tier_version="0.1.0",
                causal_graph_version="0.1.0",
                physics_model_version="0.1.0",
                temporal_model_version="0.1.0",
                province_prior_version="0.1.0",
                commodity_library_version="0.1.0",
                scan_pipeline_version="0.1.0",
            )

    def test_frozen(self):
        r = make_version_registry()
        with pytest.raises(Exception):
            r.score_version = "9.9.9"  # type: ignore


# ---------------------------------------------------------------------------
# F.3 — ThresholdSet and ThresholdPolicy
# ---------------------------------------------------------------------------

class TestThresholdSet:
    def test_valid_ordering(self):
        t = ThresholdSet(t1=0.75, t2=0.50, t3=0.25)
        assert t.t1 > t.t2 > t.t3

    def test_inverted_ordering_rejects(self):
        with pytest.raises(Exception):
            ThresholdSet(t1=0.25, t2=0.50, t3=0.75)

    def test_equal_values_reject(self):
        with pytest.raises(Exception):
            ThresholdSet(t1=0.50, t2=0.50, t3=0.25)

    def test_zero_t3_rejects(self):
        with pytest.raises(Exception):
            ThresholdSet(t1=0.75, t2=0.50, t3=0.0)

    def test_values_above_one_reject(self):
        with pytest.raises(Exception):
            ThresholdSet(t1=1.5, t2=0.50, t3=0.25)


class TestThresholdPolicy:
    def test_commodity_default_valid(self):
        p = make_threshold_policy()
        assert p.source == ThresholdSourceEnum.COMMODITY_FROZEN_DEFAULT

    def test_aoi_percentile_requires_percentile_fields(self):
        with pytest.raises(Exception):
            ThresholdPolicy(
                thresholds=make_threshold_set(),
                source=ThresholdSourceEnum.AOI_PERCENTILE,
                commodity="copper",
                # Missing aoi_percentile_p1/p2/p3
            )

    def test_aoi_percentile_with_all_fields_valid(self):
        p = ThresholdPolicy(
            thresholds=make_threshold_set(),
            source=ThresholdSourceEnum.AOI_PERCENTILE,
            commodity="copper",
            aoi_percentile_p1=90.0,
            aoi_percentile_p2=70.0,
            aoi_percentile_p3=50.0,
        )
        assert p.source == ThresholdSourceEnum.AOI_PERCENTILE


# ---------------------------------------------------------------------------
# F.3 — TierCounts
# ---------------------------------------------------------------------------

class TestTierCounts:
    def test_valid_counts(self):
        t = make_tier_counts()
        assert t.tier_1 + t.tier_2 + t.tier_3 + t.below == t.total_cells

    def test_mismatched_total_rejects(self):
        with pytest.raises(Exception):
            TierCounts(tier_1=5, tier_2=10, tier_3=15, below=20, total_cells=99)

    def test_zero_total_valid(self):
        t = TierCounts(tier_1=0, tier_2=0, tier_3=0, below=0, total_cells=0)
        assert t.tier_1_fraction == 0.0

    def test_tier_1_fraction(self):
        t = make_tier_counts(tier_1=10, tier_2=10, tier_3=10, below=10)
        assert t.tier_1_fraction == pytest.approx(0.25)

    def test_negative_counts_reject(self):
        with pytest.raises(Exception):
            TierCounts(tier_1=-1, tier_2=10, tier_3=10, below=10, total_cells=29)


# ---------------------------------------------------------------------------
# F.4 — GateResults and SystemStatus
# ---------------------------------------------------------------------------

class TestGateResults:
    def test_valid_gate_results(self):
        gr = make_gate_results(passed=3, total=4)
        assert gr.gates_passed == 3
        assert gr.gate_ratio == pytest.approx(0.75)

    def test_mismatched_passed_count_rejects(self):
        gates = [
            GateResult(gate_id="g1", gate_name="Gate 1", passed=True),
            GateResult(gate_id="g2", gate_name="Gate 2", passed=True),
        ]
        with pytest.raises(Exception):
            GateResults(gates=gates, gates_passed=5, gates_total=2)

    def test_mismatched_total_rejects(self):
        gates = [GateResult(gate_id="g1", gate_name="Gate 1", passed=True)]
        with pytest.raises(Exception):
            GateResults(gates=gates, gates_passed=1, gates_total=99)

    def test_all_gates_pass(self):
        gr = make_gate_results(passed=4, total=4)
        assert gr.gate_ratio == 1.0

    def test_zero_gates_ratio(self):
        gr = GateResults(gates=[], gates_passed=0, gates_total=0)
        assert gr.gate_ratio == 0.0


# ---------------------------------------------------------------------------
# F.5 — ScanJob: zero score fields
# ---------------------------------------------------------------------------

class TestScanJobScoreFieldExclusion:
    """
    Constitutional proof: ScanJob must contain ZERO score-equivalent fields.
    Any of the following in ScanJob.model_fields is a Phase F violation.
    """

    PROHIBITED_FIELDS = {
        "acif_score", "display_acif_score", "max_acif_score", "weighted_acif_score",
        "evidence_score", "causal_score", "physics_score", "temporal_score",
        "province_prior", "uncertainty",
        "tier_counts", "tier_thresholds_used", "tier_threshold_source",
        "gate_results", "system_status", "confirmation_reason",
        "version_registry", "observable_vector",
        "mean_evidence_score", "mean_causal_score", "mean_physics_score",
        "mean_temporal_score", "mean_province_prior", "mean_uncertainty",
    }

    def test_no_score_fields_in_scan_job(self):
        scan_job_fields = set(ScanJob.model_fields.keys())
        violations = self.PROHIBITED_FIELDS & scan_job_fields
        assert len(violations) == 0, (
            f"CONSTITUTIONAL VIOLATION: ScanJob contains score-equivalent fields: "
            f"{violations}. These fields belong exclusively in CanonicalScan."
        )

    def test_scan_job_instantiates_with_execution_fields_only(self):
        job = ScanJob(
            scan_job_id="job_001",
            scan_id_ref="scan_001",
            status=ScanStatus.RUNNING,
            pipeline_stage=PipelineStageEnum.EVIDENCE_SCORING,
            progress_pct=45.0,
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW,
        )
        assert job.status == ScanStatus.RUNNING
        assert job.progress_pct == 45.0
        assert not hasattr(job, "acif_score")

    def test_scan_job_has_no_canonical_fields(self):
        """CanonicalScan fields must not appear in ScanJob."""
        canonical_fields = set(CanonicalScan.model_fields.keys())
        scan_job_fields = set(ScanJob.model_fields.keys())
        # The ONLY allowed shared fields are scan_id_ref (ref to scan) and status
        # scan_id vs scan_id_ref are different field names
        overlap = canonical_fields & scan_job_fields
        # status and scan_id could overlap — these are acceptable cross-references
        acceptable_overlap = {"status"}
        violations = overlap - acceptable_overlap
        assert len(violations) == 0, (
            f"ScanJob and CanonicalScan share fields beyond acceptable: {violations}"
        )


# ---------------------------------------------------------------------------
# F.5 — CanonicalScan
# ---------------------------------------------------------------------------

class TestCanonicalScan:
    def test_completed_scan_instantiates(self):
        scan = make_completed_canonical_scan()
        assert scan.status == ScanStatus.COMPLETED
        assert scan.display_acif_score == pytest.approx(0.62)

    def test_completed_scan_requires_critical_fields(self):
        with pytest.raises(Exception):
            CanonicalScan(
                scan_id="scan_bad",
                status=ScanStatus.COMPLETED,
                commodity="gold",
                scan_tier=ScanTier.SMART,
                environment=ScanEnvironment.ONSHORE,
                aoi_geojson={},
                grid_resolution_degrees=0.01,
                total_cells=50,
                submitted_at=NOW,
                # Missing: display_acif_score, tier_counts, tier_thresholds_used,
                #          system_status, version_registry, completed_at
            )

    def test_tier_counts_must_match_total_cells(self):
        with pytest.raises(Exception):
            CanonicalScan(
                scan_id="scan_bad",
                status=ScanStatus.COMPLETED,
                commodity="gold",
                scan_tier=ScanTier.SMART,
                environment=ScanEnvironment.ONSHORE,
                aoi_geojson={},
                grid_resolution_degrees=0.01,
                total_cells=50,
                display_acif_score=0.6,
                tier_counts=TierCounts(tier_1=5, tier_2=5, tier_3=5, below=5, total_cells=20),
                # total_cells=50 != tier_counts.total_cells=20
                tier_thresholds_used=make_threshold_policy(),
                system_status=SystemStatusEnum.PASS_CONFIRMED,
                gate_results=make_gate_results(),
                confirmation_reason=make_confirmation_reason(),
                version_registry=make_version_registry(),
                submitted_at=NOW,
                completed_at=NOW,
            )

    def test_canonical_scan_is_frozen(self):
        scan = make_completed_canonical_scan()
        with pytest.raises(Exception):
            scan.display_acif_score = 0.99  # type: ignore

    def test_reprocess_lineage_fields(self):
        scan = CanonicalScan(
            scan_id="scan_002",
            status=ScanStatus.COMPLETED,
            commodity="gold",
            scan_tier=ScanTier.SMART,
            environment=ScanEnvironment.ONSHORE,
            aoi_geojson={},
            grid_resolution_degrees=0.01,
            total_cells=50,
            display_acif_score=0.62,
            tier_counts=make_tier_counts(),
            tier_thresholds_used=make_threshold_policy(),
            system_status=SystemStatusEnum.PASS_CONFIRMED,
            gate_results=make_gate_results(),
            confirmation_reason=make_confirmation_reason(),
            version_registry=make_version_registry(),
            submitted_at=NOW,
            completed_at=NOW,
            parent_scan_id="scan_001",
            reprocess_reason="Updated province priors",
        )
        assert scan.parent_scan_id == "scan_001"
        assert scan.reprocess_reason == "Updated province priors"


# ---------------------------------------------------------------------------
# F.5 — ScanCell
# ---------------------------------------------------------------------------

class TestScanCell:
    def test_minimal_cell_instantiates(self):
        cell = ScanCell(
            cell_id="cell_001",
            scan_id="scan_001",
            lat_center=51.5,
            lon_center=-0.1,
            cell_size_degrees=0.01,
            environment="ONSHORE",
        )
        assert cell.acif_score is None
        assert cell.tier is None

    def test_veto_flags_default_false(self):
        cell = ScanCell(
            cell_id="cell_002",
            scan_id="scan_001",
            lat_center=51.5,
            lon_center=-0.1,
            cell_size_degrees=0.01,
            environment="ONSHORE",
        )
        assert cell.causal_veto_fired is False
        assert cell.province_veto_fired is False
        assert cell.offshore_gate_blocked is False

    def test_score_bounds_enforced(self):
        with pytest.raises(Exception):
            ScanCell(
                cell_id="c", scan_id="s",
                lat_center=0.0, lon_center=0.0,
                cell_size_degrees=0.01,
                environment="ONSHORE",
                acif_score=1.5,  # > 1.0
            )

    def test_lat_bounds_enforced(self):
        with pytest.raises(Exception):
            ScanCell(
                cell_id="c", scan_id="s",
                lat_center=91.0,  # > 90
                lon_center=0.0, cell_size_degrees=0.01,
                environment="ONSHORE",
            )


# ---------------------------------------------------------------------------
# F.6 — Digital Twin Models
# ---------------------------------------------------------------------------

class TestDigitalTwinModels:
    def test_voxel_instantiates(self):
        v = DigitalTwinVoxel(
            voxel_id="vox_001",
            scan_id="scan_001",
            twin_version=1,
            lat_center=51.5,
            lon_center=-0.1,
            depth_m=500.0,
            depth_range_m=(250.0, 750.0),
            commodity_probs={"gold": 0.72},
            created_at=NOW,
        )
        assert v.commodity_probs["gold"] == pytest.approx(0.72)

    def test_commodity_prob_bounds(self):
        with pytest.raises(Exception):
            DigitalTwinVoxel(
                voxel_id="vox_bad",
                scan_id="scan_001",
                twin_version=1,
                lat_center=0.0,
                lon_center=0.0,
                depth_m=100.0,
                depth_range_m=(0.0, 200.0),
                commodity_probs={"gold": 1.5},  # > 1.0
                created_at=NOW,
            )

    def test_twin_query_instantiates(self):
        q = TwinQuery(scan_id="scan_001", min_probability=0.5, depth_min_m=100.0)
        assert q.limit == 500


# ---------------------------------------------------------------------------
# F.8 — Scan Request Models
# ---------------------------------------------------------------------------

class TestScanRequestModels:
    def test_polygon_request_valid(self):
        r = ScanRequest(
            commodity="gold",
            scan_tier=ScanTier.SMART,
            aoi_polygon=ScanPolygon(
                coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]
            ),
        )
        assert r.commodity == "gold"

    def test_grid_request_valid(self):
        r = ScanRequest(
            commodity="copper",
            scan_tier=ScanTier.BOOTSTRAP,
            grid=ScanGrid(min_lat=50.0, max_lat=51.0, min_lon=-1.0, max_lon=0.0, resolution_degrees=0.01),
        )
        assert r.grid is not None

    def test_both_geometries_rejects(self):
        with pytest.raises(Exception):
            ScanRequest(
                commodity="gold",
                scan_tier=ScanTier.SMART,
                aoi_polygon=ScanPolygon(coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]]),
                grid=ScanGrid(min_lat=50.0, max_lat=51.0, min_lon=-1.0, max_lon=0.0, resolution_degrees=0.01),
            )

    def test_no_geometry_rejects(self):
        with pytest.raises(Exception):
            ScanRequest(commodity="gold", scan_tier=ScanTier.SMART)

    def test_inverted_grid_rejects(self):
        with pytest.raises(Exception):
            ScanGrid(min_lat=51.0, max_lat=50.0, min_lon=-1.0, max_lon=0.0, resolution_degrees=0.01)

    def test_scan_status_response_completed_requires_summary(self):
        with pytest.raises(Exception):
            ScanStatusResponse(
                scan_id="s",
                status=ScanStatus.COMPLETED,
                canonical_summary=None,
                job_status=None,
            )

    def test_scan_status_response_running_requires_job_status(self):
        with pytest.raises(Exception):
            ScanStatusResponse(
                scan_id="s",
                status=ScanStatus.RUNNING,
                canonical_summary=None,
                job_status=None,
            )


# ---------------------------------------------------------------------------
# Constitutional: model import isolation
# ---------------------------------------------------------------------------

class TestModelImportIsolation:
    """
    Verifies that no model file imports from core/, services/, storage/,
    api/, or pipeline/ layers. Models must be self-contained.
    """

    FORBIDDEN_PREFIXES = [
        "app.core.",
        "app.services.",
        "app.storage.",
        "app.api.",
        "app.pipeline.",
    ]

    MODEL_MODULES = [
        "app.models.enums",
        "app.models.observable_vector",
        "app.models.version_registry",
        "app.models.threshold_policy",
        "app.models.tier_counts",
        "app.models.gate_results",
        "app.models.scan_cell",
        "app.models.scan_job",
        "app.models.canonical_scan",
        "app.models.digital_twin_model",
        "app.models.auth_model",
        "app.models.scan_request",
    ]

    def test_no_forbidden_imports_in_any_model(self):
        violations = []
        for module_name in self.MODEL_MODULES:
            if module_name not in sys.modules:
                continue
            module = sys.modules[module_name]
            source_file = inspect.getfile(module)
            with open(source_file) as f:
                source = f.read()
            for prefix in self.FORBIDDEN_PREFIXES:
                if f"from {prefix}" in source or f"import {prefix}" in source:
                    violations.append(f"{module_name} imports from forbidden layer: {prefix}")
        assert len(violations) == 0, (
            f"Model import isolation violations:\n" + "\n".join(violations)
        )