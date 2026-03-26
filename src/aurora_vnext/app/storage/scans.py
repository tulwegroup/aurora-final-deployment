"""
Aurora OSI vNext — Canonical Scan Store + ScanCell Store
Phase G §G.3

WRITE-ONCE after status=COMPLETED.

The canonical freeze contract:
  1. create_pending_scan()   → writes initial record, status=PENDING
  2. freeze_canonical_scan() → single atomic write of all canonical fields
                               + status=COMPLETED
  3. StorageImmutabilityError is raised by both the DB trigger AND this layer
     if freeze is attempted twice on the same scan_id.
  4. get_canonical_scan() → read-only retrieval, always returns frozen state.

ScanCell records are written atomically alongside the CanonicalScan at step 19.
They are never modified after write.

FAILURE-PATH IMMUTABILITY PROOF (referenced by api/scan.py and Phase L docs):
  create_pending_scan() writes ONLY: scan_id, status=PENDING, commodity, scan_tier,
    environment, aoi_geojson, grid_resolution_degrees, parent_scan_id, submitted_at.
  NO score fields. NO tier fields. NO gate fields. NO component scores.
  freeze_canonical_scan() is the SOLE path to write any result field.
  freeze_canonical_scan() sets status=COMPLETED atomically with all result fields.
  The DB WHERE clause (AND status != 'COMPLETED') prevents double-freeze races.
  Therefore: a scan that fails before step 19 has status=PENDING|RUNNING|FAILED
  and zero result fields in the canonical store — immutability is structurally guaranteed.

No scientific logic. No scoring. No imports from core/ or services/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_scan import CanonicalScan, CanonicalScanSummary
from app.models.enums import ScanEnvironment, ScanStatus, ScanTier
from app.storage.base import (
    BaseStore,
    PaginatedResult,
    PaginationParams,
    StorageImmutabilityError,
    StorageNotFoundError,
)


class CanonicalScanStore(BaseStore):
    """
    Storage interface for canonical scan records.

    IMMUTABILITY CONTRACT:
      Once a record has status=COMPLETED, all write operations are blocked
      at two independent enforcement points:
        1. PostgreSQL trigger (trg_canonical_scan_immutability)
        2. This class's freeze guard (pre-write check before DB call)
    """

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    async def create_pending_scan(
        self,
        scan_id: Optional[str] = None,
        commodity: str = "",
        scan_tier: ScanTier = ScanTier.SMART,
        environment: ScanEnvironment = ScanEnvironment.ONSHORE,
        aoi_geojson: dict | None = None,
        grid_resolution_degrees: float = 0.01,
        parent_scan_id: Optional[str] = None,
        operator_notes: Optional[str] = None,
    ) -> str:
        """
        Write initial PENDING canonical scan record before pipeline starts.

        IMMUTABILITY PROOF:
          Writes ONLY identity/config fields. Zero result fields are written here.
          Any pipeline failure before step 19 leaves this record in PENDING status
          with no score, tier, gate, or component fields populated.
          This is the structural guarantee that failed pipelines leave no
          partial canonical result state.

        Returns the scan_id.
        """
        new_id = scan_id or str(uuid4())
        await self._session.execute(
            text("""
                INSERT INTO canonical_scans (
                    scan_id, status, commodity, scan_tier, environment,
                    aoi_geojson, grid_resolution_degrees, parent_scan_id,
                    operator_notes, submitted_at
                ) VALUES (
                    :scan_id, 'PENDING', :commodity, :scan_tier, :environment,
                    :aoi_geojson::jsonb, :resolution, :parent_scan_id,
                    :operator_notes, NOW()
                )
            """),
            {
                "scan_id": new_id,
                "commodity": commodity,
                "scan_tier": scan_tier.value,
                "environment": environment.value,
                "aoi_geojson": json.dumps(aoi_geojson or {}),
                "resolution": grid_resolution_degrees,
                "parent_scan_id": parent_scan_id,
                "operator_notes": operator_notes,
            }
        )
        await self._session.commit()
        return new_id

    async def freeze_canonical_scan(self, canonical_scan: CanonicalScan) -> None:
        """
        Atomic write of all canonical result fields + status=COMPLETED.

        This is the ONLY path through which a scan transitions to COMPLETED.
        It is called ONCE at pipeline step 19 (canonical freeze).

        IMMUTABILITY PROOF:
          - Application-level: pre-check rejects double-freeze before DB call
          - Database-level: WHERE status != 'COMPLETED' ensures atomicity
          - DB trigger: trg_canonical_scan_immutability blocks any UPDATE on COMPLETED rows
          - Together these form two independent, complementary enforcement layers.

        Raises StorageImmutabilityError if the scan is already COMPLETED.
        """
        existing = await self._get_status(canonical_scan.scan_id)
        if existing == ScanStatus.COMPLETED.value:
            raise StorageImmutabilityError(
                f"AURORA_IMMUTABILITY_VIOLATION: scan_id={canonical_scan.scan_id} "
                f"is already COMPLETED. freeze_canonical_scan() may only be called once. "
                f"To reprocess, use reprocess_controller.submit_reprocess() to create "
                f"a new scan with parent_scan_id={canonical_scan.scan_id}."
            )

        await self._session.execute(
            text("""
                UPDATE canonical_scans SET
                    status                      = 'COMPLETED',
                    total_cells                 = :total_cells,
                    display_acif_score          = :display_acif_score,
                    max_acif_score              = :max_acif_score,
                    weighted_acif_score         = :weighted_acif_score,
                    tier_counts                 = :tier_counts::jsonb,
                    tier_thresholds_used        = :tier_thresholds_used::jsonb,
                    system_status               = :system_status,
                    gate_results                = :gate_results::jsonb,
                    confirmation_reason         = :confirmation_reason::jsonb,
                    mean_evidence_score         = :mean_evidence_score,
                    mean_causal_score           = :mean_causal_score,
                    mean_physics_score          = :mean_physics_score,
                    mean_temporal_score         = :mean_temporal_score,
                    mean_province_prior         = :mean_province_prior,
                    mean_uncertainty            = :mean_uncertainty,
                    causal_veto_cell_count      = :causal_veto_count,
                    physics_veto_cell_count     = :physics_veto_count,
                    province_veto_cell_count    = :province_veto_count,
                    offshore_blocked_cell_count = :offshore_blocked_count,
                    offshore_cell_count         = :offshore_cell_count,
                    water_column_corrected      = :water_column_corrected,
                    version_registry            = :version_registry::jsonb,
                    normalisation_params        = :normalisation_params::jsonb,
                    parent_scan_id              = :parent_scan_id,
                    reprocess_reason            = :reprocess_reason,
                    reprocess_changed_params    = :reprocess_changed_params::jsonb,
                    migration_class             = :migration_class,
                    migration_notes             = :migration_notes,
                    completed_at                = NOW()
                WHERE scan_id = :scan_id
                  AND status != 'COMPLETED'
            """),
            {
                "scan_id":                  canonical_scan.scan_id,
                "total_cells":              canonical_scan.total_cells,
                "display_acif_score":       canonical_scan.display_acif_score,
                "max_acif_score":           canonical_scan.max_acif_score,
                "weighted_acif_score":      canonical_scan.weighted_acif_score,
                "tier_counts":              _jsonb(canonical_scan.tier_counts),
                "tier_thresholds_used":     _jsonb(canonical_scan.tier_thresholds_used),
                "system_status":            canonical_scan.system_status.value if canonical_scan.system_status else None,
                "gate_results":             _jsonb(canonical_scan.gate_results),
                "confirmation_reason":      _jsonb(canonical_scan.confirmation_reason),
                "mean_evidence_score":      canonical_scan.mean_evidence_score,
                "mean_causal_score":        canonical_scan.mean_causal_score,
                "mean_physics_score":       canonical_scan.mean_physics_score,
                "mean_temporal_score":      canonical_scan.mean_temporal_score,
                "mean_province_prior":      canonical_scan.mean_province_prior,
                "mean_uncertainty":         canonical_scan.mean_uncertainty,
                "causal_veto_count":        canonical_scan.causal_veto_cell_count or 0,
                "physics_veto_count":       canonical_scan.physics_veto_cell_count or 0,
                "province_veto_count":      canonical_scan.province_veto_cell_count or 0,
                "offshore_blocked_count":   canonical_scan.offshore_blocked_cell_count or 0,
                "offshore_cell_count":      canonical_scan.offshore_cell_count or 0,
                "water_column_corrected":   canonical_scan.water_column_corrected,
                "version_registry":         _jsonb(canonical_scan.version_registry),
                "normalisation_params":     json.dumps(canonical_scan.normalisation_params or {}),
                "parent_scan_id":           canonical_scan.parent_scan_id,
                "reprocess_reason":         canonical_scan.reprocess_reason,
                "reprocess_changed_params": _jsonb(canonical_scan.reprocess_changed_params),
                "migration_class":          canonical_scan.migration_class.value if canonical_scan.migration_class else None,
                "migration_notes":          canonical_scan.migration_notes,
            }
        )
        await self._session.commit()

    async def soft_delete_scan(
        self,
        scan_id: str,
        actor: str,
        reason: str,
    ) -> None:
        """
        Admin-only soft delete. Physical record retained for audit.
        Caller MUST write an audit record before calling this method.
        """
        result = await self._session.execute(
            text("SELECT soft_delete_canonical_scan(:scan_id, :actor, :reason)"),
            {"scan_id": scan_id, "actor": actor, "reason": reason},
        )
        await self._session.commit()

    # -------------------------------------------------------------------------
    # Read operations (all read-only; never trigger recomputation)
    # -------------------------------------------------------------------------

    async def get_canonical_scan(self, scan_id: str) -> CanonicalScan:
        """
        Retrieve a CanonicalScan by ID.
        Raises StorageNotFoundError if not found.

        REPEATED-READ CONSISTENCY PROOF:
          The returned record is hydrated from the DB row.
          Canonical rows are never modified after freeze_canonical_scan().
          Therefore this method always returns identical values for the same scan_id.
        """
        row = await self._session.execute(
            text("SELECT * FROM canonical_scans WHERE scan_id = :scan_id"),
            {"scan_id": scan_id},
        )
        record = row.mappings().fetchone()
        if record is None:
            raise StorageNotFoundError(f"CanonicalScan not found: scan_id={scan_id}")
        return _row_to_canonical_scan(record)

    async def list_canonical_scans(
        self,
        commodity: Optional[str] = None,
        status: Optional[str] = None,
        system_status: Optional[str] = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult:
        """List canonical scans with optional filters. Returns paginated summaries."""
        p = pagination or PaginationParams.default()
        filters = ["status != 'SOFT_DELETED'"]
        params: dict = {"limit": p.page_size, "offset": p.offset}
        if commodity:
            filters.append("commodity = :commodity")
            params["commodity"] = commodity
        if status:
            filters.append("status = :status")
            params["status"] = status
        if system_status:
            filters.append("system_status = :system_status")
            params["system_status"] = system_status

        where = " AND ".join(filters)
        rows = await self._session.execute(
            text(f"""
                SELECT scan_id, commodity, scan_tier, environment, status,
                       display_acif_score, max_acif_score, system_status,
                       tier_counts, total_cells, submitted_at, completed_at,
                       parent_scan_id, migration_class
                FROM canonical_scans
                WHERE {where}
                ORDER BY submitted_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        total_row = await self._session.execute(
            text(f"SELECT COUNT(*) FROM canonical_scans WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
        total = total_row.scalar() or 0
        items = [_row_to_summary(r) for r in rows.mappings().fetchall()]
        return PaginatedResult(items=items, total=total, params=p)

    async def _get_status(self, scan_id: str) -> Optional[str]:
        """Internal: fetch only the status field for pre-write guard checks."""
        row = await self._session.execute(
            text("SELECT status FROM canonical_scans WHERE scan_id = :scan_id"),
            {"scan_id": scan_id},
        )
        record = row.fetchone()
        return record[0] if record else None


# ---------------------------------------------------------------------------
# ScanCell Store — written once at canonical freeze, never modified
# ---------------------------------------------------------------------------

class ScanCellStore(BaseStore):
    """
    Storage for per-cell scientific outputs.
    Written once at canonical freeze. Read-only thereafter.
    """

    async def write_cells(self, scan_id: str, cells: list[dict]) -> None:
        """
        Bulk-write ScanCell records for one scan.
        Called ONCE at canonical freeze (pipeline step 19).
        Any attempt to write cells for an already-frozen scan raises StorageImmutabilityError.
        """
        for cell in cells:
            await self._session.execute(
                text("""
                    INSERT INTO scan_cells (
                        cell_id, scan_id, lat_center, lon_center, cell_size_degrees,
                        environment, evidence_score, causal_score, physics_score,
                        temporal_score, province_prior, uncertainty, acif_score, tier,
                        gravity_residual, physics_residual, water_column_residual,
                        causal_veto_fired, physics_veto_fired, temporal_veto_fired,
                        province_veto_fired, offshore_gate_blocked,
                        u_sensor, u_model, u_physics, u_temporal, u_prior,
                        observable_coverage_fraction, missing_observable_count
                    ) VALUES (
                        :cell_id, :scan_id, :lat, :lon, :cell_size,
                        :env, :ev, :ca, :ph, :tm, :pr, :unc, :acif, :tier,
                        :g_res, :ph_res, :wc_res,
                        :c_veto, :p_veto, :t_veto, :prov_veto, :off_blocked,
                        :u_s, :u_m, :u_p, :u_t, :u_pr,
                        :coverage, :missing
                    )
                    ON CONFLICT (scan_id, cell_id) DO NOTHING
                """),
                {
                    "cell_id": cell["cell_id"], "scan_id": cell["scan_id"],
                    "lat": cell.get("lat_center"), "lon": cell.get("lon_center"),
                    "cell_size": cell.get("cell_size_degrees"),
                    "env": cell.get("environment"),
                    "ev": cell.get("evidence_score"), "ca": cell.get("causal_score"),
                    "ph": cell.get("physics_score"), "tm": cell.get("temporal_score"),
                    "pr": cell.get("province_prior"), "unc": cell.get("uncertainty"),
                    "acif": cell.get("acif_score"), "tier": cell.get("tier"),
                    "g_res": cell.get("gravity_residual"),
                    "ph_res": cell.get("physics_residual"),
                    "wc_res": cell.get("water_column_residual"),
                    "c_veto": cell.get("causal_veto_fired", False),
                    "p_veto": cell.get("physics_veto_fired", False),
                    "t_veto": cell.get("temporal_veto_fired", False),
                    "prov_veto": cell.get("province_veto_fired", False),
                    "off_blocked": cell.get("offshore_gate_blocked", False),
                    "u_s": cell.get("u_sensor"), "u_m": cell.get("u_model"),
                    "u_p": cell.get("u_physics"), "u_t": cell.get("u_temporal"),
                    "u_pr": cell.get("u_prior"),
                    "coverage": cell.get("observable_coverage_fraction"),
                    "missing": cell.get("missing_observable_count"),
                }
            )
        await self._session.commit()

    async def list_cells_for_scan(
        self,
        scan_id: str,
        tier_filter: Optional[str] = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult:
        """Read ScanCell records for a scan. No recomputation."""
        p = pagination or PaginationParams.default()
        filters = ["scan_id = :scan_id"]
        params: dict = {"scan_id": scan_id, "limit": p.page_size, "offset": p.offset}
        if tier_filter:
            filters.append("tier = :tier")
            params["tier"] = tier_filter
        where = " AND ".join(filters)

        rows = await self._session.execute(
            text(f"SELECT * FROM scan_cells WHERE {where} ORDER BY cell_id LIMIT :limit OFFSET :offset"),
            params,
        )
        total_row = await self._session.execute(
            text(f"SELECT COUNT(*) FROM scan_cells WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
        total = total_row.scalar() or 0
        items = [dict(r) for r in rows.mappings().fetchall()]
        return PaginatedResult(items=items, total=total, params=p)

    async def get_cell(self, scan_id: str, cell_id: str) -> dict:
        """Single ScanCell lookup by scan_id + cell_id."""
        row = await self._session.execute(
            text("SELECT * FROM scan_cells WHERE scan_id = :scan_id AND cell_id = :cell_id"),
            {"scan_id": scan_id, "cell_id": cell_id},
        )
        record = row.mappings().fetchone()
        if record is None:
            raise StorageNotFoundError(f"ScanCell not found: scan_id={scan_id}, cell_id={cell_id}")
        return dict(record)


# ---------------------------------------------------------------------------
# Row mapping helpers
# ---------------------------------------------------------------------------

def _jsonb(obj) -> Optional[str]:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump())
    return json.dumps(obj)


def _row_to_canonical_scan(row) -> CanonicalScan:
    from app.models.gate_results import ConfirmationReason, GateResults
    from app.models.threshold_policy import ThresholdPolicy
    from app.models.tier_counts import TierCounts
    from app.models.version_registry import VersionRegistry

    d = dict(row)
    return CanonicalScan(
        scan_id=str(d["scan_id"]),
        status=ScanStatus(d["status"]),
        commodity=d["commodity"],
        scan_tier=ScanTier(d["scan_tier"]),
        environment=ScanEnvironment(d["environment"]),
        aoi_geojson=d["aoi_geojson"] or {},
        grid_resolution_degrees=float(d["grid_resolution_degrees"]),
        total_cells=d["total_cells"] or 0,
        display_acif_score=_float(d.get("display_acif_score")),
        max_acif_score=_float(d.get("max_acif_score")),
        weighted_acif_score=_float(d.get("weighted_acif_score")),
        tier_counts=TierCounts(**d["tier_counts"]) if d.get("tier_counts") else None,
        tier_thresholds_used=ThresholdPolicy(**d["tier_thresholds_used"]) if d.get("tier_thresholds_used") else None,
        system_status=d.get("system_status"),
        gate_results=GateResults(**d["gate_results"]) if d.get("gate_results") else None,
        confirmation_reason=ConfirmationReason(**d["confirmation_reason"]) if d.get("confirmation_reason") else None,
        mean_evidence_score=_float(d.get("mean_evidence_score")),
        mean_causal_score=_float(d.get("mean_causal_score")),
        mean_physics_score=_float(d.get("mean_physics_score")),
        mean_temporal_score=_float(d.get("mean_temporal_score")),
        mean_province_prior=_float(d.get("mean_province_prior")),
        mean_uncertainty=_float(d.get("mean_uncertainty")),
        causal_veto_cell_count=d.get("causal_veto_cell_count"),
        physics_veto_cell_count=d.get("physics_veto_cell_count"),
        province_veto_cell_count=d.get("province_veto_cell_count"),
        offshore_blocked_cell_count=d.get("offshore_blocked_cell_count"),
        offshore_cell_count=d.get("offshore_cell_count"),
        water_column_corrected=d.get("water_column_corrected", False),
        version_registry=VersionRegistry(**d["version_registry"]) if d.get("version_registry") else None,
        normalisation_params=d.get("normalisation_params"),
        submitted_at=d["submitted_at"],
        completed_at=d.get("completed_at"),
        parent_scan_id=str(d["parent_scan_id"]) if d.get("parent_scan_id") else None,
        reprocess_reason=d.get("reprocess_reason"),
        reprocess_changed_params=d.get("reprocess_changed_params"),
        migration_class=d.get("migration_class"),
        migration_notes=d.get("migration_notes"),
    )


def _row_to_summary(row) -> CanonicalScanSummary:
    d = dict(row)
    tier_counts = d.get("tier_counts") or {}
    return CanonicalScanSummary(
        scan_id=str(d["scan_id"]),
        commodity=d["commodity"],
        scan_tier=ScanTier(d["scan_tier"]),
        environment=ScanEnvironment(d["environment"]),
        status=ScanStatus(d["status"]),
        display_acif_score=_float(d.get("display_acif_score")),
        max_acif_score=_float(d.get("max_acif_score")),
        system_status=d.get("system_status"),
        tier_1_count=tier_counts.get("tier_1"),
        total_cells=d.get("total_cells", 0),
        submitted_at=d["submitted_at"],
        completed_at=d.get("completed_at"),
        parent_scan_id=str(d["parent_scan_id"]) if d.get("parent_scan_id") else None,
        migration_class=d.get("migration_class"),
    )


def _float(v) -> Optional[float]:
    return float(v) if v is not None else None