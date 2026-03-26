"""
Aurora OSI vNext — Canonical Scan Store (STUB)
Implemented in Phase G

Responsibilities (when implemented):
  - create_pending_scan: write initial record with status=PENDING
  - freeze_canonical_scan: single write of all canonical fields + status=COMPLETED
    → Storage layer REJECTS if record already has status=COMPLETED
  - get_canonical_scan: read-only retrieval
  - list_canonical_scans: paginated retrieval
  - soft_delete_scan: admin only; audit record required

CONSTITUTIONAL RULE: freeze_canonical_scan is write-once.
A second call with the same scan_id raises a StorageImmutabilityError.
"""

# Phase G implementation placeholder