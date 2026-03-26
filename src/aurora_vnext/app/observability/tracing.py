"""
Aurora OSI vNext — OpenTelemetry Distributed Tracing
Phase U §U.2

Provides:
  - configure_tracing(): set up OTLP exporter + resource attributes
  - trace_span(): context manager for creating child spans
  - Span attribute schemas per operation type (documented below)

SPAN ATTRIBUTE SCHEMAS:
  HTTP request span:
    http.method, http.path, http.status_code, http.duration_ms
    aurora.user_id, aurora.user_role

  Pipeline stage span:
    aurora.scan_id, aurora.pipeline_stage, aurora.stage_duration_ms
    aurora.cell_count (integer — row count, not scientific value)

  DB query span:
    db.system="postgresql", db.operation, db.query_type
    aurora.scan_id (if applicable), db.duration_ms

  Cache operation span:
    aurora.cache_operation (get/set/invalidate), aurora.cache_hit (bool)
    aurora.cache_key_type

  Twin build span:
    aurora.scan_id, aurora.twin_version (int), aurora.voxel_count (int)
    aurora.twin_build_duration_ms

CONSTITUTIONAL RULES — Phase U:
  Rule 1: Span attributes NEVER include: acif_score, tier_counts,
           evidence_score, causal_score, physics_score, tier_thresholds_used,
           normalisation_params, or any scientific field value as a label.
  Rule 2: aurora.scan_id is a string identifier — not a scientific value.
  Rule 3: aurora.cell_count and aurora.voxel_count are integer row counts —
           infrastructure metadata, not scientific outputs.
  Rule 4: Scientific field values may appear in span EVENTS (log-like records
           within a span) ONLY when explicitly tagged with
           event_type="canonical_field_passthrough". They must not be
           used as span labels/attributes for aggregation.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Optional

from app.config.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional OpenTelemetry import
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    logger.info("opentelemetry not installed — tracing disabled (noop)")

# Module-level tracer (initialised by configure_tracing())
_tracer = None

# Attributes forbidden as span labels (scientific output fields — Rule 1)
_FORBIDDEN_SPAN_ATTRS = frozenset({
    "acif_score", "display_acif_score", "max_acif_score", "weighted_acif_score",
    "evidence_score", "causal_score", "physics_score", "temporal_score",
    "mean_evidence_score", "tier_counts", "system_status", "gate_results",
    "tier_thresholds_used", "normalisation_params",
})


# ---------------------------------------------------------------------------
# Tracer initialisation
# ---------------------------------------------------------------------------

def configure_tracing(
    service_name: str = "aurora-vnext",
    otlp_endpoint: Optional[str] = None,
) -> None:
    """
    Configure OpenTelemetry tracing with OTLP exporter.

    Args:
        service_name:  Service name for trace resource.
        otlp_endpoint: OTLP gRPC endpoint (e.g. "http://otel-collector:4317").
                       If None, tracing is configured but no exporter is attached
                       (useful for testing).

    PROOF: configures tracer infrastructure only. No scientific field accessed.
    """
    global _tracer

    if not _OTEL_AVAILABLE:
        logger.info("tracing_skipped", extra={"reason": "opentelemetry not installed"})
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("tracing_configured", extra={"otlp_endpoint": otlp_endpoint})
    else:
        logger.info("tracing_configured", extra={"otlp_endpoint": "none (noop exporter)"})

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)


def _get_tracer():
    global _tracer
    if _tracer is None and _OTEL_AVAILABLE:
        _tracer = trace.get_tracer("aurora-vnext")
    return _tracer


# ---------------------------------------------------------------------------
# Span context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace_span(
    operation_name: str,
    attributes: Optional[dict[str, Any]] = None,
):
    """
    Create a tracing span for an operation.

    Attributes are validated against _FORBIDDEN_SPAN_ATTRS before being set.
    Forbidden attribute keys are silently dropped — they must not appear as
    aggregatable span labels.

    Usage:
        with trace_span("pipeline.evidence_stage", {"aurora.scan_id": scan_id}):
            await run_evidence(...)

    PROOF: attribute validation block prevents scientific field values from
    leaking into span labels used for trace aggregation.
    """
    t = _get_tracer()

    if t is None:
        # No-op path: tracing disabled
        start = time.monotonic()
        try:
            yield _NoopSpan()
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "span_noop",
                extra={"operation": operation_name, "duration_ms": elapsed_ms},
            )
        return

    # Validate and sanitise attributes — drop forbidden scientific fields
    safe_attrs: dict[str, Any] = {}
    if attributes:
        for k, v in attributes.items():
            if k in _FORBIDDEN_SPAN_ATTRS:
                logger.info(
                    "span_attr_blocked",
                    extra={"key": k, "operation": operation_name},
                )
                continue   # RULE 1: drop silently
            safe_attrs[k] = v

    with t.start_as_current_span(operation_name, attributes=safe_attrs) as span:
        start = time.monotonic()
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            span.set_attribute("duration_ms", elapsed_ms)


class _NoopSpan:
    """No-op span when tracing is disabled."""
    def set_attribute(self, *_, **__): pass
    def add_event(self, *_, **__): pass
    def record_exception(self, *_, **__): pass
    def set_status(self, *_, **__): pass


# ---------------------------------------------------------------------------
# Typed span helpers — one per operation type
# ---------------------------------------------------------------------------

def http_span_attrs(method: str, path: str, user_id: str, user_role: str) -> dict:
    """
    Attributes for HTTP request spans.
    PROOF: no scientific field value included.
    """
    return {
        "http.method":    method,
        "http.path":      path,
        "aurora.user_id": user_id or "anonymous",
        "aurora.user_role": user_role or "anonymous",
    }


def pipeline_span_attrs(scan_id: str, stage: str, cell_count: Optional[int] = None) -> dict:
    """
    Attributes for pipeline stage spans.
    cell_count is integer row count — infrastructure metadata, not scientific value.
    """
    attrs = {
        "aurora.scan_id":        scan_id,
        "aurora.pipeline_stage": stage,
    }
    if cell_count is not None:
        attrs["aurora.cell_count"] = cell_count   # integer count, Rule 3
    return attrs


def twin_span_attrs(scan_id: str, twin_version: int, voxel_count: Optional[int] = None) -> dict:
    """
    Attributes for twin build spans.
    voxel_count is integer row count — not a scientific output.
    """
    attrs = {
        "aurora.scan_id":     scan_id,
        "aurora.twin_version": twin_version,
    }
    if voxel_count is not None:
        attrs["aurora.voxel_count"] = voxel_count   # integer count, Rule 3
    return attrs


def db_span_attrs(query_type: str, scan_id: Optional[str] = None) -> dict:
    """Attributes for DB query spans."""
    attrs = {
        "db.system":     "postgresql",
        "db.query_type": query_type,
    }
    if scan_id:
        attrs["aurora.scan_id"] = scan_id
    return attrs


def cache_span_attrs(operation: str, key_type: str, hit: Optional[bool] = None) -> dict:
    """Attributes for cache operation spans."""
    attrs = {
        "aurora.cache_operation": operation,
        "aurora.cache_key_type":  key_type,
    }
    if hit is not None:
        attrs["aurora.cache_hit"] = hit
    return attrs