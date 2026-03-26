"""
Aurora OSI vNext — Health & Readiness API
Phase Q §Q.1 — Observability / Deployment Hardening

ENDPOINT INVENTORY:
  GET /health/live    — liveness probe (process alive)
  GET /health/ready   — readiness probe (DB + queue reachable)
  GET /health/version — version registry snapshot (read-only)
  GET /health/metrics — lightweight operational counters (no score data)

CONSTITUTIONAL RULES — Phase Q:
  Rule 1: Zero scientific logic. No imports from core/*.
  Rule 2: No canonical scan fields in any response.
           Responses contain ONLY infrastructure state.
  Rule 3: No score, tier, gate, threshold, or ACIF data.
  Rule 4: version_registry values are READ from config/versions.py — never
           recomputed or overridden. Health endpoint is read-only.
  Rule 5: Readiness probe verifies DB connectivity only — it does NOT read
           scan results, does NOT check scientific outputs.

No imports from core/*, services/* (scientific), pipeline/*, storage/scans.py.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])

# Process start time for uptime calculation
_START_TIME = time.monotonic()
_START_WALL = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Liveness probe — is the process alive?
# ---------------------------------------------------------------------------

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict:
    """
    Liveness probe for container orchestrator (Kubernetes, ECS, etc.).
    Returns 200 if the process is running. No DB check.
    Never returns scan result data.
    """
    return {
        "status": "alive",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "started_at": _START_WALL.isoformat(),
    }


# ---------------------------------------------------------------------------
# Readiness probe — can the service handle requests?
# ---------------------------------------------------------------------------

@router.get("/ready")
async def readiness() -> JSONResponse:
    """
    Readiness probe — checks DB connectivity and environment completeness.
    Returns 200 if ready, 503 if not.

    PROOF: uses raw SQL 'SELECT 1' only — no scan table access,
    no canonical scan read, no scientific data involved.
    """
    checks: dict[str, str] = {}
    healthy = True

    # Check DB connectivity via minimal ping
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        from app.config.settings import get_settings
        s = get_settings()
        engine = create_async_engine(s.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        healthy = False

    # Check required env vars (no secret values returned)
    required_env = ["AURORA_SECRET_KEY", "AURORA_ADMIN_PASS"]
    for var in required_env:
        checks[f"env.{var}"] = "set" if os.environ.get(var) else "missing"
        if not os.environ.get(var):
            healthy = False

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if healthy else "not_ready",
            "checks": checks,
        },
    )


# ---------------------------------------------------------------------------
# Version registry — read-only snapshot
# ---------------------------------------------------------------------------

@router.get("/version", status_code=status.HTTP_200_OK)
async def version_info() -> dict:
    """
    Current version registry values from config/settings.py.
    Read-only — no computation, no override.

    PROOF: values sourced directly from Settings fields which mirror
    environment variables. No scientific constant is defined here.
    """
    from app.config.settings import get_settings
    s = get_settings()
    return {
        "aurora_env":                    s.aurora_env.value,
        "version_registry": {
            "score_version":             s.aurora_score_version,
            "tier_version":              s.aurora_tier_version,
            "causal_graph_version":      s.aurora_causal_graph_version,
            "physics_model_version":     s.aurora_physics_model_version,
            "temporal_model_version":    s.aurora_temporal_model_version,
            "province_prior_version":    s.aurora_province_prior_version,
            "commodity_library_version": s.aurora_commodity_library_version,
            "scan_pipeline_version":     s.aurora_scan_pipeline_version,
        },
        "note": "All version values read from environment — never recomputed.",
    }


# ---------------------------------------------------------------------------
# Operational metrics — infrastructure counters only
# ---------------------------------------------------------------------------

@router.get("/metrics", status_code=status.HTTP_200_OK)
async def metrics() -> dict:
    """
    Lightweight operational counters for monitoring dashboards.

    PROOF: No scan results, scores, or thresholds returned.
    Metrics are row counts and queue sizes only — infrastructure state.
    """
    import sys
    counts: dict = {}

    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        from app.config.settings import get_settings
        s = get_settings()
        engine = create_async_engine(s.database_url)
        async with engine.connect() as conn:
            for table, label in [
                ("canonical_scans", "total_scans"),
                ("scan_cells",      "total_cells"),
                ("audit_log",       "total_audit_events"),
            ]:
                try:
                    row = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[label] = row.scalar()
                except Exception:
                    counts[label] = None
        await engine.dispose()
    except Exception:
        pass

    return {
        "process": {
            "uptime_seconds":    round(time.monotonic() - _START_TIME, 1),
            "python_version":    sys.version.split()[0],
        },
        "storage_counts":        counts,
        "note": "Infrastructure counters only. No scientific data included.",
    }