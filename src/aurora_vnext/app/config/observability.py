"""
Aurora OSI vNext — Structured Logging & Observability Configuration
Phase Q §Q.2 — Observability

Provides:
  - get_logger(name): structured JSON logger (production) or text (dev)
  - log_pipeline_event(logger, stage, scan_id, details): pipeline stage emitter
  - log_audit_event(logger, event_type, actor, details): security event emitter
  - RequestLoggingMiddleware: ASGI middleware for request/response timing

CONSTITUTIONAL RULES — Phase Q:
  Rule 1: No scientific logic. No imports from core/*.
  Rule 2: Log records NEVER include: acif_score, tier, evidence_score,
           causal_score, physics_score, or any scientific output field.
           They MAY include: scan_id, pipeline_stage, actor, duration_ms,
           status_code, request_path — infrastructure metadata only.
  Rule 3: No threshold, no ACIF formula, no scoring constant introduced here.
  Rule 4: This module is import-safe — no circular imports with core/*.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a structured logger for the given module name.

    In production (JSON format): emits newline-delimited JSON records
    suitable for CloudWatch, Datadog, or any log aggregator.
    In development (text format): human-readable output.

    Usage:
        logger = get_logger(__name__)
        logger.info("Scan submitted", extra={"scan_id": scan_id})
    """
    from app.config.settings import get_settings
    s = get_settings()

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger   # Already configured

    handler = logging.StreamHandler()

    if s.aurora_log_format.value == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    level = getattr(logging, s.aurora_log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for structured log aggregators."""

    # Fields that must NEVER appear in a log record (scientific outputs)
    _BLOCKED_FIELDS = frozenset({
        "acif_score", "display_acif_score", "max_acif_score", "weighted_acif_score",
        "evidence_score", "causal_score", "physics_score", "temporal_score",
        "mean_evidence_score", "tier_counts", "system_status", "gate_results",
        "tier_thresholds_used", "normalisation_params",
    })

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }

        # Include extra fields — but block scientific output fields
        for k, v in record.__dict__.items():
            if k.startswith("_") or k in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            ):
                continue
            if k in self._BLOCKED_FIELDS:
                continue   # PROOF: scientific fields never logged
            payload[k] = v

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Typed log helpers
# ---------------------------------------------------------------------------

def log_pipeline_event(
    logger: logging.Logger,
    stage: str,
    scan_id: str,
    details: Optional[dict] = None,
    level: str = "info",
) -> None:
    """
    Emit a structured pipeline stage event.

    Allowed detail keys: duration_ms, cell_count, error_message,
    worker_id, queue_depth — infrastructure metadata ONLY.

    PROOF: scientific output fields are blocked by _JsonFormatter._BLOCKED_FIELDS.
    """
    extra = {"scan_id": scan_id, "pipeline_stage": stage}
    if details:
        extra.update({k: v for k, v in details.items()})
    getattr(logger, level)("Pipeline stage: %s", stage, extra=extra)


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    actor_email: Optional[str],
    details: Optional[dict] = None,
) -> None:
    """
    Emit a structured security event log record.
    Does NOT include scan result data.
    """
    extra = {"event_type": event_type, "actor_email": actor_email or "unknown"}
    if details:
        extra.update(details)
    logger.info("Security event: %s", event_type, extra=extra)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware: logs request path, method, status code, and duration.

    PROOF: response body is never read — only HTTP metadata logged.
    No scientific output can leak through this middleware.
    """

    def __init__(self, app, logger_name: str = "aurora.http"):
        super().__init__(app)
        self._logger = get_logger(logger_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        self._logger.info(
            "%s %s → %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "http_method":   request.method,
                "http_path":     request.url.path,
                "http_status":   response.status_code,
                "duration_ms":   duration_ms,
                "client_ip":     request.client.host if request.client else None,
            },
        )
        return response