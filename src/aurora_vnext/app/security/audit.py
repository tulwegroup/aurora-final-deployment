"""
Aurora OSI vNext — Security Audit Event Emitter
Phase O §O.4

Emits typed security audit events for all Phase O required categories.
Delegates persistence to storage/audit.py AuditLogStore — this module
only builds event payloads and calls append_audit_event().

PHASE O REQUIRED AUDIT EVENTS (all implemented here):
  1. LOGIN_SUCCESS        — successful credential verification
  2. LOGIN_FAILURE        — failed credential verification (wrong password / unknown user)
  3. SCAN_SUBMITTED       — scan enqueued after POST /scan/grid or /scan/polygon
  4. SCAN_DELETED         — soft delete executed via DELETE /history/{id}
  5. SCAN_REPROCESSED     — reprocess initiated via POST /history/{id}/reprocess
  6. THRESHOLD_POLICY_CHANGED — threshold/config change (admin only)
  7. ROLE_CHANGED         — user role updated via PATCH /admin/users/{id}/role
  8. DATA_EXPORTED        — GET /datasets/export/{id} executed
  9. ADMIN_BOOTSTRAPPED   — bootstrap admin created on first deployment
  10. LOGOUT              — explicit logout (token revocation)

APPEND-ONLY PROOF:
  - append_audit_event() is the ONLY write method on AuditLogStore.
  - update_audit_event() and delete_audit_event() explicitly raise
    StorageAuditViolationError (see storage/audit.py).
  - PostgreSQL RLS blocks UPDATE and DELETE on the audit_log table for ALL roles.
  - This module only calls append_audit_event() — never update or delete.
  - Verified structurally: no UPDATE/DELETE SQL in storage/audit.py append path.

CONSTITUTIONAL RULE: This module never imports from core/scoring, core/tiering,
core/gates, or any scientific authority. Security audit events carry identity
and action metadata only — no score, tier, or gate data.
"""

from __future__ import annotations

from typing import Optional

from app.models.enums import AuditEventEnum, RoleEnum
from app.storage.audit import AuditLogStore


# ---------------------------------------------------------------------------
# Login events
# ---------------------------------------------------------------------------

async def audit_login_success(
    store: AuditLogStore,
    user_id: str,
    email: str,
    role: RoleEnum,
    ip_address: Optional[str] = None,
) -> None:
    """Append LOGIN_SUCCESS event — successful credential verification."""
    await store.append_audit_event(
        event_type=AuditEventEnum.LOGIN_SUCCESS,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=role,
        details={"method": "password"},
        ip_address=ip_address,
    )


async def audit_login_failure(
    store: AuditLogStore,
    attempted_email: str,
    reason: str,
    ip_address: Optional[str] = None,
) -> None:
    """
    Append LOGIN_FAILURE event — failed credential verification.

    NOTE: actor_user_id is NOT set (user may not exist).
    actor_email carries the attempted email for security monitoring.
    reason must NOT include the supplied password — only 'wrong_password'
    or 'unknown_user' labels are accepted.
    """
    safe_reason = reason if reason in ("wrong_password", "unknown_user", "account_inactive") else "unknown"
    await store.append_audit_event(
        event_type=AuditEventEnum.LOGIN_FAILURE,
        actor_email=attempted_email,
        details={"reason": safe_reason},
        ip_address=ip_address,
    )


