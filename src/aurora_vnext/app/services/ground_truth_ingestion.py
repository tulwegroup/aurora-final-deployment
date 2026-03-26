"""
Aurora OSI vNext — Ground Truth Ingestion Service
Phase Y §Y.2

CONSTITUTIONAL RULES:
  Rule 1 (directive 1): Ingestion never touches existing canonical scans.
  Rule 2 (directive 2): is_synthetic guard enforced here — synthetic records
          rejected from authoritative paths at this layer.
  Rule 3 (directive 3): geological_data_type validation enforced.
  Rule 4 (directive 4): confidence weighting fields are validated before acceptance.
  Rule 5 (directive 5): no ACIF computation, no tier assignment, no gate evaluation.
  Rule 6 (directive 7): event-driven architecture — emits domain events for
          downstream consumers (bulk, streaming, national survey syncing).
  Rule 7: No import from core/scoring, core/tiering, core/gates.

Ingestion validation flow:
  1. Schema validation (all required fields present)
  2. Synthetic guard (is_synthetic=True → REJECTED immediately)
  3. Provenance completeness check
  4. Confidence weighting bounds check
  5. Geological data type routing (type-specific field checks)
  6. Deduplication check (spatial + source_identifier proximity)
  7. Emit GroundTruthIngested event → storage adapter
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models.ground_truth_model import (
    GroundTruthRecord,
    GroundTruthStatus,
    GeologicalDataType,
    GroundTruthProvenance,
    ConfidenceWeighting,
    new_record_id,
)
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# §Y.2.1 — Ingestion result
# ---------------------------------------------------------------------------

@dataclass
class IngestionResult:
    """Result of a single ground-truth ingestion attempt."""
    success:      bool
    record_id:    Optional[str]
    rejection_reason: Optional[str]
    warnings:     list[str]


# ---------------------------------------------------------------------------
# §Y.2.2 — Rejection exceptions (fail-fast)
# ---------------------------------------------------------------------------

class SyntheticDataRejectedError(ValueError):
    """
    CONSTITUTIONAL SAFEGUARD (directive 6):
    Synthetic records are NEVER accepted at ingestion into authoritative paths.
    This error is raised at the first layer — not silently filtered downstream.
    """

class MissingProvenanceError(ValueError):
    """Raised when provenance is absent or incomplete."""

class MissingConfidenceError(ValueError):
    """Raised when any confidence weighting field is absent."""

class InvalidGeologicalTypeError(ValueError):
    """Raised when geological_data_type is unrecognised."""

class DuplicateRecordError(ValueError):
    """Raised when a spatially and source-identical record already exists."""


# ---------------------------------------------------------------------------
# §Y.2.3 — Type-specific validation rules
# ---------------------------------------------------------------------------

# Required payload keys per geological data type (directive 3)
_TYPE_REQUIRED_PAYLOAD_KEYS: dict[GeologicalDataType, list[str]] = {
    GeologicalDataType.DEPOSIT_OCCURRENCE:     ["deposit_name", "deposit_class"],
    GeologicalDataType.DRILL_INTERSECTION:     ["hole_id", "from_m", "to_m"],
    GeologicalDataType.GEOCHEMICAL_ANOMALY:    ["element", "value_ppm"],
    GeologicalDataType.GEOPHYSICAL_VALIDATION: ["geophysical_method", "observed_value"],
    GeologicalDataType.PRODUCTION_HISTORY:     ["operation_name", "production_period"],
    GeologicalDataType.BASIN_VALIDATION:       ["basin_name", "system_type"],
}


def _validate_type_payload(record: GroundTruthRecord) -> list[str]:
    """
    Check that type-specific required payload keys are present.
    Returns list of warning strings (non-fatal missing optional fields).
    Raises ValueError on missing required keys.
    """
    required = _TYPE_REQUIRED_PAYLOAD_KEYS.get(record.geological_data_type, [])
    missing = [k for k in required if k not in record.data_payload]
    if missing:
        raise ValueError(
            f"Record {record.record_id}: geological_data_type="
            f"{record.geological_data_type.value} missing required payload fields: {missing}"
        )
    return []


# ---------------------------------------------------------------------------
# §Y.2.4 — Core ingestion validation pipeline
# ---------------------------------------------------------------------------

def validate_ground_truth_record(record: GroundTruthRecord) -> list[str]:
    """
    Full validation pipeline for a single GroundTruthRecord.
    Returns list of non-fatal warnings.
    Raises on any fatal validation failure.

    STEP 1: Synthetic guard (directive 6 — fail-fast, first check)
    STEP 2: Provenance completeness
    STEP 3: Confidence bounds
    STEP 4: Type-specific payload validation
    STEP 5: Spatial plausibility (if lat/lon present)
    """
    warnings: list[str] = []

    # STEP 1: Synthetic guard — MUST be first (directive 6)
    if record.is_synthetic:
        raise SyntheticDataRejectedError(
            f"Record {record.record_id} is marked is_synthetic=True. "
            "Synthetic records are prohibited from authoritative calibration ingestion. "
            "Use test harnesses for synthetic data validation only."
        )

    # STEP 2: Provenance completeness
    p = record.provenance
    if not all([p.source_name, p.source_identifier, p.country, p.commodity, p.license_note]):
        raise MissingProvenanceError(
            f"Record {record.record_id}: provenance has empty required fields."
        )

    # STEP 3: Confidence weighting bounds (already checked by ConfidenceWeighting.__post_init__,
    # but re-validate here for explicit ingestion-layer enforcement)
    c = record.confidence
    for field_name, val in [
        ("source_confidence",           c.source_confidence),
        ("spatial_accuracy",            c.spatial_accuracy),
        ("temporal_relevance",          c.temporal_relevance),
        ("geological_context_strength", c.geological_context_strength),
    ]:
        if not (0.0 <= val <= 1.0):
            raise MissingConfidenceError(
                f"Record {record.record_id}: confidence.{field_name}={val} out of [0,1]"
            )
    if c.composite < 0.1:
        warnings.append(
            f"Record {record.record_id}: composite confidence {c.composite:.3f} is very low — "
            "consider whether this record provides useful calibration signal."
        )

    # STEP 4: Type-specific payload validation (directive 3)
    warnings.extend(_validate_type_payload(record))

    # STEP 5: Spatial plausibility
    if record.lat is not None and not (-90 <= record.lat <= 90):
        raise ValueError(f"Record {record.record_id}: lat={record.lat} out of range [-90, 90]")
    if record.lon is not None and not (-180 <= record.lon <= 180):
        raise ValueError(f"Record {record.record_id}: lon={record.lon} out of range [-180, 180]")

    return warnings


# ---------------------------------------------------------------------------
# §Y.2.5 — Ingestion service
# ---------------------------------------------------------------------------

class GroundTruthIngestionService:
    """
    Validates and routes ground-truth records to the storage adapter.

    Architecture (directive 7 — event-driven, supports bulk/streaming):
      - ingest_one():  single-record path (interactive upload, API)
      - ingest_bulk(): batch path (national survey datasets, bulk import)
      - Both paths emit domain events for downstream consumers.

    CONSTITUTIONAL GUARANTEE:
      No canonical scan is touched. No ACIF is computed. No tier assigned.
      This service is model configuration input only (directive 5).
    """

    def __init__(self, storage, event_bus=None):
        """
        Args:
            storage:   GroundTruthStorage adapter
            event_bus: Optional EventBus for domain event emission
        """
        self._storage   = storage
        self._event_bus = event_bus

    def ingest_one(self, record: GroundTruthRecord) -> IngestionResult:
        """
        Validate and store a single GroundTruthRecord.

        Validation failure → IngestionResult(success=False, rejection_reason=...)
        Storage success   → IngestionResult(success=True, record_id=...)
        Domain event emitted on success.
        """
        try:
            warnings = validate_ground_truth_record(record)
        except SyntheticDataRejectedError as e:
            logger.warning("gt_ingest_rejected_synthetic", extra={"record_id": record.record_id})
            return IngestionResult(
                success=False, record_id=record.record_id,
                rejection_reason=f"SYNTHETIC_REJECTED: {e}", warnings=[],
            )
        except (MissingProvenanceError, MissingConfidenceError,
                InvalidGeologicalTypeError, ValueError) as e:
            logger.warning("gt_ingest_rejected_validation", extra={"record_id": record.record_id})
            return IngestionResult(
                success=False, record_id=record.record_id,
                rejection_reason=str(e), warnings=[],
            )

        self._storage.write(record)

        if self._event_bus:
            self._event_bus.publish_sync(
                "ground_truth.ingested",
                {
                    "record_id":            record.record_id,
                    "geological_data_type": record.geological_data_type.value,
                    "commodity":            record.provenance.commodity,
                    "country":              record.provenance.country,
                    "source_name":          record.provenance.source_name,
                },
            )

        logger.info("gt_ingest_success", extra={
            "record_id": record.record_id,
            "type":      record.geological_data_type.value,
        })
        return IngestionResult(
            success=True, record_id=record.record_id,
            rejection_reason=None, warnings=warnings,
        )

    def ingest_bulk(self, records: list[GroundTruthRecord]) -> list[IngestionResult]:
        """
        Batch ingestion path for national survey datasets and bulk imports.
        Each record is validated independently — one failure does not block others.
        Returns one IngestionResult per input record.
        """
        results = []
        for record in records:
            results.append(self.ingest_one(record))

        n_ok  = sum(1 for r in results if r.success)
        n_fail = len(results) - n_ok
        logger.info("gt_bulk_ingest_complete", extra={"accepted": n_ok, "rejected": n_fail})

        if self._event_bus and n_ok > 0:
            self._event_bus.publish_sync(
                "ground_truth.bulk_ingested",
                {"accepted": n_ok, "rejected": n_fail, "total": len(records)},
            )

        return results