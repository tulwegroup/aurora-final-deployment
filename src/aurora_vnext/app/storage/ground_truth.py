"""
Aurora OSI vNext — Ground Truth Storage Adapter
Phase Y §Y.4

CONSTITUTIONAL RULES:
  Rule 1 (directive 6): is_synthetic guard enforced at storage layer.
          Any attempt to write a synthetic record raises SyntheticStorageViolation.
          This is the SECOND enforcement point after ingestion service validation.
  Rule 2 (directive 2): All writes are append-only. No record is overwritten or deleted.
          Status transitions create new records with updated state.
  Rule 3 (directive 1): Canonical scan storage is NOT modified by this layer.
          CalibrationScanTrace is written separately to scan lineage storage.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

from typing import Optional

from app.models.ground_truth_model import (
    GroundTruthRecord,
    GroundTruthStatus,
    CalibrationScanTrace,
)
from app.services.calibration_version import CalibrationVersion, CalibrationVersionStatus
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# §Y.4.1 — Storage violation exceptions
# ---------------------------------------------------------------------------

class SyntheticStorageViolation(RuntimeError):
    """
    CONSTITUTIONAL SAFEGUARD (directive 6, storage layer):
    Raised when an attempt is made to write a synthetic record to authoritative storage.
    This is the final enforcement barrier — even if ingestion service is bypassed.
    """

class DestructiveWriteViolation(RuntimeError):
    """Raised if code attempts to overwrite an existing immutable record."""


# ---------------------------------------------------------------------------
# §Y.4.2 — In-process store (replace with DB adapter in production)
# ---------------------------------------------------------------------------

class GroundTruthStorage:
    """
    Append-only ground-truth record storage.

    DIRECTIVE 6 ENFORCEMENT — STORAGE LAYER:
      write() inspects is_synthetic before any I/O.
      This is the second enforcement point (after ingestion service).
      A synthetic record that somehow bypasses ingestion validation
      will be rejected here.

    DIRECTIVE 2 ENFORCEMENT:
      Records are stored by record_id in an append-only dict.
      A second write with the same record_id raises DestructiveWriteViolation.
      Status transitions must use transition_status() which creates a new entry.
    """

    def __init__(self) -> None:
        self._records:  dict[str, GroundTruthRecord]    = {}
        self._versions: dict[str, CalibrationVersion]   = {}
        self._traces:   dict[str, CalibrationScanTrace] = {}
        self._active_version_id: Optional[str]          = None

    # ── Ground truth records ──────────────────────────────────────────────

    def write(self, record: GroundTruthRecord) -> None:
        """
        Write a GroundTruthRecord.

        CONSTITUTIONAL GUARDS:
          1. Synthetic rejection (directive 6 — storage layer)
          2. Immutability check (directive 2 — no overwrite)
        """
        # GUARD 1: Synthetic rejection
        if record.is_synthetic:
            raise SyntheticStorageViolation(
                f"STORAGE LAYER REJECTION: record {record.record_id} has is_synthetic=True. "
                "Synthetic records must not be written to authoritative ground-truth storage. "
                "Use test fixtures or mock storage for synthetic data."
            )

        # GUARD 2: No overwrite
        if record.record_id in self._records:
            raise DestructiveWriteViolation(
                f"Record {record.record_id} already exists in storage. "
                "Ground-truth records are immutable — use transition_status() "
                "to update lifecycle state."
            )

        self._records[record.record_id] = record
        logger.info("gt_storage_write", extra={"record_id": record.record_id})

    def transition_status(
        self,
        record_id: str,
        new_status: GroundTruthStatus,
        rejection_reason: Optional[str] = None,
        superseded_by: Optional[str] = None,
    ) -> GroundTruthRecord:
        """
        Transition a record to a new lifecycle status.
        Creates a new immutable record — original is preserved in _records
        under its record_id with a versioned key.
        """
        existing = self.get(record_id)
        if existing is None:
            raise ValueError(f"Record {record_id!r} not found in storage")

        from dataclasses import replace
        updated = replace(
            existing,
            status           = new_status,
            rejection_reason = rejection_reason or existing.rejection_reason,
            superseded_by    = superseded_by or existing.superseded_by,
        )
        # Preserve original under versioned key, write updated to primary key
        versioned_key = f"{record_id}::{existing.status.value}"
        self._records[versioned_key] = existing
        self._records[record_id]     = updated
        return updated

    def get(self, record_id: str) -> Optional[GroundTruthRecord]:
        return self._records.get(record_id)

    def list_approved(self, commodity: Optional[str] = None) -> list[GroundTruthRecord]:
        """Return all APPROVED records, optionally filtered by commodity."""
        records = [
            r for r in self._records.values()
            if r.status == GroundTruthStatus.APPROVED
            and not r.record_id.endswith("::")   # exclude versioned keys
            and "::" not in r.record_id
        ]
        if commodity:
            records = [r for r in records if r.provenance.commodity == commodity]
        return records

    def list_all(self) -> list[GroundTruthRecord]:
        return [v for k, v in self._records.items() if "::" not in k]

    # ── Calibration versions ──────────────────────────────────────────────

    def write_version(self, version: CalibrationVersion) -> None:
        """Write or update a CalibrationVersion record (versions are mutable for status transitions)."""
        self._versions[version.version_id] = version
        if version.status == CalibrationVersionStatus.ACTIVE:
            self._active_version_id = version.version_id

    def get_version(self, version_id: str) -> Optional[CalibrationVersion]:
        return self._versions.get(version_id)

    def get_active_version(self) -> Optional[CalibrationVersion]:
        if self._active_version_id:
            return self._versions.get(self._active_version_id)
        return None

    def list_versions(self) -> list[CalibrationVersion]:
        return list(self._versions.values())

    # ── Scan traces ───────────────────────────────────────────────────────

    def write_trace(self, trace: CalibrationScanTrace) -> None:
        """Write calibration-scan trace at scan-freeze time (directive 2)."""
        self._traces[trace.scan_id] = trace

    def get_trace(self, scan_id: str) -> Optional[CalibrationScanTrace]:
        return self._traces.get(scan_id)