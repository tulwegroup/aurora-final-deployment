"""
Aurora OSI vNext — Pipeline Telemetry Instrumentation
Phase U §U.3

Thin instrumentation layer called from pipeline/scan_pipeline.py
at stage boundaries. Emits metrics + structured log + trace span
for each pipeline stage without touching scientific logic.

INSTRUMENTED STAGES (orchestration only — no science):
  submit        → record_scan_submitted()
  harmonise     → stage timing
  evidence      → stage timing + cell_count
  causal        → stage timing
  physics       → stage timing
  temporal      → stage timing
  priors        → stage timing
  uncertainty   → stage timing
  scoring       → stage timing + cell_count
  tiering       → stage timing
  gates         → stage timing
  freeze        → record_scan_completed() + duration
  twin_build    → record_twin_built() + duration + voxel_count
  failed        → record_scan_failed(stage)

CONSTITUTIONAL RULES — Phase U:
  Rule 1: This module calls ONLY metrics.py and tracing.py functions.
           It NEVER calls compute_acif(), assign_tier(), evaluate_gates().
  Rule 2: Scientific field values are passed in only for verbatim canonical
           log emission after freeze (scan_tier is the stored enum string).
           acif_score may be passed to emit_canonical_acif_gauge() which is
           gated by EMIT_CANONICAL_SUMMARY_METRICS env var — read-only passthrough.
  Rule 3: No arithmetic on any scientific field in this module.
  Rule 4: No import from core/*.

LAYER: Instrumentation shim. May import from observability/ only.
       Must NOT import from core/*, pipeline/scan_pipeline.py, storage/scans.py.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Optional

from app.observability.metrics import (
    record_scan_submitted,
    record_scan_completed,
    record_scan_failed,
    record_twin_built,
    record_migration,
    emit_canonical_acif_gauge,
    PIPELINE_STAGE_DURATION,
    QUEUE_DEPTH,
    timed,
)
from app.observability.tracing import (
    trace_span,
    pipeline_span_attrs,
    twin_span_attrs,
)
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Stage timing context manager
# ---------------------------------------------------------------------------

@contextmanager
def instrument_stage(scan_id: str, stage: str, cell_count: Optional[int] = None):
    """
    Instrument one pipeline stage: emit timing metric + structured log + trace span.

    Usage (in scan_pipeline.py):
        with instrument_stage(scan_id, "evidence", cell_count=len(cells)):
            results = await run_evidence_stage(cells, commodity_config)

    PROOF: yields control immediately; only measures wall-clock time.
    No scientific field is read, compared, or computed here.
    """
    attrs = pipeline_span_attrs(scan_id, stage, cell_count)
    with trace_span(f"pipeline.{stage}", attrs) as span:
        with timed(PIPELINE_STAGE_DURATION, stage=stage):
            start = time.monotonic()
            try:
                yield span
            finally:
                elapsed_ms = round((time.monotonic() - start) * 1000)
                logger.info(
                    "pipeline_stage_complete",
                    extra={
                        "scan_id":    scan_id,
                        "stage":      stage,
                        "cell_count": cell_count,
                        "duration_ms": elapsed_ms,
                    },
                )
                span.set_attribute("duration_ms", elapsed_ms)


# ---------------------------------------------------------------------------
# Lifecycle event handlers
# ---------------------------------------------------------------------------

def on_scan_submitted(scan_id: str, commodity: str, environment: str) -> None:
    """
    Called immediately after a new scan is enqueued.
    PROOF: logs scan_id (identifier), commodity/environment (strings).
    No scientific field touched.
    """
    record_scan_submitted(commodity, environment)
    logger.info(
        "scan_submitted",
        extra={"scan_id": scan_id, "commodity": commodity, "environment": environment},
    )


def on_scan_completed(
    scan_id: str,
    commodity: str,
    scan_tier: str,
    submitted_at: float,
    acif_score: Optional[float] = None,
) -> None:
    """
    Called after canonical freeze is written to storage.

    Args:
        scan_id:      Identifier.
        commodity:    String label.
        scan_tier:    Canonical enum string from frozen record (e.g. "TIER_1").
                      PROOF: stored string value — not recomputed or re-derived.
        submitted_at: Unix timestamp of submission (monotonic). Duration = now - submitted_at.
                      PROOF: wall-clock duration — no scientific arithmetic.
        acif_score:   Verbatim display_acif_score from frozen canonical record.
                      Passed to gauge only if EMIT_CANONICAL_SUMMARY_METRICS=true.
                      PROOF: not recomputed here — caller reads from storage.
    """
    duration_s = time.monotonic() - submitted_at
    record_scan_completed(commodity, scan_tier, duration_s)
    emit_canonical_acif_gauge(scan_id, commodity, acif_score)   # gated by env var
    logger.info(
        "scan_completed",
        extra={
            "scan_id":       scan_id,
            "commodity":     commodity,
            "scan_tier":     scan_tier,   # verbatim stored enum — not recomputed
            "duration_s":    round(duration_s, 2),
        },
    )


def on_scan_failed(scan_id: str, stage: str, error_message: str) -> None:
    """Called when a pipeline stage raises an unrecoverable error."""
    record_scan_failed(stage)
    logger.info(
        "scan_failed",
        extra={"scan_id": scan_id, "stage": stage, "error": error_message},
    )


def on_twin_built(
    scan_id: str,
    twin_version: int,
    voxel_count: int,
    start_time: float,
) -> None:
    """
    Called after twin voxels are written to storage.

    voxel_count: integer DB row count — not a scientific value.
    duration:    wall-clock time — not derived from scientific fields.
    """
    duration_s = time.monotonic() - start_time
    record_twin_built(voxel_count, duration_s)
    logger.info(
        "twin_built",
        extra={
            "scan_id":      scan_id,
            "twin_version": twin_version,
            "voxel_count":  voxel_count,   # integer row count — Rule 3
            "duration_s":   round(duration_s, 2),
        },
    )


def on_migration_record(scan_id: str, migration_class: str) -> None:
    """Called per record in migration pipeline. migration_class is 'A', 'B', or 'C'."""
    record_migration(migration_class)
    logger.info(
        "migration_record",
        extra={"scan_id": scan_id, "migration_class": migration_class},
    )


def set_queue_depth(depth: int) -> None:
    """Update the queue depth gauge with the current pending scan count."""
    QUEUE_DEPTH.set(depth)
    logger.info("queue_depth_updated", extra={"depth": depth})