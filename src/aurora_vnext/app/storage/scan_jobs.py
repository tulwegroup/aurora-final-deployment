"""
Aurora OSI vNext — Scan Job Store
Phase G §G.2

MUTABLE store for pipeline execution state.
Completely separate from canonical_scans — carries ZERO score fields.

ScanJob records are:
  - CREATED when pipeline starts (status=PENDING)
  - UPDATED throughout execution (RUNNING, stage changes, progress)
  - ARCHIVED (is_archived=True) after canonical freeze — NOT deleted
  - Archived records are preserved for pipeline debugging and audit trails
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PipelineStageEnum, ScanStatus
from app.models.scan_job import ScanJob
from app.storage.base import BaseStore, StorageNotFoundError


class ScanJobStore(BaseStore):

    async def create_scan_job(self, scan_id_ref: str) -> ScanJob:
        """Create a new PENDING scan job for the given scan_id_ref."""
        job_id = str(uuid4())
        await self._session.execute(
            text("""
                INSERT INTO scan_jobs (
                    scan_job_id, scan_id_ref, status, created_at, updated_at
                ) VALUES (
                    :job_id, :scan_id_ref, 'PENDING', NOW(), NOW()
                )
            """),
            {"job_id": job_id, "scan_id_ref": scan_id_ref},
        )
        await self._session.commit()
        return await self.get_scan_job(job_id)

    async def update_scan_job_status(
        self,
        job_id: str,
        status: ScanStatus,
        pipeline_stage: Optional[PipelineStageEnum] = None,
        progress_pct: Optional[float] = None,
        error_detail: Optional[str] = None,
        error_stage: Optional[PipelineStageEnum] = None,
    ) -> ScanJob:
        """Update pipeline execution state. Never touches score fields."""
        params: dict = {
            "job_id": job_id,
            "status": status.value,
            "pipeline_stage": pipeline_stage.value if pipeline_stage else None,
            "progress_pct": progress_pct,
            "error_detail": error_detail,
            "error_stage": error_stage.value if error_stage else None,
        }
        set_clauses = ["status = :status", "updated_at = NOW()"]
        if pipeline_stage is not None:
            set_clauses.append("pipeline_stage = :pipeline_stage")
        if progress_pct is not None:
            set_clauses.append("progress_pct = :progress_pct")
        if error_detail is not None:
            set_clauses.append("error_detail = :error_detail")
        if error_stage is not None:
            set_clauses.append("error_stage = :error_stage")
        if status == ScanStatus.RUNNING:
            set_clauses.append("started_at = COALESCE(started_at, NOW())")
        if status in (ScanStatus.COMPLETED, ScanStatus.FAILED):
            set_clauses.append("completed_at = NOW()")

        await self._session.execute(
            text(f"UPDATE scan_jobs SET {', '.join(set_clauses)} WHERE scan_job_id = :job_id"),
            params,
        )
        await self._session.commit()
        return await self.get_scan_job(job_id)

    async def archive_scan_job(self, job_id: str) -> None:
        """
        Archive a scan job after canonical freeze.
        Archived jobs are excluded from active job lists but preserved for audit.
        """
        await self._session.execute(
            text("UPDATE scan_jobs SET is_archived = TRUE, updated_at = NOW() WHERE scan_job_id = :job_id"),
            {"job_id": job_id},
        )
        await self._session.commit()

    async def get_scan_job(self, job_id: str) -> ScanJob:
        row = await self._session.execute(
            text("SELECT * FROM scan_jobs WHERE scan_job_id = :job_id"),
            {"job_id": job_id},
        )
        record = row.mappings().fetchone()
        if record is None:
            raise StorageNotFoundError(f"ScanJob not found: job_id={job_id}")
        return _row_to_scan_job(record)

    async def get_active_jobs(self, limit: int = 50) -> list[ScanJob]:
        """Return all non-archived, non-completed jobs."""
        rows = await self._session.execute(
            text("""
                SELECT * FROM scan_jobs
                WHERE is_archived = FALSE
                  AND status NOT IN ('COMPLETED', 'FAILED')
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [_row_to_scan_job(r) for r in rows.mappings().fetchall()]

    async def get_job_for_scan(self, scan_id_ref: str) -> Optional[ScanJob]:
        """Get the most recent job for a given scan_id_ref."""
        row = await self._session.execute(
            text("""
                SELECT * FROM scan_jobs
                WHERE scan_id_ref = :scan_id_ref
                ORDER BY created_at DESC LIMIT 1
            """),
            {"scan_id_ref": scan_id_ref},
        )
        record = row.mappings().fetchone()
        return _row_to_scan_job(record) if record else None


def _row_to_scan_job(row) -> ScanJob:
    d = dict(row)
    return ScanJob(
        scan_job_id=str(d["scan_job_id"]),
        scan_id_ref=str(d["scan_id_ref"]),
        status=ScanStatus(d["status"]),
        pipeline_stage=PipelineStageEnum(d["pipeline_stage"]) if d.get("pipeline_stage") else None,
        progress_pct=float(d["progress_pct"]) if d.get("progress_pct") is not None else None,
        created_at=d["created_at"],
        started_at=d.get("started_at"),
        updated_at=d["updated_at"],
        completed_at=d.get("completed_at"),
        error_detail=d.get("error_detail"),
        error_stage=PipelineStageEnum(d["error_stage"]) if d.get("error_stage") else None,
        is_archived=d.get("is_archived", False),
    )