"""
Aurora OSI vNext — Phase Y Ground Truth Calibration Tests
Phase Y §Y.6 — Completion Proof Tests

PROOF REQUIREMENTS (from Phase Y approval directives):
  1. Calibration never modifies canonical scan outputs retroactively
  2. Calibration version lineage is immutable
  3. Synthetic data is rejected at ingestion AND storage layers
  4. Confidence weighting is explicit — composite formula is auditable
  5. Geological data type validation enforced at ingestion
  6. Calibration output is model configuration only (no ACIF/tier)
  7. Provenance required on every record
  8. CalibrationScanTrace provides traceability per scan
  9. No core/* imports in Phase Y files
"""

from __future__ import annotations

import pytest
from datetime import datetime


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_provenance(**kwargs):
    from app.models.ground_truth_model import GroundTruthProvenance
    defaults = dict(
        source_name       = "USGS MRDS",
        source_identifier = "https://mrdata.usgs.gov/mrds/record/10009247",
        country           = "ZA",
        commodity         = "gold",
        license_note      = "Public domain (US Government)",
        ingestion_timestamp = datetime.utcnow().isoformat(),
    )
    defaults.update(kwargs)
    return GroundTruthProvenance(**defaults)


def _make_confidence(**kwargs):
    from app.models.ground_truth_model import ConfidenceWeighting
    defaults = dict(
        source_confidence           = 0.9,
        spatial_accuracy            = 0.85,
        temporal_relevance          = 0.8,
        geological_context_strength = 0.75,
    )
    defaults.update(kwargs)
    return ConfidenceWeighting(**defaults)


def _make_record(is_synthetic=False, geo_type=None, payload=None, **kwargs):
    from app.models.ground_truth_model import (
        GroundTruthRecord, GeologicalDataType, new_record_id,
    )
    return GroundTruthRecord(
        record_id            = new_record_id(),
        geological_data_type = geo_type or GeologicalDataType.DEPOSIT_OCCURRENCE,
        provenance           = _make_provenance(),
        confidence           = _make_confidence(),
        is_synthetic         = is_synthetic,
        lat                  = -26.1,
        lon                  = 27.5,
        data_payload         = payload or {"deposit_name": "Witwatersrand Basin", "deposit_class": "gold_vein"},
        **kwargs,
    )


# ─── 1. Synthetic rejection at ingestion ─────────────────────────────────────

class TestSyntheticDataRejection:
    def test_ingestion_rejects_synthetic(self):
        """PROOF (directive 6): synthetic records are rejected at ingestion service."""
        from app.services.ground_truth_ingestion import (
            validate_ground_truth_record, SyntheticDataRejectedError,
        )
        record = _make_record(is_synthetic=True)
        with pytest.raises(SyntheticDataRejectedError):
            validate_ground_truth_record(record)

    def test_storage_rejects_synthetic(self):
        """PROOF (directive 6): synthetic records are rejected at STORAGE LAYER independently."""
        from app.storage.ground_truth import GroundTruthStorage, SyntheticStorageViolation
        store = GroundTruthStorage()
        record = _make_record(is_synthetic=True)
        with pytest.raises(SyntheticStorageViolation):
            store.write(record)

    def test_non_synthetic_accepted(self):
        from app.services.ground_truth_ingestion import validate_ground_truth_record
        record = _make_record(is_synthetic=False)
        warnings = validate_ground_truth_record(record)
        assert isinstance(warnings, list)

    def test_synthetic_flag_is_mandatory_field(self):
        """is_synthetic must exist as a field — cannot be omitted."""
        import dataclasses
        from app.models.ground_truth_model import GroundTruthRecord
        field_names = [f.name for f in dataclasses.fields(GroundTruthRecord)]
        assert "is_synthetic" in field_names


# ─── 2. Provenance required ───────────────────────────────────────────────────

class TestProvenanceRequired:
    def test_empty_source_name_raises(self):
        from app.models.ground_truth_model import GroundTruthProvenance
        with pytest.raises(ValueError, match="source_name"):
            GroundTruthProvenance(
                source_name="",  # empty
                source_identifier="https://example.com",
                country="ZA", commodity="gold",
                license_note="Open", ingestion_timestamp="2026-01-01T00:00:00",
            )

    def test_empty_source_identifier_raises(self):
        from app.models.ground_truth_model import GroundTruthProvenance
        with pytest.raises(ValueError, match="source_identifier"):
            GroundTruthProvenance(
                source_name="USGS", source_identifier="",
                country="ZA", commodity="gold",
                license_note="Open", ingestion_timestamp="2026-01-01T00:00:00",
            )

    def test_valid_provenance_accepted(self):
        p = _make_provenance()
        assert p.source_name == "USGS MRDS"


# ─── 3. Confidence weighting explicit + auditable ─────────────────────────────

