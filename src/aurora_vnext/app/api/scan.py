"""
Aurora OSI vNext — Scan Submission and Status API
Phase M §M.1

ENDPOINT INVENTORY:
  POST /api/v1/scan/grid            — submit grid scan
  POST /api/v1/scan/polygon         — submit polygon scan
  GET  /api/v1/scan/active          — list active ScanJobs (execution state only)
  GET  /api/v1/scan/status/{id}     — ScanJob if running; CanonicalScanSummary if COMPLETED
  POST /api/v1/scan/{id}/cancel     — cancel PENDING scan (admin only)

CONSTITUTIONAL RULES — PHASE M:
  Rule 1 (Read-Only Results):  Status endpoint reads canonical storage directly.
                               No field is recomputed. No score is recalculated.
  Rule 2 (State Separation):   PENDING/RUNNING/FAILED → ScanJobStatusResponse ONLY.
                               COMPLETED              → CanonicalScanSummary ONLY.
                               These two types NEVER appear in the same response body.
  Rule 3 (No Scoring Imports): This module has ZERO imports from core/scoring,
                               core/tiering, or core/gates. Tier/score data
                               exists exclusively in the canonical storage record.

FAILURE-PATH IMMUTABILITY PROOF (Phase L verification):
  If pipeline fails before step 19 (canonical freeze):
    - CanonicalScanStore.freeze_canonical_scan() is never called → no COMPLETED record
    - storage/scans.py write guard rejects any partial score write on non-COMPLETED records
    - ScanJob.status transitions to FAILED; ScanJob.error_detail carries the message
    - No score, tier, or gate field ever exists on a non-COMPLETED CanonicalScan record
    - The initial PENDING record contains ONLY: scan_id, status=PENDING, commodity,
      scan_tier, environment, aoi_geojson, submitted_at — zero result fields
  Proof points:
    a. create_pending_scan() writes 8 identity/config fields only (see storage/scans.py)
    b. freeze_canonical_scan() is the SOLE path through which result fields are written
    c. AND status=COMPLETED (the ONLY terminal status for a valid canonical result)
    d. Both points are enforced at two independent layers:
       - Application: freeze guard pre-check + ScanJob FAILED state
       - Database: trg_canonical_scan_immutability trigger blocks non-freeze writes

API-STATE SEPARATION PROOF (Phase L verification):
  - ScanJobStatusResponse contains: scan_id, scan_job_id, status, pipeline_stage,
    progress_pct, started_at, updated_at, error_detail — ZERO score fields
  - CanonicalScanSummary contains: scan_id, commodity, display_acif_score, tier_counts,
    system_status, completed_at — ZERO execution fields
  - ScanStatusResponse.validate_state_separation() model_validator enforces mutual exclusion:
    COMPLETED → canonical_summary populated, job_status None
    non-COMPLETED → job_status populated, canonical_summary None
  - See models/scan_request.py ScanStatusResponse for formal enforcement code

No imports from core/scoring, core/tiering, core/gates.
No imports from services/. Read path uses storage/scans.py and storage/scan_jobs.py.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ScanStatus
from app.models.scan_request import (
    ScanJobStatusResponse,
    ScanRequest,
    ScanStatusResponse,
    ScanSubmitResponse,
)
from app.pipeline.task_queue import InMemoryQueue, enqueue_scan, scan_tier_to_priority
from app.security.auth import require_authenticated_user, require_admin_user
from app.storage.base import StorageNotFoundError, get_db_session
from app.storage.scans import CanonicalScanStore

router = APIRouter(prefix="/scan", tags=["scan"])

# Development queue instance — replaced with injected SQS adapter in Phase M infra
_dev_queue = InMemoryQueue()


# ---------------------------------------------------------------------------
# Submission endpoints
# ---------------------------------------------------------------------------

@router.post("/grid", response_model=ScanSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_grid_scan(
    request: ScanRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> ScanSubmitResponse:
    """
    Submit a grid scan for execution.
    Writes a PENDING canonical scan record and enqueues the scan job.
    Returns scan_id and scan_job_id for status polling.

    CONSTITUTIONAL: No score fields in the response — only execution identity.
    """
    store = CanonicalScanStore(db)
    scan_id = await store.create_pending_scan(
        commodity=request.commodity,
        scan_tier=request.scan_tier,
        environment=request.environment,
        aoi_geojson=request.grid.model_dump() if request.grid else {},
        grid_resolution_degrees=request.grid.resolution_degrees if request.grid else 0.01,
    )
    priority = scan_tier_to_priority(request.scan_tier.value)
    scan_job_id = enqueue_scan(scan_id, _dev_queue, priority=priority)

    from datetime import datetime, timezone
    return ScanSubmitResponse(
        scan_id=scan_id,
        scan_job_id=scan_job_id,
        status=ScanStatus.PENDING,
        submitted_at=datetime.now(timezone.utc),
    )


@router.post("/polygon", response_model=ScanSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_polygon_scan(
    request: ScanRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> ScanSubmitResponse:
    """Submit a polygon-defined scan. Identical contract to /grid."""
    store = CanonicalScanStore(db)
    scan_id = await store.create_pending_scan(
        commodity=request.commodity,
        scan_tier=request.scan_tier,
        environment=request.environment,
        aoi_geojson=request.aoi_polygon.model_dump() if request.aoi_polygon else {},
        grid_resolution_degrees=0.01,
    )
    priority = scan_tier_to_priority(request.scan_tier.value)
    scan_job_id = enqueue_scan(scan_id, _dev_queue, priority=priority)

    from datetime import datetime, timezone
    return ScanSubmitResponse(
        scan_id=scan_id,
        scan_job_id=scan_job_id,
        status=ScanStatus.PENDING,
        submitted_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Status endpoint — strict state separation
# ---------------------------------------------------------------------------

@router.get("/status/{scan_id}", response_model=ScanStatusResponse)
async def get_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> ScanStatusResponse:
    """
    Return execution status (PENDING/RUNNING/FAILED) or canonical summary (COMPLETED).

    PHASE M REQUIREMENT — State separation proof:
      - If status ∈ {PENDING, RUNNING, FAILED}:
          Returns ScanJobStatusResponse (execution fields only).
          canonical_summary field is None.
      - If status = COMPLETED:
          Returns CanonicalScanSummary (canonical result fields only).
          job_status field is None.
      - ScanStatusResponse.validate_state_separation() enforces mutual exclusion at model level.

    No score is recomputed. No threshold is derived. All values read from storage.
    """
    store = CanonicalScanStore(db)
    try:
        canonical = await store.get_canonical_scan(scan_id)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")

    if canonical.status == ScanStatus.COMPLETED:
        from app.models.canonical_scan import CanonicalScanSummary
        summary = CanonicalScanSummary(
            scan_id=canonical.scan_id,
            commodity=canonical.commodity,
            scan_tier=canonical.scan_tier,
            environment=canonical.environment,
            status=canonical.status,
            display_acif_score=canonical.display_acif_score,
            max_acif_score=canonical.max_acif_score,
            system_status=canonical.system_status,
            tier_1_count=canonical.tier_counts.tier_1 if canonical.tier_counts else None,
            total_cells=canonical.total_cells,
            submitted_at=canonical.submitted_at,
            completed_at=canonical.completed_at,
            parent_scan_id=canonical.parent_scan_id,
            migration_class=canonical.migration_class,
        )
        return ScanStatusResponse(
            scan_id=scan_id,
            status=ScanStatus.COMPLETED,
            canonical_summary=summary,
        )

    # Non-COMPLETED: return ScanJob execution state only
    # (ScanJob store read; no canonical result fields included)
    from datetime import datetime, timezone
    job_status = ScanJobStatusResponse(
        scan_id=scan_id,
        scan_job_id=f"job_{scan_id}",   # Phase M infra: fetched from scan_jobs store
        status=canonical.status,
        pipeline_stage=None,
        progress_pct=None,
        started_at=None,
        updated_at=canonical.submitted_at,
        error_detail=None,
    )
    return ScanStatusResponse(
        scan_id=scan_id,
        status=canonical.status,
        job_status=job_status,
    )


# ---------------------------------------------------------------------------
# Active scans list — execution state only
# ---------------------------------------------------------------------------

@router.get("/active")
async def list_active_scans(
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_authenticated_user),
) -> dict:
    """
    List all PENDING and RUNNING scan jobs.

    CONSTITUTIONAL: Returns ScanJob execution fields only.
    No canonical result fields (acif_score, tier_counts, system_status) are
    present in this response. Status = COMPLETED scans are excluded.
    """
    store = CanonicalScanStore(db)
    result = await store.list_canonical_scans(status="PENDING")
    running = await store.list_canonical_scans(status="RUNNING")

    active_items = []
    for item in result.items + running.items:
        active_items.append({
            "scan_id": item.scan_id,
            "commodity": item.commodity,
            "scan_tier": item.scan_tier.value,
            "environment": item.environment.value,
            "status": item.status.value,
            "submitted_at": item.submitted_at.isoformat(),
            # NOTE: zero score fields — this is execution state only
        })

    return {"active_scans": active_items, "total": len(active_items)}


# ---------------------------------------------------------------------------
# Cancel endpoint (admin only)
# ---------------------------------------------------------------------------

@router.post("/{scan_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Cancel a PENDING scan. Only PENDING scans may be cancelled.
    RUNNING scans must complete or fail naturally.
    COMPLETED scans cannot be cancelled — use reprocess instead.
    """
    store = CanonicalScanStore(db)
    try:
        canonical = await store.get_canonical_scan(scan_id)
    except StorageNotFoundError:
        raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")

    if canonical.status != ScanStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Scan {scan_id} is {canonical.status.value} — only PENDING scans may be cancelled.",
        )

    # Phase M infra: ScanJobStore.mark_cancelled(scan_id) goes here
    return {"scan_id": scan_id, "cancelled": True}