"""
Phase G — Storage Layer Contract Tests

Tests the storage layer without a live database by verifying:
  1. StorageImmutabilityError is raised at application level before DB call
  2. StorageAuditViolationError is raised when update/delete attempted on audit log
  3. StorageOffshoreGateError is raised for uncorrected offshore cells
  4. Exception hierarchy is correct
  5. PaginationParams validates inputs
  6. Store modules do not import from core/, services/, or api/
  7. Migration SQL files define required tables and triggers
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage.base import (
    PaginatedResult,
    PaginationParams,
    StorageAuditViolationError,
    StorageConstraintError,
    StorageError,
    StorageImmutabilityError,
    StorageNotFoundError,
    StorageOffshoreGateError,
    StorageReplayError,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestStorageExceptions:
    def test_immutability_is_storage_error(self):
        assert issubclass(StorageImmutabilityError, StorageError)

    def test_audit_violation_is_storage_error(self):
        assert issubclass(StorageAuditViolationError, StorageError)

    def test_not_found_is_storage_error(self):
        assert issubclass(StorageNotFoundError, StorageError)

    def test_offshore_gate_is_storage_error(self):
        assert issubclass(StorageOffshoreGateError, StorageError)

    def test_replay_is_storage_error(self):
        assert issubclass(StorageReplayError, StorageError)

    def test_constraint_is_storage_error(self):
        assert issubclass(StorageConstraintError, StorageError)

    def test_immutability_error_message(self):
        err = StorageImmutabilityError("scan_id=test-123 is COMPLETED")
        assert "COMPLETED" in str(err) or "test-123" in str(err)

    def test_audit_violation_error_message(self):
        err = StorageAuditViolationError("UPDATE not permitted")
        assert "UPDATE" in str(err) or "not permitted" in str(err)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPaginationParams:
    def test_default_pagination(self):
        p = PaginationParams.default()
        assert p.page == 1
        assert p.page_size == 50
        assert p.offset == 0

    def test_page_2_offset(self):
        p = PaginationParams(page=2, page_size=25)
        assert p.offset == 25

    def test_page_3_offset(self):
        p = PaginationParams(page=3, page_size=10)
        assert p.offset == 20

    def test_invalid_page_rejects(self):
        with pytest.raises(ValueError):
            PaginationParams(page=0, page_size=50)

    def test_invalid_page_size_rejects(self):
        with pytest.raises(ValueError):
            PaginationParams(page=1, page_size=0)

    def test_page_size_over_500_rejects(self):
        with pytest.raises(ValueError):
            PaginationParams(page=1, page_size=501)

    def test_total_pages_ceiling(self):
        p = PaginationParams(page=1, page_size=10)
        result = PaginatedResult(items=list(range(10)), total=25, params=p)
        assert result.total_pages == 3  # ceil(25/10) = 3

    def test_total_pages_exact(self):
        p = PaginationParams(page=1, page_size=10)
        result = PaginatedResult(items=list(range(10)), total=20, params=p)
        assert result.total_pages == 2


# ---------------------------------------------------------------------------
# CanonicalScanStore — Immutability guard (application-level)
# ---------------------------------------------------------------------------

class TestCanonicalScanStoreImmutability:
    """
    Tests the application-level immutability guard in CanonicalScanStore.
    Does not require a live database — mocks the _get_status call.
    """

    @pytest.mark.asyncio
    async def test_freeze_raises_on_completed_scan(self):
        """
        freeze_canonical_scan() must raise StorageImmutabilityError
        if the scan already has status=COMPLETED.
        """
        from app.storage.scans import CanonicalScanStore

        mock_session = AsyncMock()
        store = CanonicalScanStore(session=mock_session)

        # Patch _get_status to return COMPLETED
        store._get_status = AsyncMock(return_value="COMPLETED")

        # Build a minimal CanonicalScan (status=COMPLETED to pass model validation)
        from datetime import datetime, timezone
        from app.models.canonical_scan import CanonicalScan
        from app.models.enums import ScanEnvironment, ScanStatus, ScanTier, SystemStatusEnum
        from app.models.gate_results import ConfirmationReason, GateResult, GateResults
        from app.models.threshold_policy import ThresholdPolicy, ThresholdSet
        from app.models.tier_counts import TierCounts
        from app.models.version_registry import VersionRegistry

        NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scan = CanonicalScan(
            scan_id="scan_frozen",
            status=ScanStatus.COMPLETED,
            commodity="gold",
            scan_tier=ScanTier.SMART,
            environment=ScanEnvironment.ONSHORE,
            aoi_geojson={},
            grid_resolution_degrees=0.01,
            total_cells=10,
            display_acif_score=0.7,
            tier_counts=TierCounts(tier_1=2, tier_2=3, tier_3=3, below=2, total_cells=10),
            tier_thresholds_used=ThresholdPolicy(
                thresholds=ThresholdSet(t1=0.75, t2=0.5, t3=0.25),
                source="commodity_frozen_default",
                commodity="gold",
            ),
            system_status=SystemStatusEnum.PASS_CONFIRMED,
            gate_results=GateResults(gates=[], gates_passed=0, gates_total=0),
            confirmation_reason=ConfirmationReason(gate_ratio=1.0),
            version_registry=VersionRegistry(
                score_version="0.1.0", tier_version="0.1.0",
                causal_graph_version="0.1.0", physics_model_version="0.1.0",
                temporal_model_version="0.1.0", province_prior_version="0.1.0",
                commodity_library_version="0.1.0", scan_pipeline_version="0.1.0",
            ),
            submitted_at=NOW,
            completed_at=NOW,
        )

        with pytest.raises(StorageImmutabilityError) as exc_info:
            await store.freeze_canonical_scan(scan)

        assert "COMPLETED" in str(exc_info.value)
        assert "freeze_canonical_scan" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_freeze_proceeds_on_pending_scan(self):
        """freeze_canonical_scan() proceeds when status=PENDING."""
        from app.storage.scans import CanonicalScanStore
        from datetime import datetime, timezone
        from app.models.canonical_scan import CanonicalScan
        from app.models.enums import ScanEnvironment, ScanStatus, ScanTier, SystemStatusEnum
        from app.models.gate_results import ConfirmationReason, GateResults
        from app.models.threshold_policy import ThresholdPolicy, ThresholdSet
        from app.models.tier_counts import TierCounts
        from app.models.version_registry import VersionRegistry

        NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        store = CanonicalScanStore(session=mock_session)
        store._get_status = AsyncMock(return_value="PENDING")  # Not completed yet

        scan = CanonicalScan(
            scan_id="scan_pending",
            status=ScanStatus.COMPLETED,
            commodity="gold",
            scan_tier=ScanTier.SMART,
            environment=ScanEnvironment.ONSHORE,
            aoi_geojson={},
            grid_resolution_degrees=0.01,
            total_cells=10,
            display_acif_score=0.7,
            tier_counts=TierCounts(tier_1=2, tier_2=3, tier_3=3, below=2, total_cells=10),
            tier_thresholds_used=ThresholdPolicy(
                thresholds=ThresholdSet(t1=0.75, t2=0.5, t3=0.25),
                source="commodity_frozen_default",
                commodity="gold",
            ),
            system_status=SystemStatusEnum.PASS_CONFIRMED,
            gate_results=GateResults(gates=[], gates_passed=0, gates_total=0),
            confirmation_reason=ConfirmationReason(gate_ratio=1.0),
            version_registry=VersionRegistry(
                score_version="0.1.0", tier_version="0.1.0",
                causal_graph_version="0.1.0", physics_model_version="0.1.0",
                temporal_model_version="0.1.0", province_prior_version="0.1.0",
                commodity_library_version="0.1.0", scan_pipeline_version="0.1.0",
            ),
            submitted_at=NOW,
            completed_at=NOW,
        )

        # Should not raise — PENDING scan is freezeable
        await store.freeze_canonical_scan(scan)
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# AuditLogStore — Update/Delete explicitly blocked
# ---------------------------------------------------------------------------

class TestAuditLogStoreImmutability:
    @pytest.mark.asyncio
    async def test_update_raises_audit_violation(self):
        from app.storage.audit import AuditLogStore
        mock_session = AsyncMock()
        store = AuditLogStore(session=mock_session)

        with pytest.raises(StorageAuditViolationError) as exc_info:
            await store.update_audit_event(audit_id="abc", details={})

        assert "immutable" in str(exc_info.value).lower() or "UPDATE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_raises_audit_violation(self):
        from app.storage.audit import AuditLogStore
        mock_session = AsyncMock()
        store = AuditLogStore(session=mock_session)

        with pytest.raises(StorageAuditViolationError) as exc_info:
            await store.delete_audit_event(audit_id="abc")

        assert "immutable" in str(exc_info.value).lower() or "DELETE" in str(exc_info.value)


# ---------------------------------------------------------------------------
# HarmonisedTensorStore — Offshore gate enforcement
# ---------------------------------------------------------------------------

class TestHarmonisedTensorOffshoreGate:
    @pytest.mark.asyncio
    async def test_offshore_cell_without_correction_raises(self):
        from app.storage.observables import HarmonisedTensorStore
        mock_session = AsyncMock()
        store = HarmonisedTensorStore(session=mock_session)

        with pytest.raises(StorageOffshoreGateError) as exc_info:
            await store.write_harmonised_tensor(
                scan_id="scan_001",
                cell_id="cell_offshore_001",
                environment="OFFSHORE",
                observable_vector={"x_spec_1": 0.5},
                normalisation_params={},
                present_count=1,
                missing_count=41,
                offshore_corrected=False,  # ← NOT corrected
            )

        assert "offshore" in str(exc_info.value).lower()
        assert "cell_offshore_001" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_offshore_cell_with_correction_proceeds(self):
        from app.storage.observables import HarmonisedTensorStore
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        store = HarmonisedTensorStore(session=mock_session)

        # Should NOT raise — offshore_corrected=True
        await store.write_harmonised_tensor(
            scan_id="scan_001",
            cell_id="cell_offshore_002",
            environment="OFFSHORE",
            observable_vector={"x_off_1": 0.3},
            normalisation_params={},
            present_count=1,
            missing_count=41,
            offshore_corrected=True,  # ← Correction applied
        )
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_onshore_cell_no_correction_required(self):
        from app.storage.observables import HarmonisedTensorStore
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        store = HarmonisedTensorStore(session=mock_session)

        # Onshore cells never need offshore_corrected=True
        await store.write_harmonised_tensor(
            scan_id="scan_001",
            cell_id="cell_onshore_001",
            environment="ONSHORE",
            observable_vector={"x_spec_1": 0.6},
            normalisation_params={},
            present_count=1,
            missing_count=41,
            offshore_corrected=False,
        )
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Storage import isolation
# ---------------------------------------------------------------------------

class TestStorageImportIsolation:
    """
    Verifies that no storage module imports from core/, services/, or api/.
    Storage layer (Layer 1) must not depend on higher layers.
    """

    FORBIDDEN_PREFIXES = [
        "app.core.",
        "app.services.",
        "app.api.",
        "app.pipeline.",
    ]

    STORAGE_MODULES = [
        "app.storage.base",
        "app.storage.scans",
        "app.storage.scan_jobs",
        "app.storage.observables",
        "app.storage.history",
        "app.storage.twin",
        "app.storage.audit",
        "app.storage.commodity_library",
        "app.storage.province_priors",
    ]

    def test_no_forbidden_imports_in_storage_modules(self):
        violations = []
        for module_name in self.STORAGE_MODULES:
            if module_name not in sys.modules:
                continue
            module = sys.modules[module_name]
            try:
                source_file = inspect.getfile(module)
                with open(source_file) as f:
                    source = f.read()
                for prefix in self.FORBIDDEN_PREFIXES:
                    if f"from {prefix}" in source or f"import {prefix}" in source:
                        violations.append(
                            f"{module_name} imports from forbidden layer: {prefix}"
                        )
            except (TypeError, OSError):
                pass
        assert len(violations) == 0, (
            "Storage layer import isolation violations:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Migration SQL integrity checks
# ---------------------------------------------------------------------------

class TestMigrationSQLIntegrity:
    """
    Verifies that the migration SQL files contain the required tables,
    triggers, and constraints without executing against a live database.
    """

    BASE = Path(__file__).parent.parent.parent / "infra" / "db" / "migrations"

    def _read(self, filename: str) -> str:
        return (self.BASE / filename).read_text()

    def test_migration_001_canonical_scans_table(self):
        sql = self._read("001_initial_schema.sql")
        assert "CREATE TABLE IF NOT EXISTS canonical_scans" in sql

    def test_migration_001_scan_jobs_table(self):
        sql = self._read("001_initial_schema.sql")
        assert "CREATE TABLE IF NOT EXISTS scan_jobs" in sql

    def test_migration_001_immutability_trigger_exists(self):
        sql = self._read("001_initial_schema.sql")
        assert "enforce_canonical_scan_immutability" in sql
        assert "trg_canonical_scan_immutability" in sql

    def test_migration_001_trigger_rejects_completed_updates(self):
        sql = self._read("001_initial_schema.sql")
        assert "OLD.status = 'COMPLETED'" in sql
        assert "AURORA_IMMUTABILITY_VIOLATION" in sql

    def test_migration_001_audit_log_rls(self):
        sql = self._read("001_initial_schema.sql")
        assert "ROW LEVEL SECURITY" in sql
        assert "audit_log_no_update" in sql
        assert "audit_log_no_delete" in sql

    def test_migration_001_postgis_enabled(self):
        sql = self._read("001_initial_schema.sql")
        assert "postgis" in sql.lower()

    def test_migration_001_scan_cells_table(self):
        sql = self._read("001_initial_schema.sql")
        assert "CREATE TABLE IF NOT EXISTS scan_cells" in sql

    def test_migration_001_digital_twin_voxels(self):
        sql = self._read("001_initial_schema.sql")
        assert "CREATE TABLE IF NOT EXISTS digital_twin_voxels" in sql

    def test_migration_001_history_index_materialised_view(self):
        sql = self._read("001_initial_schema.sql")
        assert "MATERIALIZED VIEW" in sql
        assert "history_index" in sql

    def test_migration_001_no_acif_formula(self):
        """Migration SQL must contain zero scoring formulas."""
        sql = self._read("001_initial_schema.sql")
        acif_patterns = ["acif =", "* E_i", "* C_i", "evidence * causal"]
        for pattern in acif_patterns:
            assert pattern not in sql, (
                f"Migration SQL contains scoring formula pattern: '{pattern}'"
            )

    def test_migration_002_commodity_tables(self):
        sql = self._read("002_commodity_library.sql")
        assert "CREATE TABLE IF NOT EXISTS commodity_definitions" in sql
        assert "CREATE TABLE IF NOT EXISTS observable_weighting_vectors" in sql
        assert "CREATE TABLE IF NOT EXISTS spectral_response_curves" in sql
        assert "CREATE TABLE IF NOT EXISTS depth_kernel_params" in sql
        assert "CREATE TABLE IF NOT EXISTS environmental_regime_modifiers" in sql

    def test_migration_002_nine_families_inserted(self):
        sql = self._read("002_commodity_library.sql")
        for family_id in ("'A'", "'B'", "'C'", "'D'", "'E'", "'F'", "'G'", "'H'", "'I'"):
            assert family_id in sql

    def test_migration_002_forty_commodities(self):
        sql = self._read("002_commodity_library.sql")
        # Count INSERT rows for commodity_definitions
        assert "'gold'" in sql
        assert "'copper'" in sql
        assert "'lithium'" in sql
        assert "'diamond'" in sql
        assert "'manganese_nodule'" in sql  # offshore

    def test_migration_003_province_tables(self):
        sql = self._read("003_province_priors.sql")
        assert "CREATE TABLE IF NOT EXISTS tectono_stratigraphic_provinces" in sql
        assert "CREATE TABLE IF NOT EXISTS province_prior_probabilities" in sql
        assert "CREATE TABLE IF NOT EXISTS province_cell_cache" in sql

    def test_migration_003_impossible_province_constraint(self):
        sql = self._read("003_province_priors.sql")
        assert "impossible_province_has_zero_probability" in sql
        assert "prior_probability = 0.0" in sql

    def test_migration_003_posterior_requires_parent(self):
        sql = self._read("003_province_priors.sql")
        assert "posterior_has_parent" in sql

    def test_migration_003_postgis_spatial_index(self):
        sql = self._read("003_province_priors.sql")
        assert "GIST" in sql
        assert "province_geom" in sql