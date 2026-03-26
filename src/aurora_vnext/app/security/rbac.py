"""
Aurora OSI vNext — Role-Based Access Control
Phase O §O.2

Roles (from RoleEnum):
  admin    — full access: all read, write, delete, reprocess, user management, audit
  operator — scan submission, read results, no delete/reprocess/user management
  viewer   — read-only: scan results, datasets, twin queries

RBAC matrix (enforced by FastAPI dependency guards):

  Endpoint category             | admin | operator | viewer
  ───────────────────────────────┼───────┼──────────┼───────
  POST /scan/grid, /polygon      |  ✓    |    ✓     |   ✗
  GET  /scan/status, /active     |  ✓    |    ✓     |   ✓
  POST /scan/{id}/cancel         |  ✓    |    ✗     |   ✗
  GET  /history, /history/{id}   |  ✓    |    ✓     |   ✓
  GET  /history/{id}/cells       |  ✓    |    ✓     |   ✓
  DELETE /history/{id}           |  ✓    |    ✗     |   ✗
  POST /history/{id}/reprocess   |  ✓    |    ✗     |   ✗
  GET  /datasets/*               |  ✓    |    ✓     |   ✓
  GET  /datasets/export/{id}     |  ✓    |    ✗     |   ✗
  GET  /twin/*                   |  ✓    |    ✓     |   ✓
  POST /twin/{id}/query          |  ✓    |    ✓     |   ✓
  POST /auth/login               |  —  (public)     |
  POST /auth/refresh             |  —  (public)     |
  GET  /admin/users              |  ✓    |    ✗     |   ✗
  POST /admin/users              |  ✓    |    ✗     |   ✗
  PATCH /admin/users/{id}/role   |  ✓    |    ✗     |   ✗
  GET  /admin/audit              |  ✓    |    ✗     |   ✗

CONSTITUTIONAL RULE: Security modules never import from core/scoring,
core/tiering, core/gates, or any Phase I/J scientific authority.
These guards only enforce identity and role — they do not touch scan
logic, canonical fields, or pipeline execution.

The guards in this module are thin wrappers re-exporting the dependency
functions from security/auth.py for clean import paths in router modules.
"""

from __future__ import annotations

from app.models.enums import RoleEnum

# Re-export all dependency functions from auth.py for clean router imports
from app.security.auth import (
    get_current_user,
    require_admin_user,
    require_authenticated_user,
    require_operator_or_above,
)

__all__ = [
    "get_current_user",
    "require_authenticated_user",
    "require_admin_user",
    "require_operator_or_above",
    "ROLE_PERMISSIONS",
]

# ---------------------------------------------------------------------------
# Declarative permission registry — used by tests and documentation only
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "scan_submit": {
        "allowed": [RoleEnum.ADMIN.value, RoleEnum.OPERATOR.value],
        "denied":  [RoleEnum.VIEWER.value],
        "guard":   "require_operator_or_above",
    },
    "scan_cancel": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
    "scan_read": {
        "allowed": [RoleEnum.ADMIN.value, RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "denied":  [],
        "guard":   "require_authenticated_user",
    },
    "scan_delete": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
    "scan_reprocess": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
    "dataset_read": {
        "allowed": [RoleEnum.ADMIN.value, RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "denied":  [],
        "guard":   "require_authenticated_user",
    },
    "dataset_export": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
    "twin_read": {
        "allowed": [RoleEnum.ADMIN.value, RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "denied":  [],
        "guard":   "require_authenticated_user",
    },
    "user_management": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
    "audit_log_read": {
        "allowed": [RoleEnum.ADMIN.value],
        "denied":  [RoleEnum.OPERATOR.value, RoleEnum.VIEWER.value],
        "guard":   "require_admin_user",
    },
}