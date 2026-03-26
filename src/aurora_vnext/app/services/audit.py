"""
Aurora OSI vNext — Service-Layer Audit Event Emitter
Phase K §K.6

Responsibility: provide a lightweight audit event builder for service-layer
operations. Service modules call `emit_audit_event()` to signal significant
transitions. The actual WRITE to the audit_log table is performed by
`storage/audit.py` (Layer 1) — services only build and emit event objects.

This separation maintains Layer 2 → Layer 1 dependency direction.
Services never import from storage/ directly.

Audit events emitted by services:
  - OFFSHORE_CORRECTION_APPLIED  (services/offshore.py)
  - OFFSHORE_CORRECTION_DEGRADED (services/offshore.py, quality=degraded)
  - GRAVITY_COMPOSITE_BUILT      (services/gravity.py)
  - HARMONISATION_COMPLETE       (services/harmonization.py)
  - INVERSION_COMPLETE           (services/quantum.py)
  - SENSOR_ACQUISITION_COMPLETE  (services/gee.py)

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty,
  storage/*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ServiceAuditEventType(str, Enum):
    OFFSHORE_CORRECTION_APPLIED  = "OFFSHORE_CORRECTION_APPLIED"
    OFFSHORE_CORRECTION_DEGRADED = "OFFSHORE_CORRECTION_DEGRADED"
    OFFSHORE_GATE_VIOLATION      = "OFFSHORE_GATE_VIOLATION"
    GRAVITY_COMPOSITE_BUILT      = "GRAVITY_COMPOSITE_BUILT"
    HARMONISATION_COMPLETE       = "HARMONISATION_COMPLETE"
    INVERSION_COMPLETE           = "INVERSION_COMPLETE"
    SENSOR_ACQUISITION_COMPLETE  = "SENSOR_ACQUISITION_COMPLETE"


@dataclass(frozen=True)
class ServiceAuditEvent:
    """
    Immutable audit event emitted by a service-layer operation.
    Consumed by the scan pipeline (Phase L), which writes to storage/audit.py.
    """
    event_type: ServiceAuditEventType
    cell_id: str
    scan_id: str
    timestamp_utc: str
    service_module: str
    details: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def emit_audit_event(
    event_type: ServiceAuditEventType,
    cell_id: str,
    scan_id: str,
    service_module: str,
    details: Optional[dict[str, Any]] = None,
    warnings: Optional[tuple[str, ...]] = None,
) -> ServiceAuditEvent:
    """
    Build an immutable ServiceAuditEvent.

    This function does NOT write to any storage layer.
    The scan pipeline (Phase L) collects events and passes them to
    storage/audit.py for persistence.

    Returns:
        ServiceAuditEvent — ready for pipeline collection.
    """
    return ServiceAuditEvent(
        event_type=event_type,
        cell_id=cell_id,
        scan_id=scan_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        service_module=service_module,
        details=details or {},
        warnings=warnings or (),
    )


def build_offshore_correction_event(
    cell_id: str,
    scan_id: str,
    correction_quality: str,
    warnings: tuple[str, ...],
) -> ServiceAuditEvent:
    """Convenience builder for offshore correction audit events."""
    event_type = (
        ServiceAuditEventType.OFFSHORE_CORRECTION_DEGRADED
        if correction_quality == "degraded"
        else ServiceAuditEventType.OFFSHORE_CORRECTION_APPLIED
    )
    return emit_audit_event(
        event_type=event_type,
        cell_id=cell_id,
        scan_id=scan_id,
        service_module="services.offshore",
        details={"correction_quality": correction_quality},
        warnings=warnings,
    )


def build_harmonisation_event(
    cell_id: str,
    scan_id: str,
    missions_used: tuple[str, ...],
    present_count: int,
    coverage_fraction: float,
    offshore_corrected: bool,
) -> ServiceAuditEvent:
    """Convenience builder for harmonisation completion audit events."""
    return emit_audit_event(
        event_type=ServiceAuditEventType.HARMONISATION_COMPLETE,
        cell_id=cell_id,
        scan_id=scan_id,
        service_module="services.harmonization",
        details={
            "missions_used": list(missions_used),
            "present_observables": present_count,
            "coverage_fraction": round(coverage_fraction, 4),
            "offshore_corrected": offshore_corrected,
        },
    )


def build_gravity_event(
    cell_id: str,
    scan_id: str,
    orbit_sources_used: tuple[str, ...],
    super_resolution_applied: bool,
    g_composite_mgal: Optional[float],
) -> ServiceAuditEvent:
    """Convenience builder for gravity decomposition audit events."""
    return emit_audit_event(
        event_type=ServiceAuditEventType.GRAVITY_COMPOSITE_BUILT,
        cell_id=cell_id,
        scan_id=scan_id,
        service_module="services.gravity",
        details={
            "orbit_sources": list(orbit_sources_used),
            "super_resolution": super_resolution_applied,
            "g_composite_mgal": g_composite_mgal,
        },
    )