async def audit_logout(
    store: AuditLogStore,
    user_id: str,
    email: str,
    role: RoleEnum,
    jti: str,
    ip_address: Optional[str] = None,
) -> None:
    """Append LOGOUT event — explicit token revocation."""
    await store.append_audit_event(
        event_type=AuditEventEnum.LOGOUT,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=role,
        details={"revoked_jti": jti},
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Scan events
# ---------------------------------------------------------------------------

async def audit_scan_submitted(
    store: AuditLogStore,
    user_id: str,
    email: str,
    role: RoleEnum,
    scan_id: str,
    commodity: str,
    scan_tier: str,
    ip_address: Optional[str] = None,
) -> None:
    """Append SCAN_SUBMITTED event — scan enqueued for execution."""
    await store.append_audit_event(
        event_type=AuditEventEnum.SCAN_SUBMITTED,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=role,
        scan_id=scan_id,
        details={"commodity": commodity, "scan_tier": scan_tier},
        ip_address=ip_address,
    )


async def audit_scan_deleted(
    store: AuditLogStore,
    user_id: str,
    email: str,
    role: RoleEnum,
    scan_id: str,
    reason: str,
    ip_address: Optional[str] = None,
) -> None:
    """Append SCAN_DELETED event — must be written BEFORE soft delete executes."""
    await store.append_audit_event(
        event_type=AuditEventEnum.SCAN_DELETED,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=role,
        scan_id=scan_id,
        details={"reason": reason},
        ip_address=ip_address,
    )


async def audit_scan_reprocessed(
    store: AuditLogStore,
    user_id: str,
    email: str,
    role: RoleEnum,
    parent_scan_id: str,
    new_scan_id: str,
    changed_params: dict,
    reason: str,
    ip_address: Optional[str] = None,
) -> None:
    """Append SCAN_REPROCESSED event — reprocess initiated."""
    await store.append_audit_event(
        event_type=AuditEventEnum.SCAN_REPROCESSED,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=role,
        scan_id=parent_scan_id,
        details={
            "parent_scan_id":  parent_scan_id,
            "new_scan_id":     new_scan_id,
            "changed_params":  changed_params,
            "reason":          reason,
        },
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Config / policy change events
# ---------------------------------------------------------------------------

async def audit_threshold_policy_changed(
    store: AuditLogStore,
    user_id: str,
    email: str,
    scan_id: str,
    old_policy: dict,
    new_policy: dict,
    ip_address: Optional[str] = None,
) -> None:
    """Append THRESHOLD_POLICY_CHANGED event — config/policy updated."""
    await store.append_audit_event(
        event_type=AuditEventEnum.THRESHOLD_POLICY_CHANGED,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=RoleEnum.ADMIN,
        scan_id=scan_id,
        details={"old_policy": old_policy, "new_policy": new_policy},
        ip_address=ip_address,
    )


async def audit_role_changed(
    store: AuditLogStore,
    admin_user_id: str,
    admin_email: str,
    target_user_id: str,
    target_email: str,
    old_role: RoleEnum,
    new_role: RoleEnum,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Append ROLE_CHANGED event — user role updated."""
    await store.append_audit_event(
        event_type=AuditEventEnum.ROLE_CHANGED,
        actor_user_id=admin_user_id,
        actor_email=admin_email,
        actor_role=RoleEnum.ADMIN,
        details={
            "target_user_id": target_user_id,
            "target_email":   target_email,
            "old_role":       old_role.value,
            "new_role":       new_role.value,
            "reason":         reason,
        },
        ip_address=ip_address,
    )


async def audit_data_exported(
    store: AuditLogStore,
    user_id: str,
    email: str,
    scan_id: str,
    export_format: str,
    ip_address: Optional[str] = None,
) -> None:
    """Append DATA_EXPORTED event — export executed."""
    await store.append_audit_event(
        event_type=AuditEventEnum.DATA_EXPORTED,
        actor_user_id=user_id,
        actor_email=email,
        actor_role=RoleEnum.ADMIN,
        scan_id=scan_id,
        details={"format": export_format},
        ip_address=ip_address,
    )


# ---------------------------------------------------------------------------
# Bootstrap event
# ---------------------------------------------------------------------------

async def audit_admin_bootstrapped(
    store: AuditLogStore,
    admin_email: str,
    ip_address: Optional[str] = None,
) -> None:
    """
    Append ADMIN_BOOTSTRAPPED event — written once on first deployment.
    Written before the admin user record is persisted.
    """
    await store.append_audit_event(
        event_type=AuditEventEnum.ADMIN_BOOTSTRAPPED,
        actor_email=admin_email,
        actor_role=RoleEnum.ADMIN,
        details={"must_rotate": True},
        ip_address=ip_address,
    )