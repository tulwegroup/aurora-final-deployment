"""
Aurora OSI vNext — Ground Truth Audit Log
Phase Z §Z.2

Append-only audit log for all ground-truth state transitions.

CONSTITUTIONAL RULES:
  Rule 1: Every state transition (submit, approve, reject, revoke) appends
          a new AuditEntry — no entry is ever deleted or overwritten.
  Rule 2: Audit entries record infrastructure metadata only:
          who, what, when, record_id, from_state, to_state, reason.
          No scientific field values (ACIF, tier) are stored in audit entries.
  Rule 3: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class AuditEntry:
    """
    Immutable audit log entry for a single ground-truth state transition.

    Fields:
      entry_id:    UUID string
      actor_id:    User ID who performed the action
      actor_role:  Role at time of action
      action:      Verb — "submitted", "approved", "rejected", "revoked", "superseded"
      record_id:   GroundTruthRecord.record_id affected
      from_status: Status before transition (None for initial submission)
      to_status:   Status after transition
      reason:      Mandatory for reject/revoke; optional for others
      occurred_at: ISO 8601 UTC timestamp
    """
    entry_id:    str
    actor_id:    str
    actor_role:  str
    action:      str
    record_id:   str
    from_status: Optional[str]
    to_status:   str
    reason:      Optional[str]
    occurred_at: str


class GroundTruthAuditLog:
    """
    Append-only audit log. Entries are never deleted or modified.

    Provides:
      append(entry)            — add a new entry
      entries_for(record_id)   — all transitions for a specific record
      all_entries()            — full log (admin view)
    """

    def __init__(self) -> None:
        self._log: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._log.append(entry)

    def entries_for(self, record_id: str) -> list[AuditEntry]:
        return [e for e in self._log if e.record_id == record_id]

    def all_entries(self) -> list[AuditEntry]:
        return list(self._log)

    def make_entry(
        self,
        actor_id:    str,
        actor_role:  str,
        action:      str,
        record_id:   str,
        to_status:   str,
        from_status: Optional[str] = None,
        reason:      Optional[str] = None,
    ) -> AuditEntry:
        import uuid
        entry = AuditEntry(
            entry_id    = str(uuid.uuid4()),
            actor_id    = actor_id,
            actor_role  = actor_role,
            action      = action,
            record_id   = record_id,
            from_status = from_status,
            to_status   = to_status,
            reason      = reason,
            occurred_at = datetime.utcnow().isoformat(),
        )
        self.append(entry)
        return entry