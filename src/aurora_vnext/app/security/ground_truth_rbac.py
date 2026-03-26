"""
Aurora OSI vNext — Ground Truth RBAC
Phase Z §Z.1

Role-based access control for ground-truth management operations.

Roles:
  viewer   — read-only: list and inspect records and provenance
  operator — upload/submit new records; cannot approve/reject
  admin    — approve/reject, revoke, manage all records

CONSTITUTIONAL RULE: No role grants the ability to delete or destructively
edit a ground-truth record. All mutations are append-only state transitions.
"""

from __future__ import annotations

from enum import Enum


class GTRole(str, Enum):
    VIEWER   = "viewer"
    OPERATOR = "operator"
    ADMIN    = "admin"


class GTPermission(str, Enum):
    READ            = "read"
    SUBMIT          = "submit"       # upload / ingest
    APPROVE         = "approve"      # approve / reject
    REVOKE          = "revoke"       # revoke a calibration version
    VIEW_AUDIT_LOG  = "view_audit_log"


_ROLE_PERMISSIONS: dict[GTRole, set[GTPermission]] = {
    GTRole.VIEWER:   {GTPermission.READ},
    GTRole.OPERATOR: {GTPermission.READ, GTPermission.SUBMIT},
    GTRole.ADMIN:    {
        GTPermission.READ, GTPermission.SUBMIT,
        GTPermission.APPROVE, GTPermission.REVOKE,
        GTPermission.VIEW_AUDIT_LOG,
    },
}


class PermissionDeniedError(PermissionError):
    """Raised when a role attempts an operation it is not permitted to perform."""


def require_permission(role: GTRole, permission: GTPermission) -> None:
    """
    Assert that the given role has the required permission.
    Raises PermissionDeniedError if not.
    """
    allowed = _ROLE_PERMISSIONS.get(role, set())
    if permission not in allowed:
        raise PermissionDeniedError(
            f"Role {role.value!r} does not have permission {permission.value!r}. "
            f"Permitted operations for this role: {[p.value for p in allowed]}"
        )


def has_permission(role: GTRole, permission: GTPermission) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, set())