"""
Aurora OSI vNext — Prometheus Metrics Collectors
Phase U §U.1 — Observability & Operational Telemetry

Exposes Prometheus metrics for infrastructure and pipeline execution.

METRICS INVENTORY:
  Infrastructure:
    aurora_http_requests_total{method, path, status}        — request count
    aurora_http_request_duration_seconds{method, path}      — latency histogram
    aurora_cache_hits_total{cache_key_type}                  — cache hit count
    aurora_cache_misses_total{cache_key_type}                — cache miss count
    aurora_cache_invalidations_total                         — scan invalidations
    aurora_db_query_duration_seconds{query_type}             — DB query latency
    aurora_redis_operation_duration_seconds{operation}       — Redis op latency
    aurora_rate_limit_rejections_total{role}                 — 429 responses
  Pipeline:
    aurora_scan_submitted_total{commodity, environment}      — scans submitted
    aurora_scan_completed_total{commodity, scan_tier}        — scans completed
    aurora_scan_failed_total{stage}                          — scan failures
    aurora_scan_duration_seconds{commodity, scan_tier}       — end-to-end duration
    aurora_pipeline_stage_duration_seconds{stage}            — per-stage latency
    aurora_queue_depth                                       — pending scan queue
    aurora_twin_build_duration_seconds                       — twin build latency
    aurora_twin_voxel_count                                  — voxels produced per build
    aurora_migration_processed_total{migration_class}        — migration records processed

CONSTITUTIONAL RULES — Phase U:
  Rule 1: No scientific transformation. No arithmetic on ACIF, tier, or score fields.
  Rule 2: Scientific field values are NEVER used as metric labels.
           Labels contain only: commodity (string), environment (string),
           scan_tier (enum string), stage (string), role (string).
           Labels never contain: acif_score values, tier thresholds, score floats.
  Rule 3: `aurora_scan_duration_seconds` measures wall-clock time between
           scan submission and canonical freeze. It is NOT derived from any
           scientific field. It is a pure infrastructure timing measurement.
  Rule 4: `aurora_twin_voxel_count` is an integer row count. It is NOT a
           scientific output — it measures data volume, not mineral probability.
  Rule 5: No import from core/*.
  Rule 6: ACIF scores and tier counts may be emitted as Gauge values ONLY when
           explicitly configured via EMIT_CANONICAL_SUMMARY_METRICS=true.
           Even then: values are read verbatim from the frozen canonical record
           — never recomputed. The metric is a pass-through observation, not
           a derived computation.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Optional

from app.config.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metric definitions
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        REGISTRY, CollectorRegistry,
    )
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    logger.info("prometheus_client not installed — metrics disabled")


def _make_counter(name, doc, labels=()):
    if not _PROM_AVAILABLE: return _NoopMetric()
    try:
        return Counter(name, doc, labels)
    except Exception:
        return REGISTRY._names_to_collectors.get(name, _NoopMetric())


def _make_histogram(name, doc, labels=(), buckets=None):
    if not _PROM_AVAILABLE: return _NoopMetric()
    kwargs = {"labelnames": labels}
    if buckets: kwargs["buckets"] = buckets
    try:
        return Histogram(name, doc, **kwargs)
    except Exception:
        return REGISTRY._names_to_collectors.get(name, _NoopMetric())


def _make_gauge(name, doc, labels=()):
    if not _PROM_AVAILABLE: return _NoopMetric()
    try:
        return Gauge(name, doc, labels)
    except Exception:
        return REGISTRY._names_to_collectors.get(name, _NoopMetric())


class _NoopMetric:
    """Silent no-op metric when prometheus_client is unavailable."""
    def labels(self, **_): return self
    def inc(self, *_, **__): pass
    def dec(self, *_, **__): pass
    def set(self, *_, **__): pass
    def observe(self, *_, **__): pass
    def time(self): return _NoopCtx()


class _NoopCtx:
    def __enter__(self): return self
    def __exit__(self, *_): pass


# ── HTTP metrics ─────────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = _make_counter(
    "aurora_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = _make_histogram(
    "aurora_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ── Cache metrics ─────────────────────────────────────────────────────────────

CACHE_HITS = _make_counter(
    "aurora_cache_hits_total",
    "Cache hits by key type",
    ["cache_key_type"],
)

CACHE_MISSES = _make_counter(
    "aurora_cache_misses_total",
    "Cache misses by key type",
    ["cache_key_type"],
)

CACHE_INVALIDATIONS = _make_counter(
    "aurora_cache_invalidations_total",
    "Cache invalidations (scan reprocess events)",
)

# ── DB / Redis metrics ────────────────────────────────────────────────────────

DB_QUERY_DURATION = _make_histogram(
    "aurora_db_query_duration_seconds",
    "Database query latency",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

REDIS_OP_DURATION = _make_histogram(
    "aurora_redis_operation_duration_seconds",
    "Redis operation latency",
    ["operation"],
    buckets=[0.0001, 0.001, 0.005, 0.01, 0.05, 0.1],
)

RATE_LIMIT_REJECTIONS = _make_counter(
    "aurora_rate_limit_rejections_total",
    "Rate limit 429 responses",
    ["role"],
)

# ── Pipeline metrics ──────────────────────────────────────────────────────────

SCAN_SUBMITTED = _make_counter(
    "aurora_scan_submitted_total",
    "Scans submitted — labelled by commodity and environment (strings only)",
    ["commodity", "environment"],
)

SCAN_COMPLETED = _make_counter(
    "aurora_scan_completed_total",
    "Scans completed — labelled by commodity and scan_tier (canonical enum string)",
    ["commodity", "scan_tier"],
)

SCAN_FAILED = _make_counter(
    "aurora_scan_failed_total",
    "Scans failed — labelled by pipeline stage",
    ["stage"],
)

SCAN_DURATION = _make_histogram(
    "aurora_scan_duration_seconds",
    "Wall-clock time from scan submission to canonical freeze. "
    "Infrastructure timing — NOT derived from any scientific field.",
    ["commodity", "scan_tier"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)

PIPELINE_STAGE_DURATION = _make_histogram(
    "aurora_pipeline_stage_duration_seconds",
    "Per-stage pipeline latency",
    ["stage"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

QUEUE_DEPTH = _make_gauge(
    "aurora_queue_depth",
    "Number of scans pending in the task queue",
)

TWIN_BUILD_DURATION = _make_histogram(
    "aurora_twin_build_duration_seconds",
    "Wall-clock time for digital twin build (infrastructure timing)",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

TWIN_VOXEL_COUNT = _make_histogram(
    "aurora_twin_voxel_count",
    "Number of voxels produced per twin build "
    "(integer row count — not a scientific output)",
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000],
)

MIGRATION_PROCESSED = _make_counter(
    "aurora_migration_processed_total",
    "Migration records processed by class (A/B/C)",
    ["migration_class"],
)

# ── Optional: canonical summary pass-through gauges ─────────────────────────
# RULE 6: Only active when EMIT_CANONICAL_SUMMARY_METRICS=true.
# Values read verbatim from frozen canonical record — NEVER recomputed.

CANONICAL_ACIF_GAUGE = _make_gauge(
    "aurora_canonical_acif_score",
    "display_acif_score verbatim from frozen CanonicalScan. "
    "Pass-through observation only — never recomputed. "
    "Requires EMIT_CANONICAL_SUMMARY_METRICS=true.",
    ["scan_id", "commodity"],
)

# ---------------------------------------------------------------------------
# Timing context manager — convenience wrapper
# ---------------------------------------------------------------------------

@contextmanager
def timed(histogram, **labels):
    """
    Context manager: records elapsed wall-clock time to a Histogram.

    Usage:
        with timed(PIPELINE_STAGE_DURATION, stage="evidence"):
            await run_evidence_stage(...)

    PROOF: measures time.monotonic() delta only. No scientific field accessed.
    """
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        if labels:
            histogram.labels(**labels).observe(elapsed)
        else:
            histogram.observe(elapsed)


# ---------------------------------------------------------------------------
# Metric emission helpers — called from pipeline and API layers
# ---------------------------------------------------------------------------

def record_scan_submitted(commodity: str, environment: str) -> None:
    """Called at scan submission. Labels are string identifiers — not scores."""
    SCAN_SUBMITTED.labels(
        commodity=commodity or "unknown",
        environment=environment or "unknown",
    ).inc()


def record_scan_completed(commodity: str, scan_tier: str, duration_seconds: float) -> None:
    """
    Called at canonical freeze.

    PROOF: scan_tier is the canonical enum string (e.g. "TIER_1") — the stored
    label, not a numeric threshold. duration_seconds is wall-clock time, not
    derived from any scientific field.
    """
    SCAN_COMPLETED.labels(
        commodity=commodity or "unknown",
        scan_tier=scan_tier or "unknown",
    ).inc()
    SCAN_DURATION.labels(
        commodity=commodity or "unknown",
        scan_tier=scan_tier or "unknown",
    ).observe(duration_seconds)


def record_scan_failed(stage: str) -> None:
    SCAN_FAILED.labels(stage=stage).inc()


def record_twin_built(voxel_count: int, duration_seconds: float) -> None:
    """
    Called after twin build completes.
    voxel_count is an integer DB row count — not a scientific value.
    """
    TWIN_BUILD_DURATION.observe(duration_seconds)
    TWIN_VOXEL_COUNT.observe(voxel_count)


def record_migration(migration_class: str) -> None:
    MIGRATION_PROCESSED.labels(migration_class=migration_class).inc()


def emit_canonical_acif_gauge(scan_id: str, commodity: str, acif_score: Optional[float]) -> None:
    """
    RULE 6: Optional pass-through gauge for monitoring dashboards.
    acif_score is the verbatim value from the frozen CanonicalScan record.
    This function MUST only be called with a value read from storage —
    never with a recomputed value.
    """
    import os
    if os.environ.get("EMIT_CANONICAL_SUMMARY_METRICS", "").lower() != "true":
        return
    if acif_score is not None:
        CANONICAL_ACIF_GAUGE.labels(
            scan_id=scan_id,
            commodity=commodity or "unknown",
        ).set(acif_score)