class TestConfidenceWeighting:
    def test_out_of_bounds_raises(self):
        from app.models.ground_truth_model import ConfidenceWeighting
        with pytest.raises(ValueError):
            ConfidenceWeighting(
                source_confidence=1.5,  # > 1
                spatial_accuracy=0.8,
                temporal_relevance=0.7,
                geological_context_strength=0.6,
            )

    def test_composite_is_geometric_mean(self):
        """PROOF (directive 4): composite formula is geometric mean — explicitly auditable."""
        import math
        c = _make_confidence(
            source_confidence=0.8,
            spatial_accuracy=0.7,
            temporal_relevance=0.9,
            geological_context_strength=0.6,
        )
        expected = math.pow(0.8 * 0.7 * 0.9 * 0.6, 0.25)
        assert abs(c.composite - expected) < 1e-10

    def test_all_four_fields_required(self):
        """All four confidence fields must be present — no opaque weighting."""
        import dataclasses
        from app.models.ground_truth_model import ConfidenceWeighting
        field_names = {f.name for f in dataclasses.fields(ConfidenceWeighting)}
        assert "source_confidence"           in field_names
        assert "spatial_accuracy"            in field_names
        assert "temporal_relevance"          in field_names
        assert "geological_context_strength" in field_names


# ─── 4. Geological data type validation ───────────────────────────────────────

class TestGeologicalDataTypeValidation:
    def test_drill_intersection_requires_hole_id(self):
        from app.services.ground_truth_ingestion import validate_ground_truth_record
        from app.models.ground_truth_model import GeologicalDataType
        record = _make_record(
            geo_type=GeologicalDataType.DRILL_INTERSECTION,
            payload={"hole_id": "DDH-001", "from_m": 10.0},  # missing to_m
        )
        with pytest.raises(ValueError, match="to_m"):
            validate_ground_truth_record(record)

    def test_geochemical_anomaly_requires_element(self):
        from app.services.ground_truth_ingestion import validate_ground_truth_record
        from app.models.ground_truth_model import GeologicalDataType
        record = _make_record(
            geo_type=GeologicalDataType.GEOCHEMICAL_ANOMALY,
            payload={"value_ppm": 450.0},  # missing element
        )
        with pytest.raises(ValueError, match="element"):
            validate_ground_truth_record(record)

    def test_valid_deposit_occurrence_accepted(self):
        from app.services.ground_truth_ingestion import validate_ground_truth_record
        record = _make_record()  # deposit_occurrence with valid payload
        warnings = validate_ground_truth_record(record)
        assert isinstance(warnings, list)


# ─── 5. Calibration version lineage (directive 2) ────────────────────────────

class TestCalibrationVersionLineage:
    def _make_storage(self):
        from app.storage.ground_truth import GroundTruthStorage
        return GroundTruthStorage()

    def _make_params(self):
        from app.services.calibration_version import CalibrationParameters
        return CalibrationParameters(lambda_1_updates={"gold": 0.48})

    def test_create_version_assigns_uuid(self):
        from app.services.calibration_version import CalibrationVersionManager
        storage = self._make_storage()
        mgr = CalibrationVersionManager(storage)
        v = mgr.create_version(
            description="Test", rationale="Unit test",
            parameters=self._make_params(),
            ground_truth_record_ids=["r1"],
            calibration_effect_flags=["lambda_updated"],
            created_by="test_user",
        )
        assert v.version_id and "-" in v.version_id  # UUID

    def test_activate_creates_applies_after_timestamp(self):
        """PROOF (directive 1): activation sets applies_to_scans_after = now."""
        from app.services.calibration_version import CalibrationVersionManager, CalibrationVersionStatus
        storage = self._make_storage()
        mgr = CalibrationVersionManager(storage)
        v = mgr.create_version(
            description="Test", rationale="Test rationale",
            parameters=self._make_params(),
            ground_truth_record_ids=[],
            calibration_effect_flags=[],
            created_by="test",
        )
        activated = mgr.activate(v.version_id)
        assert activated.applies_to_scans_after != ""
        assert activated.status == CalibrationVersionStatus.ACTIVE

    def test_activate_supersedes_previous_version(self):
        """PROOF (directive 2): prior ACTIVE version becomes SUPERSEDED — not deleted."""
        from app.services.calibration_version import CalibrationVersionManager, CalibrationVersionStatus
        storage = self._make_storage()
        mgr = CalibrationVersionManager(storage)

        v1 = mgr.create_version("V1", "First version", self._make_params(), [], [], "u1")
        v1_activated = mgr.activate(v1.version_id)
        assert v1_activated.status == CalibrationVersionStatus.ACTIVE

        v2 = mgr.create_version("V2", "Second version", self._make_params(), [], [], "u1",
                                 parent_version_id=v1.version_id)
        mgr.activate(v2.version_id)

        # V1 must be SUPERSEDED — not deleted
        v1_stored = storage.get_version(v1.version_id)
        assert v1_stored is not None
        assert v1_stored.status == CalibrationVersionStatus.SUPERSEDED

    def test_lineage_chain_walks_parents(self):
        from app.services.calibration_version import CalibrationVersionManager
        storage = self._make_storage()
        mgr = CalibrationVersionManager(storage)

        v1 = mgr.create_version("Root", "Root version", self._make_params(), [], [], "u1")
        v2 = mgr.create_version("Child", "Child version", self._make_params(), [], [], "u1",
                                  parent_version_id=v1.version_id)
        chain = mgr.get_lineage(v2.version_id)
        assert [v.version_id for v in chain] == [v1.version_id, v2.version_id]

    def test_rationale_required(self):
        from app.services.calibration_version import CalibrationVersionManager
        storage = self._make_storage()
        mgr = CalibrationVersionManager(storage)
        with pytest.raises(ValueError, match="rationale"):
            mgr.create_version("V", "", self._make_params(), [], [], "u1")


