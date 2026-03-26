"""
Aurora OSI vNext — Ground Truth Admin API
Phase Z §Z.3

REST endpoints for ground-truth management.

Endpoints:
  POST   /api/v1/gt/records              — submit a new ground-truth record
  GET    /api/v1/gt/records              — list records (with status filter)
  GET    /api/v1/gt/records/{id}         — get record + provenance detail
  POST   /api/v1/gt/records/{id}/approve — approve (admin only)
  POST   /api/v1/gt/records/{id}/reject  — reject with reason (admin only)
  GET    /api/v1/gt/records/{id}/history — full state transition history
  GET    /api/v1/gt/audit                — full audit log (admin only)
  GET    /api/v1/gt/calibration/versions — list calibration versions + lineage
  POST   /api/v1/gt/calibration/versions/{id}/activate — activate draft (admin)
  POST   /api/v1/gt/calibration/versions/{id}/revoke   — revoke (admin)

CONSTITUTIONAL RULES:
  Rule 1: No endpoint deletes or destructively overwrites any record.
          All mutations are status transitions appended to audit log.
  Rule 2: Approve/reject/revoke require admin role — enforced by RBAC.
  Rule 3: No scientific computation in this layer. No ACIF, no tier assignment.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.security.ground_truth_rbac import GTRole, GTPermission, require_permission, PermissionDeniedError
from app.models.ground_truth_model import (
    GroundTruthRecord, GroundTruthStatus, GeologicalDataType,
    GroundTruthProvenance, ConfidenceWeighting, new_record_id,
)
from app.services.ground_truth_ingestion import GroundTruthIngestionService
from app.services.calibration_version import CalibrationVersionManager
from app.storage.ground_truth import GroundTruthStorage
from app.storage.ground_truth_audit import GroundTruthAuditLog
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/gt", tags=["ground_truth"])

# Module-level singletons (replaced by DI in production)
_storage   = GroundTruthStorage()
_audit_log = GroundTruthAuditLog()
_ingestion = GroundTruthIngestionService(_storage)
_cal_mgr   = CalibrationVersionManager(_storage)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ProvenanceIn(BaseModel):
    source_name:        str
    source_identifier:  str
    country:            str
    commodity:          str
    license_note:       str

    class Config:
        extra = "forbid"


class ConfidenceIn(BaseModel):
    source_confidence:           float
    spatial_accuracy:            float
    temporal_relevance:          float
    geological_context_strength: float

    class Config:
        extra = "forbid"


class SubmitRecordRequest(BaseModel):
    geological_data_type: str
    provenance:           ProvenanceIn
    confidence:           ConfidenceIn
    lat:                  Optional[float] = None
    lon:                  Optional[float] = None
    depth_m:              Optional[float] = None
    data_payload:         dict = {}

    class Config:
        extra = "forbid"


class ApproveRejectRequest(BaseModel):
    reason: Optional[str] = None


class RevokeRequest(BaseModel):
    reason: str


# ---------------------------------------------------------------------------
# Helper: resolve role from header (simplified; replace with real auth in prod)
# ---------------------------------------------------------------------------

def _get_role(x_actor_role: Optional[str]) -> GTRole:
    try:
        return GTRole(x_actor_role or "viewer")
    except ValueError:
        return GTRole.VIEWER


def _get_actor(x_actor_id: Optional[str]) -> str:
    return x_actor_id or "anonymous"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/records", status_code=201)
async def submit_record(
    body: SubmitRecordRequest,
    x_actor_role: Optional[str] = Header(default=None),
    x_actor_id:   Optional[str] = Header(default=None),
):
    """
    Submit a new ground-truth record for review.
    operator or admin role required.
    """
    role   = _get_role(x_actor_role)
    actor  = _get_actor(x_actor_id)
    try:
        require_permission(role, GTPermission.SUBMIT)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    from datetime import datetime
    try:
        geo_type = GeologicalDataType(body.geological_data_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown geological_data_type: {body.geological_data_type!r}")

    provenance = GroundTruthProvenance(
        source_name       = body.provenance.source_name,
        source_identifier = body.provenance.source_identifier,
        country           = body.provenance.country,
        commodity         = body.provenance.commodity,
        license_note      = body.provenance.license_note,
        ingestion_timestamp = datetime.utcnow().isoformat(),
    )
    confidence = ConfidenceWeighting(**body.confidence.dict())
    record = GroundTruthRecord(
        record_id            = new_record_id(),
        geological_data_type = geo_type,
        provenance           = provenance,
        confidence           = confidence,
        is_synthetic         = False,   # API submissions are never synthetic
        lat                  = body.lat,
        lon                  = body.lon,
        depth_m              = body.depth_m,
        data_payload         = body.data_payload,
    )

    result = _ingestion.ingest_one(record)
    if not result.success:
        raise HTTPException(status_code=422, detail=result.rejection_reason)

    _audit_log.make_entry(
        actor_id=actor, actor_role=role.value,
        action="submitted", record_id=record.record_id,
        to_status=GroundTruthStatus.PENDING.value,
    )
    return {"record_id": record.record_id, "status": "pending", "warnings": result.warnings}


@router.get("/records")
async def list_records(
    status: Optional[str] = None,
    commodity: Optional[str] = None,
    x_actor_role: Optional[str] = Header(default=None),
):
    role = _get_role(x_actor_role)
    try:
        require_permission(role, GTPermission.READ)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    records = _storage.list_all()
    if status:
        records = [r for r in records if r.status.value == status]
    if commodity:
        records = [r for r in records if r.provenance.commodity == commodity]

    return [
        {
            "record_id":            r.record_id,
            "geological_data_type": r.geological_data_type.value,
            "status":               r.status.value,
            "commodity":            r.provenance.commodity,
            "country":              r.provenance.country,
            "source_name":          r.provenance.source_name,
            "confidence_composite": round(r.confidence.composite, 4),
        }
        for r in records
    ]


@router.get("/records/{record_id}")
async def get_record(record_id: str, x_actor_role: Optional[str] = Header(default=None)):
    role = _get_role(x_actor_role)
    try:
        require_permission(role, GTPermission.READ)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    record = _storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return {
        "record_id":            record.record_id,
        "geological_data_type": record.geological_data_type.value,
        "status":               record.status.value,
        "is_synthetic":         record.is_synthetic,
        "lat": record.lat, "lon": record.lon, "depth_m": record.depth_m,
        "provenance": {
            "source_name":        record.provenance.source_name,
            "source_identifier":  record.provenance.source_identifier,
            "country":            record.provenance.country,
            "commodity":          record.provenance.commodity,
            "license_note":       record.provenance.license_note,
            "ingestion_timestamp": record.provenance.ingestion_timestamp,
        },
        "confidence": {
            "source_confidence":           record.confidence.source_confidence,
            "spatial_accuracy":            record.confidence.spatial_accuracy,
            "temporal_relevance":          record.confidence.temporal_relevance,
            "geological_context_strength": record.confidence.geological_context_strength,
            "composite":                   round(record.confidence.composite, 4),
        },
        "data_payload":    record.data_payload,
        "rejection_reason": record.rejection_reason,
        "superseded_by":   record.superseded_by,
    }


@router.post("/records/{record_id}/approve")
async def approve_record(
    record_id: str, body: ApproveRejectRequest,
    x_actor_role: Optional[str] = Header(default=None),
    x_actor_id:   Optional[str] = Header(default=None),
):
    """Approve a PENDING record. Admin only."""
    role  = _get_role(x_actor_role)
    actor = _get_actor(x_actor_id)
    try:
        require_permission(role, GTPermission.APPROVE)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    record = _storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record.status != GroundTruthStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Record is {record.status.value}, not PENDING")

    updated = _storage.transition_status(record_id, GroundTruthStatus.APPROVED)
    _audit_log.make_entry(
        actor_id=actor, actor_role=role.value, action="approved",
        record_id=record_id,
        from_status=GroundTruthStatus.PENDING.value,
        to_status=GroundTruthStatus.APPROVED.value,
        reason=body.reason,
    )
    return {"record_id": record_id, "status": updated.status.value}


@router.post("/records/{record_id}/reject")
async def reject_record(
    record_id: str, body: ApproveRejectRequest,
    x_actor_role: Optional[str] = Header(default=None),
    x_actor_id:   Optional[str] = Header(default=None),
):
    """Reject a PENDING record. Admin only. reason required."""
    role  = _get_role(x_actor_role)
    actor = _get_actor(x_actor_id)
    try:
        require_permission(role, GTPermission.APPROVE)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="Rejection reason is required.")

    record = _storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    updated = _storage.transition_status(
        record_id, GroundTruthStatus.REJECTED, rejection_reason=body.reason
    )
    _audit_log.make_entry(
        actor_id=actor, actor_role=role.value, action="rejected",
        record_id=record_id,
        from_status=record.status.value,
        to_status=GroundTruthStatus.REJECTED.value,
        reason=body.reason,
    )
    return {"record_id": record_id, "status": updated.status.value}


@router.get("/records/{record_id}/history")
async def record_history(record_id: str, x_actor_role: Optional[str] = Header(default=None)):
    role = _get_role(x_actor_role)
    try:
        require_permission(role, GTPermission.READ)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    entries = _audit_log.entries_for(record_id)
    return [
        {
            "entry_id":    e.entry_id,
            "action":      e.action,
            "actor_id":    e.actor_id,
            "actor_role":  e.actor_role,
            "from_status": e.from_status,
            "to_status":   e.to_status,
            "reason":      e.reason,
            "occurred_at": e.occurred_at,
        }
        for e in entries
    ]


@router.get("/audit")
async def full_audit_log(x_actor_role: Optional[str] = Header(default=None)):
    """Full audit log. Admin only."""
    role = _get_role(x_actor_role)
    try:
        require_permission(role, GTPermission.VIEW_AUDIT_LOG)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return [
        {
            "entry_id": e.entry_id, "action": e.action,
            "actor_id": e.actor_id, "actor_role": e.actor_role,
            "record_id": e.record_id,
            "from_status": e.from_status, "to_status": e.to_status,
            "reason": e.reason, "occurred_at": e.occurred_at,
        }
        for e in _audit_log.all_entries()
    ]


@router.get("/calibration/versions")
async def list_calibration_versions(x_actor_role: Optional[str] = Header(default=None)):
    role = _get_role(x_actor_role)
    try:
        require_permission(role, GTPermission.READ)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    versions = _storage.list_versions()
    return [
        {
            "version_id":               v.version_id,
            "parent_version_id":        v.parent_version_id,
            "description":              v.description,
            "status":                   v.status.value,
            "applies_to_scans_after":   v.applies_to_scans_after,
            "calibration_effect_flags": list(v.calibration_effect_flags),
            "ground_truth_record_ids":  list(v.ground_truth_record_ids),
            "created_by":               v.created_by,
            "created_at":               v.created_at,
            "rationale":                v.rationale,
        }
        for v in versions
    ]


@router.post("/calibration/versions/{version_id}/activate")
async def activate_calibration_version(
    version_id: str,
    x_actor_role: Optional[str] = Header(default=None),
    x_actor_id:   Optional[str] = Header(default=None),
):
    """Activate a DRAFT calibration version. Admin only."""
    role  = _get_role(x_actor_role)
    actor = _get_actor(x_actor_id)
    try:
        require_permission(role, GTPermission.APPROVE)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        activated = _cal_mgr.activate(version_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _audit_log.make_entry(
        actor_id=actor, actor_role=role.value, action="calibration_activated",
        record_id=version_id, to_status="active",
        from_status="draft",
    )
    return {"version_id": activated.version_id, "status": activated.status.value,
            "applies_to_scans_after": activated.applies_to_scans_after}


@router.post("/calibration/versions/{version_id}/revoke")
async def revoke_calibration_version(
    version_id: str, body: RevokeRequest,
    x_actor_role: Optional[str] = Header(default=None),
    x_actor_id:   Optional[str] = Header(default=None),
):
    """Revoke a calibration version. Admin only. Lineage preserved."""
    role  = _get_role(x_actor_role)
    actor = _get_actor(x_actor_id)
    try:
        require_permission(role, GTPermission.REVOKE)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        revoked = _cal_mgr.revoke(version_id, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    _audit_log.make_entry(
        actor_id=actor, actor_role=role.value, action="calibration_revoked",
        record_id=version_id, to_status="revoked", reason=body.reason,
    )
    return {"version_id": revoked.version_id, "status": revoked.status.value}