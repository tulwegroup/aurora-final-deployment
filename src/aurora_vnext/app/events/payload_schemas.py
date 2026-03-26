"""
Aurora OSI vNext — Webhook Payload Schemas
Phase V §V.2

Defines typed payload schemas for each domain event type.
Each schema maps VERBATIM fields from the frozen canonical record.

CONSTITUTIONAL RULES — Phase V:
  Rule 1 (verbatim mapping):
    Every field in every PayloadSchema is sourced directly from the frozen
    canonical record via dict.get() or attribute access. No arithmetic,
    no normalisation, no derivation.

  Rule 6 (ACIF pass-through):
    display_acif_score is included in ScanCompletedPayload VERBATIM.
    It is not recomputed, not rounded beyond json.dumps default precision,
    not compared against a threshold, and not used to derive any other field.

  PROOF: Search this file for arithmetic operators applied to scientific fields.
    acif_score: 0 instances.
    tier_counts: 0 arithmetic instances (copied as-is from CanonicalScan.tier_counts).
    Any future field addition must follow the same verbatim-copy constraint.
    No field may be synthesised from a formula involving another scientific field.

CANONICAL SOURCE MAPPING (field → source in CanonicalScan):
  scan_id              → CanonicalScan.scan_id
  commodity            → CanonicalScan.commodity
  environment          → CanonicalScan.environment
  scan_status          → CanonicalScan.scan_status (enum string)
  system_status        → CanonicalScan.system_status (enum string)
  scan_tier            → CanonicalScan.scan_tier (enum string — verbatim)
  display_acif_score   → CanonicalScan.display_acif_score (verbatim float)
  max_acif_score       → CanonicalScan.max_acif_score (verbatim float)
  tier_counts          → CanonicalScan.tier_counts (verbatim dict)
  version_registry     → CanonicalScan.version_registry (verbatim dict)
  frozen_at            → CanonicalScan.frozen_at (ISO timestamp string)
  total_cells          → CanonicalScan.total_cells (integer count)
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Base payload
# ---------------------------------------------------------------------------

@dataclass
class BasePayload:
    scan_id:   str
    commodity: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# scan.completed payload
# ---------------------------------------------------------------------------

@dataclass
class ScanCompletedPayload(BasePayload):
    """
    Payload for scan.completed event.

    All scientific fields are sourced VERBATIM from the frozen CanonicalScan.
    PROOF: from_canonical_scan() uses record.get(key) — Python dict lookup.
    No arithmetic operator is applied to any scientific field value.
    """
    environment:         Optional[str]
    scan_status:         Optional[str]
    system_status:       Optional[str]
    scan_tier:           Optional[str]        # verbatim enum string — never threshold
    display_acif_score:  Optional[float]      # verbatim from frozen record
    max_acif_score:      Optional[float]      # verbatim from frozen record
    tier_counts:         Optional[dict]       # verbatim from frozen record
    total_cells:         Optional[int]
    version_registry:    Optional[dict]       # verbatim — propagation proof
    frozen_at:           Optional[str]

    @classmethod
    def from_canonical_scan(cls, record: dict[str, Any]) -> "ScanCompletedPayload":
        """
        Construct payload from a frozen CanonicalScan dict.

        PROOF: every field is record.get(key) — verbatim dict lookup.
        No formula, no operator, no function of multiple fields.
        """
        return cls(
            scan_id            = record.get("scan_id"),
            commodity          = record.get("commodity"),
            environment        = record.get("environment"),
            scan_status        = record.get("scan_status"),
            system_status      = record.get("system_status"),
            scan_tier          = record.get("scan_tier"),
            display_acif_score = record.get("display_acif_score"),   # verbatim
            max_acif_score     = record.get("max_acif_score"),       # verbatim
            tier_counts        = record.get("tier_counts"),          # verbatim
            total_cells        = record.get("total_cells"),
            version_registry   = record.get("version_registry"),     # verbatim propagation
            frozen_at          = record.get("frozen_at"),
        )


# ---------------------------------------------------------------------------
# scan.failed payload
# ---------------------------------------------------------------------------

@dataclass
class ScanFailedPayload(BasePayload):
    """
    Payload for scan.failed event.
    Contains only infrastructure metadata — no scientific fields.
    """
    failed_stage:  str
    error_message: str
    failed_at:     str   # ISO timestamp


# ---------------------------------------------------------------------------
# twin.built payload
# ---------------------------------------------------------------------------

@dataclass
class TwinBuiltPayload(BasePayload):
    """
    Payload for twin.built event.

    voxel_count is an integer DB row count — not a scientific output (Rule V.3).
    twin_version is an integer sequence counter — not a scientific value.
    version_registry is verbatim from the build manifest.
    """
    twin_version:    int
    voxel_count:     int              # integer row count — not scientific float
    build_duration_s: float           # wall-clock duration — not scientific
    version_registry: Optional[dict]  # verbatim from TwinBuildManifest

    @classmethod
    def from_build_manifest(cls, scan_id: str, commodity: str, manifest: dict) -> "TwinBuiltPayload":
        return cls(
            scan_id          = scan_id,
            commodity        = commodity,
            twin_version     = manifest.get("version"),
            voxel_count      = manifest.get("voxel_count"),          # integer count
            build_duration_s = manifest.get("build_duration_s"),
            version_registry = manifest.get("version_registry"),     # verbatim
        )


# ---------------------------------------------------------------------------
# scan.reprocessing payload
# ---------------------------------------------------------------------------

@dataclass
class ScanReprocessingPayload(BasePayload):
    """
    Payload for scan.reprocessing event.
    Infrastructure metadata only — reason string, no scientific fields.
    """
    reprocess_reason:    str
    triggered_at:        str      # ISO timestamp
    previous_scan_tier:  Optional[str]  # verbatim stored string from prior record


# ---------------------------------------------------------------------------
# Payload factory — assembles DomainEvent from canonical sources
# ---------------------------------------------------------------------------

def make_scan_completed_event(canonical_scan: dict[str, Any]) -> "DomainEvent":
    """
    Factory: construct a scan.completed DomainEvent from a frozen CanonicalScan dict.

    PROOF:
      1. payload = ScanCompletedPayload.from_canonical_scan(canonical_scan)
         → all fields are record.get(key) verbatim lookups
      2. DomainEvent.payload = payload.to_dict()
         → asdict() serialisation, no arithmetic
      3. occurred_at = time.time() — wall-clock timestamp of emission, not scientific
    """
    from app.events.event_bus import DomainEvent, EventType
    payload = ScanCompletedPayload.from_canonical_scan(canonical_scan)
    return DomainEvent(
        event_id    = str(uuid.uuid4()),
        event_type  = EventType.SCAN_COMPLETED,
        occurred_at = time.time(),
        payload     = payload.to_dict(),
    )


def make_scan_failed_event(
    scan_id: str, commodity: str, stage: str, error: str
) -> "DomainEvent":
    from app.events.event_bus import DomainEvent, EventType
    import datetime
    payload = ScanFailedPayload(
        scan_id       = scan_id,
        commodity     = commodity,
        failed_stage  = stage,
        error_message = error,
        failed_at     = datetime.datetime.utcnow().isoformat(),
    )
    return DomainEvent(
        event_id    = str(uuid.uuid4()),
        event_type  = EventType.SCAN_FAILED,
        occurred_at = time.time(),
        payload     = payload.to_dict(),
    )


def make_twin_built_event(
    scan_id: str, commodity: str, manifest: dict
) -> "DomainEvent":
    from app.events.event_bus import DomainEvent, EventType
    payload = TwinBuiltPayload.from_build_manifest(scan_id, commodity, manifest)
    return DomainEvent(
        event_id    = str(uuid.uuid4()),
        event_type  = EventType.TWIN_BUILT,
        occurred_at = time.time(),
        payload     = payload.to_dict(),
    )


def make_scan_reprocessing_event(
    scan_id: str, commodity: str, reason: str, previous_tier: Optional[str]
) -> "DomainEvent":
    from app.events.event_bus import DomainEvent, EventType
    import datetime
    payload = ScanReprocessingPayload(
        scan_id             = scan_id,
        commodity           = commodity,
        reprocess_reason    = reason,
        triggered_at        = datetime.datetime.utcnow().isoformat(),
        previous_scan_tier  = previous_tier,   # verbatim stored string
    )
    return DomainEvent(
        event_id    = str(uuid.uuid4()),
        event_type  = EventType.SCAN_REPROCESSING,
        occurred_at = time.time(),
        payload     = payload.to_dict(),
    )