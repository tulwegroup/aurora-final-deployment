"""
Aurora OSI vNext — Canonical Scan Store
Phase G §G.3

WRITE-ONCE after status=COMPLETED.

The canonical freeze contract:
  1. create_pending_scan()   → writes initial record, status=PENDING
  2. freeze_canonical_scan() → single atomic write of all canonical fields
                                + status=COMPLETED
  3. StorageImmutabilityError is raised by both the DB trigger AND this layer
     if freeze is attempted twice on the same scan_id.
  4. get_canonical_scan() → read-only retrieval, always returns frozen state.

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

        Raises StorageImmutabilityError if the scan is already COMPLETED.
        The underlying PostgreSQL trigger provides a second enforcement layer.
        """
        # Application-level pre-check (before hitting DB trigger)
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
        Admin-only soft delete. Does not physically remove the record.
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
        Retrieve a completed CanonicalScan by ID.
        Raises StorageNotFoundError if not found.
        All returned fields are sourced directly from the frozen DB record.
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
# Row mapping helpers
# ---------------------------------------------------------------------------

def _jsonb(obj) -> Optional[str]:
    """Serialise a Pydantic model or dict to a JSON string for JSONB columns."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump())
    return json.dumps(obj)


def _row_to_canonical_scan(row) -> CanonicalScan:
    """Map a raw DB row dict to a CanonicalScan Pydantic model."""
    from app.models.canonical_scan import CanonicalScan
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