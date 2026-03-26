"""
Aurora OSI vNext — Admin API
Phase O §O.6

ENDPOINT INVENTORY:
  GET   /api/v1/admin/users                — list all users (admin only)
  POST  /api/v1/admin/users                — create new user (admin only)
  PATCH /api/v1/admin/users/{id}/role      — change user role (admin only, audit required)
  GET   /api/v1/admin/audit                — paginated audit log query (admin only)
  GET   /api/v1/admin/audit/{audit_id}     — single audit record (admin only)
  GET   /api/v1/admin/bootstrap-status     — check if bootstrap has run (admin only)

CONSTITUTIONAL RULES — Phase O:
  1. All endpoints require role=admin. HTTP 403 for any other role.
  2. Role changes must be audited BEFORE the change is written.
  3. Audit log is read-only from this API — no delete/update endpoints.
  4. No scientific outputs are accessible through admin endpoints.
  5. No imports from core/*, services/* (scientific modules).

No imports from core/*, services/twin_builder, services/gee, services/gravity, etc.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_model import AuditRecord, UserCreate, UserUpdateRole
from app.models.enums import AuditEventEnum, RoleEnum
from app.security.auth import get_current_user, hash_password, require_admin_user
from app.storage.audit import AuditLogStore
from app.storage.base import PaginationParams, StorageNotFoundError, get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    List all registered users.
    Admin only — HTTP 403 for operator/viewer.
    Returns identity fields only — no scan data, no scientific outputs.
    """
    # Phase P: UserStore.list_users() goes here
    # Phase O: returns in-memory test users
    from app.api.auth import _USERS
    users = [
        {
            "user_id":   u["user_id"],
            "email":     u["email"],
            "full_name": u["full_name"],
            "role":      u["role"].value,
            "is_active": u["is_active"],
        }
        for u in _USERS.values()
    ]
    return {"users": users, "total": len(users)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Create a new user. Admin only.
    New user is created with must_rotate_password=True.
    No audit event for user creation in Phase O — Phase P adds USER_CREATED event.
    """
    import uuid
    from datetime import datetime, timezone
    from app.api.auth import _USERS

    if body.email in _USERS:
        raise HTTPException(status_code=409, detail=f"User {body.email} already exists.")

    user_id = str(uuid.uuid4())
    _USERS[body.email] = {
        "user_id":              user_id,
        "email":                body.email,
        "full_name":            body.full_name,
        "role":                 body.role,
        "password_hash":        hash_password(body.temporary_password),
        "is_active":            True,
        "must_rotate_password": True,
        "created_at":           datetime.now(timezone.utc),
    }
    return {"user_id": user_id, "email": body.email, "must_rotate_password": True}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserUpdateRole,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Change a user's role. Admin only.

    AUDIT REQUIREMENT: ROLE_CHANGED event is written BEFORE the change.
    If the audit write fails, the role change does not proceed.
    """
    from app.api.auth import _USERS

    target = next((u for u in _USERS.values() if u["user_id"] == user_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    old_role = target["role"]
    new_role = body.new_role

    if old_role == new_role:
        return {"user_id": user_id, "role": new_role.value, "changed": False}

    # Audit BEFORE change — required by Phase O
    audit = AuditLogStore(db)
    await audit.append_audit_event(
        event_type=AuditEventEnum.ROLE_CHANGED,
        actor_user_id=current_user.sub,
        actor_email=current_user.email,
        actor_role=current_user.role,
        details={
            "target_user_id": user_id,
            "target_email":   target["email"],
            "old_role":       old_role.value,
            "new_role":       new_role.value,
            "reason":         body.reason,
        },
    )

    # Role change executes after audit is committed
    _USERS[target["email"]]["role"] = new_role
    return {"user_id": user_id, "old_role": old_role.value, "new_role": new_role.value}


# ---------------------------------------------------------------------------
# Audit log read (admin only)
# ---------------------------------------------------------------------------

@router.get("/audit")
async def query_audit_log(
    event_type: Optional[str] = Query(default=None),
    actor_user_id: Optional[str] = Query(default=None),
    scan_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Paginated audit log query. Admin only.

    APPEND-ONLY PROOF: this endpoint only calls AuditLogStore.query_audit_log().
    There is no delete or update endpoint in this router.
    AuditLogStore.update_audit_event() and delete_audit_event() raise
    StorageAuditViolationError unconditionally.
    """
    audit = AuditLogStore(db)
    result = await audit.query_audit_log(
        event_type=event_type,
        actor_user_id=actor_user_id,
        scan_id=scan_id,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    return {
        "events": [_audit_to_dict(r) for r in result.items],
        "total":  result.total,
        "page":   result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    }


@router.get("/audit/{audit_id}")
async def get_audit_record(
    audit_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin_user),
) -> dict:
    """Retrieve a single audit record by ID. Admin only."""
    audit = AuditLogStore(db)
    result = await audit.query_audit_log()
    match = next((r for r in result.items if r.audit_id == audit_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Audit record {audit_id} not found.")
    return _audit_to_dict(match)


# ---------------------------------------------------------------------------
# Bootstrap status (admin only)
# ---------------------------------------------------------------------------

@router.get("/bootstrap-status")
async def bootstrap_status(
    current_user=Depends(require_admin_user),
) -> dict:
    """
    Check whether admin bootstrap has been completed.
    Returns whether any admin user exists and requires rotation.
    """
    from app.api.auth import _USERS
    admins = [u for u in _USERS.values() if u["role"] == RoleEnum.ADMIN]
    return {
        "bootstrap_done": bool(admins),
        "admin_count": len(admins),
        "rotation_pending": any(a.get("must_rotate_password") for a in admins),
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _audit_to_dict(record: AuditRecord) -> dict:
    return {
        "audit_id":      record.audit_id,
        "event_type":    record.event_type.value,
        "actor_user_id": record.actor_user_id,
        "actor_email":   record.actor_email,
        "actor_role":    record.actor_role.value if record.actor_role else None,
        "scan_id":       record.scan_id,
        "details":       record.details,
        "ip_address":    record.ip_address,
        "timestamp":     record.timestamp.isoformat(),
    }