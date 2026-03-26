"""
Aurora OSI vNext — Ground Truth Record Model
Phase Y §Y.1

CONSTITUTIONAL RULES:
  Rule 1: GroundTruthRecord is an immutable ingestion record.
          It does NOT influence any existing canonical scan retroactively.
  Rule 2: is_synthetic is MANDATORY. Synthetic records are rejected from
          all authoritative calibration paths at ingestion and storage layers.
  Rule 3: geological_data_type is a typed enum — calibration logic must
          treat each type differently (§Y directive 3).
  Rule 4: Confidence weighting fields (source_confidence, spatial_accuracy,
          temporal_relevance, geological_context_strength) are explicit and
          required. No opaque weighting function may reference absent fields.
  Rule 5: No import from core/scoring, core/tiering, core/gates.
          Ground-truth records are model configuration inputs only.

Geological Data Types (§Y directive 3):
  deposit_occurrence      — known mineral deposit or surface occurrence
  drill_intersection      — borehole/drill-collar intersection with mineralisation
  geochemical_anomaly     — lab-analysed geochemical sample anomaly
  geophysical_validation  — geophysical truth point (gravity, magnetic, seismic)
  production_history      — historical production record (mine/well)
  basin_validation        — sedimentary basin or petroleum system validation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# §Y.1.1 — Geological data type taxonomy
# ---------------------------------------------------------------------------

class GeologicalDataType(str, Enum):
    """
    Structured geological data type categories.
    Calibration logic must treat each type differently (directive 3).
    """
    DEPOSIT_OCCURRENCE     = "deposit_occurrence"
    DRILL_INTERSECTION     = "drill_intersection"
    GEOCHEMICAL_ANOMALY    = "geochemical_anomaly"
    GEOPHYSICAL_VALIDATION = "geophysical_validation"
    PRODUCTION_HISTORY     = "production_history"
    BASIN_VALIDATION       = "basin_validation"


# ---------------------------------------------------------------------------
# §Y.1.2 — Ingestion status lifecycle
# ---------------------------------------------------------------------------

class GroundTruthStatus(str, Enum):
    PENDING   = "pending"    # Ingested, awaiting review
    APPROVED  = "approved"   # Approved for calibration use
    REJECTED  = "rejected"   # Rejected — not used in calibration
    SUPERSEDED = "superseded" # Replaced by a newer record (lineage preserved)


# ---------------------------------------------------------------------------
# §Y.1.3 — Confidence weighting (directive 4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceWeighting:
    """
    Explicit confidence weighting fields required on every GroundTruthRecord.

    ALL four fields are required — calibration must reference them explicitly.
    No opaque weighting function may use absent or assumed values (directive 4).

    Fields:
      source_confidence:           Reliability of the originating source (0–1)
      spatial_accuracy:            Positional accuracy of the record location (0–1)
      temporal_relevance:          How current/applicable the data is (0–1)
      geological_context_strength: How directly applicable to the target geology (0–1)
    """
    source_confidence:           float   # ∈ [0, 1]
    spatial_accuracy:            float   # ∈ [0, 1]
    temporal_relevance:          float   # ∈ [0, 1]
    geological_context_strength: float   # ∈ [0, 1]

    def __post_init__(self) -> None:
        for name, val in [
            ("source_confidence",           self.source_confidence),
            ("spatial_accuracy",            self.spatial_accuracy),
            ("temporal_relevance",          self.temporal_relevance),
            ("geological_context_strength", self.geological_context_strength),
        ]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"ConfidenceWeighting.{name} must be in [0,1], got {val}")

    @property
    def composite(self) -> float:
        """
        Explicit composite weight = geometric mean of all four components.
        This formula is auditable — no hidden weighting (directive 4).
        """
        import math
        return math.pow(
            self.source_confidence
            * self.spatial_accuracy
            * self.temporal_relevance
            * self.geological_context_strength,
            0.25,
        )


# ---------------------------------------------------------------------------
# §Y.1.4 — Provenance (directive 7)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroundTruthProvenance:
    """
    Source provenance required on every GroundTruthRecord (directive 7).

    source_name:       Human-readable name of originating source
    source_identifier: URL, DOI, dataset ID, or database record key
    country:           ISO 3166-1 alpha-2 country code
    commodity:         Target commodity (matches Aurora commodity vocabulary)
    license_note:      Usage rights / license statement
    ingestion_timestamp: UTC ISO timestamp of ingestion
    """
    source_name:          str
    source_identifier:    str    # URL, DOI, or dataset record ID
    country:              str    # ISO 3166-1 alpha-2
    commodity:            str
    license_note:         str
    ingestion_timestamp:  str    # ISO 8601 UTC

    def __post_init__(self) -> None:
        for name, val in [
            ("source_name",       self.source_name),
            ("source_identifier", self.source_identifier),
            ("country",           self.country),
            ("commodity",         self.commodity),
            ("license_note",      self.license_note),
        ]:
            if not val or not val.strip():
                raise ValueError(f"GroundTruthProvenance.{name} must not be empty")


# ---------------------------------------------------------------------------
# §Y.1.5 — Ground truth record (directive 3, 4, 7)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroundTruthRecord:
    """
    Immutable ground-truth record for calibration ingestion.

    CONSTITUTIONAL INVARIANTS:
      - is_synthetic=True records are REJECTED at all authoritative paths.
      - provenance is REQUIRED — ingestion fails without it.
      - confidence is REQUIRED — calibration fails without it.
      - geological_data_type is REQUIRED — routes to the correct calibration handler.
      - Canonical scans are NEVER retroactively modified by ground-truth data.
        Ground-truth records update future model parameters only (directive 1).

    Spatial fields (lat, lon, depth_m) are optional — some records are
    region-level or formation-level rather than point-located.
    """
    record_id:             str
    geological_data_type:  GeologicalDataType
    provenance:            GroundTruthProvenance
    confidence:            ConfidenceWeighting
    is_synthetic:          bool                   # MANDATORY — True = rejected from calibration

    # Spatial location (optional — not all record types are point-located)
    lat:                   Optional[float] = None
    lon:                   Optional[float] = None
    depth_m:               Optional[float] = None
    aoi_polygon_wkt:       Optional[str]   = None  # WKT polygon for area-level records

    # Data payload — type-specific fields (stored as verbatim dict)
    data_payload:          dict = field(default_factory=dict)

    # Lifecycle
    status:                GroundTruthStatus = GroundTruthStatus.PENDING
    rejection_reason:      Optional[str]     = None
    superseded_by:         Optional[str]     = None  # record_id of successor
    created_at:            Optional[str]     = None

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("GroundTruthRecord.record_id must not be empty")
        # Provenance and confidence are required types — checked by type system
        # but also guard defensively
        if self.provenance is None:
            raise ValueError("GroundTruthRecord.provenance is required")
        if self.confidence is None:
            raise ValueError("GroundTruthRecord.confidence is required")


# ---------------------------------------------------------------------------
# §Y.1.6 — Calibration scan traceability (directive 2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationScanTrace:
    """
    Stored on every scan to record which calibration version was active
    at scoring time, and which ground-truth sources were used.

    CONSTITUTIONAL RULE: This record is written at scan-freeze time and
    is immutable. It proves which calibration state produced this scan.
    Historical scans are NEVER retroactively updated with newer calibration.

    Fields:
      scan_id:                   The scan this trace belongs to
      calibration_version_id:    CalibrationVersion.version_id at scoring time
      ground_truth_source_ids:   record_ids of approved ground truths used
      calibration_effect_flags:  Which model parameters were influenced
    """
    scan_id:                  str
    calibration_version_id:   str
    ground_truth_source_ids:  tuple[str, ...]
    calibration_effect_flags: tuple[str, ...]   # e.g. ("province_prior_updated", "lambda_updated")
    traced_at:                str               # ISO 8601 UTC


def new_record_id() -> str:
    return str(uuid.uuid4())


def new_trace(
    scan_id: str,
    calibration_version_id: str,
    ground_truth_source_ids: list[str],
    calibration_effect_flags: list[str],
) -> CalibrationScanTrace:
    return CalibrationScanTrace(
        scan_id=scan_id,
        calibration_version_id=calibration_version_id,
        ground_truth_source_ids=tuple(ground_truth_source_ids),
        calibration_effect_flags=tuple(calibration_effect_flags),
        traced_at=datetime.utcnow().isoformat(),
    )