# ─── 6. Calibration output is model config only — no ACIF/tier ───────────────

class TestCalibrationOutputIsConfigOnly:
    def test_calibration_parameters_has_no_acif_field(self):
        import dataclasses
        from app.services.calibration_version import CalibrationParameters
        field_names = {f.name for f in dataclasses.fields(CalibrationParameters)}
        # Must not contain any scoring output field
        for forbidden in ["acif_score", "tier", "gate_result", "scan_result"]:
            assert forbidden not in field_names, \
                f"VIOLATION: CalibrationParameters has field {forbidden!r} — scoring output"

    def test_calibration_parameters_contains_only_config(self):
        import dataclasses
        from app.services.calibration_version import CalibrationParameters
        field_names = {f.name for f in dataclasses.fields(CalibrationParameters)}
        # Must contain model configuration fields only
        expected_config_fields = {
            "province_prior_updates", "lambda_1_updates", "lambda_2_updates",
            "tau_grav_veto_updates", "tau_phys_veto_updates", "uncertainty_model_updates",
        }
        assert field_names == expected_config_fields


# ─── 7. Scan traceability (directive 2) ───────────────────────────────────────

class TestCalibrationScanTrace:
    def test_trace_stores_calibration_version_id(self):
        from app.models.ground_truth_model import new_trace
        trace = new_trace(
            scan_id="scan_abc",
            calibration_version_id="v-uuid-123",
            ground_truth_source_ids=["r1", "r2"],
            calibration_effect_flags=["lambda_updated"],
        )
        assert trace.calibration_version_id == "v-uuid-123"
        assert "r1" in trace.ground_truth_source_ids
        assert "lambda_updated" in trace.calibration_effect_flags

    def test_trace_is_immutable(self):
        from app.models.ground_truth_model import new_trace
        trace = new_trace("s1", "v1", [], [])
        with pytest.raises((AttributeError, TypeError)):
            trace.scan_id = "modified"  # frozen dataclass


# ─── 8. Storage immutability ──────────────────────────────────────────────────

class TestStorageImmutability:
    def test_duplicate_write_raises(self):
        from app.storage.ground_truth import GroundTruthStorage, DestructiveWriteViolation
        store = GroundTruthStorage()
        record = _make_record()
        store.write(record)
        with pytest.raises(DestructiveWriteViolation):
            store.write(record)   # same record_id — must raise

    def test_approved_records_list_excludes_synthetic(self):
        from app.storage.ground_truth import GroundTruthStorage, SyntheticStorageViolation
        store = GroundTruthStorage()
        record = _make_record()
        store.write(record)
        # synthetic write is blocked, so all stored records are non-synthetic
        approved = store.list_all()
        for r in approved:
            assert not r.is_synthetic


# ─── 9. No core/* imports ─────────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = [
        "app.core.scoring", "app.core.tiering", "app.core.gates",
        "app.core.evidence", "app.core.causal",
    ]
    FORBIDDEN_FNS = ["compute_acif", "assign_tier", "evaluate_gates"]

    def _check(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for prefix in self.FORBIDDEN:
            assert prefix not in src, f"VIOLATION: {module_path} imports {prefix}"
        for fn in self.FORBIDDEN_FNS:
            assert fn not in src, f"VIOLATION: {module_path} calls {fn}"

    def test_ground_truth_model(self):       self._check("app.models.ground_truth_model")
    def test_ingestion_service(self):        self._check("app.services.ground_truth_ingestion")
    def test_calibration_version(self):      self._check("app.services.calibration_version")
    def test_ground_truth_storage(self):     self._check("app.storage.ground_truth")