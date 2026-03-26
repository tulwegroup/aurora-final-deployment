"""
Aurora OSI vNext — Audit Log Store
Phase G §G.6

APPEND-ONLY. Two independent enforcement layers:
  1. PostgreSQL RLS (row-level security): UPDATE and DELETE blocked for ALL roles
  2. This class: raises StorageAuditViolationError if update/delete attempted

No data is ever removed from the audit log. Audit records are permanent.
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_model import AuditRecord
from app.models.enums import AuditEventEnum, RoleEnum
from app.storage.base import BaseStore, PaginatedResult, PaginationParams, StorageAuditViolationError


class AuditLogStore(BaseStore):

    async def append_audit_event(
        self,
        event_type: AuditEventEnum,
        actor_user_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[RoleEnum] = None,
        scan_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditRecord:
        """
        Append one audit event. This is the ONLY write path into the audit log.
        Returns the written AuditRecord for confirmation.
        """
        audit_id = str(uuid4())
        await self._session.execute(
            text("""
                INSERT INTO audit_log (
                    audit_id, event_type, actor_user_id, actor_email,
                    actor_role, scan_id, details, ip_address, timestamp
                ) VALUES (
                    :audit_id, :event_type, :actor_user_id, :actor_email,
                    :actor_role, :scan_id, :details::jsonb, :ip_address, NOW()
                )
            """),
            {
                "audit_id":      audit_id,
                "event_type":    event_type.value,
                "actor_user_id": actor_user_id,
                "actor_email":   actor_email,
                "actor_role":    actor_role.value if actor_role else None,
                "scan_id":       scan_id,
                "details":       json.dumps(details) if details else None,
                "ip_address":    ip_address,
            }
        )
        await self._session.commit()
        row = await self._session.execute(
            text("SELECT * FROM audit_log WHERE audit_id = :id"),
            {"id": audit_id},
        )
        record = row.mappings().fetchone()
        return _row_to_audit(record)

    async def update_audit_event(self, *args, **kwargs):
        """Explicitly blocked. Audit records are immutable."""
        raise StorageAuditViolationError(
            "AURORA_AUDIT_VIOLATION: Audit log records are immutable and append-only. "
            "UPDATE is not permitted for any role."
        )

    async def delete_audit_event(self, *args, **kwargs):
        """Explicitly blocked. Audit records are immutable."""
        raise StorageAuditViolationError(
            "AURORA_AUDIT_VIOLATION: Audit log records are immutable and append-only. "
            "DELETE is not permitted for any role."
        )

    async def query_audit_log(
        self,
        event_type: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        scan_id: Optional[str] = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult:
        """Read-only audit log queries. Admin role enforced by API layer."""
        p = pagination or PaginationParams.default()
        filters = ["1=1"]
        params: dict = {"limit": p.page_size, "offset": p.offset}
        if event_type:
            filters.append("event_type = :event_type")
            params["event_type"] = event_type
        if actor_user_id:
            filters.append("actor_user_id = :actor_user_id")
            params["actor_user_id"] = actor_user_id
        if scan_id:
            filters.append("scan_id = :scan_id")
            params["scan_id"] = scan_id

        where = " AND ".join(filters)
        rows = await self._session.execute(
            text(f"""
                SELECT * FROM audit_log WHERE {where}
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        count_row = await self._session.execute(
            text(f"SELECT COUNT(*) FROM audit_log WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
        total = count_row.scalar() or 0
        items = [_row_to_audit(r) for r in rows.mappings().fetchall()]
        return PaginatedResult(items=items, total=total, params=p)


def _row_to_audit(row) -> AuditRecord:
    d = dict(row)
    return AuditRecord(
        audit_id=str(d["audit_id"]),
        event_type=AuditEventEnum(d["event_type"]),
        actor_user_id=str(d["actor_user_id"]) if d.get("actor_user_id") else None,
        actor_email=d.get("actor_email"),
        actor_role=RoleEnum(d["actor_role"]) if d.get("actor_role") else None,
        scan_id=str(d["scan_id"]) if d.get("scan_id") else None,
        details=d.get("details"),
        ip_address=d.get("ip_address"),
        timestamp=d["timestamp"],
    )