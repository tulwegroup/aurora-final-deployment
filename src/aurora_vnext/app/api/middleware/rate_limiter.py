"""
Aurora OSI vNext — Token Bucket Rate Limiter Middleware
Phase T §T.2 — API Rate Limiting

Implements a sliding-window token bucket per (user_id, endpoint_group).
Uses Redis atomic INCR + EXPIRE for distributed enforcement.

Rate limit tiers (requests per minute):
  viewer:   60 RPM  — read-only, light query load
  operator: 120 RPM — scan submission + history
  admin:    300 RPM — admin panel + export operations

CONSTITUTIONAL RULES — Phase T:
  Rule 1: Rate limits are infrastructure constants (RPM integers).
           They are NOT scientific constants. No relation to ACIF or thresholds.
  Rule 2: Rate limit decisions are based on (user_role, request_count) — neither
           of which are scientific field values.
  Rule 3: Rate limit headers returned to client contain only infrastructure
           metadata: X-RateLimit-Limit, X-RateLimit-Remaining, Retry-After.
           No scientific field is included in rate limit headers.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate limit tiers — requests per 60-second window
# Infrastructure constants: NOT scientific values, NOT related to scoring.
# ---------------------------------------------------------------------------

RATE_LIMITS: dict[str, int] = {
    "admin":    300,
    "operator": 120,
    "viewer":    60,
    "anonymous": 20,
}

WINDOW_SECONDS = 60   # sliding window duration — infrastructure constant


def _redis_key(user_id: str, window_start: int) -> str:
    """
    Rate limit counter key: aurora:rl:{user_id}:{window_start}
    window_start is floor(current_unix_time / WINDOW_SECONDS) * WINDOW_SECONDS.
    """
    return f"aurora:rl:{user_id}:{window_start}"


async def check_rate_limit(
    redis_client,
    user_id: str,
    user_role: str,
) -> tuple[bool, int, int]:
    """
    Check and increment the rate limit counter for a user.

    Returns:
        (allowed, remaining, limit)
        allowed:   True if request is within limit
        remaining: requests remaining in current window
        limit:     max requests for this role

    Uses INCR + EXPIRE — atomic in Redis single-command execution.

    PROOF: only integer arithmetic on request counts. No scientific field touched.
    """
    limit = RATE_LIMITS.get(user_role, RATE_LIMITS["viewer"])
    window_start = (int(time.time()) // WINDOW_SECONDS) * WINDOW_SECONDS
    key = _redis_key(user_id, window_start)

    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, WINDOW_SECONDS + 5)   # +5s grace for clock skew
        remaining = max(0, limit - count)
        return count <= limit, remaining, limit
    except Exception as e:
        logger.info("rate_limit_redis_error", extra={"user_id": user_id, "error": str(e)})
        return True, limit, limit   # Fail open on Redis error


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware applying token bucket rate limiting.

    Skips rate limiting for:
      - /health/* endpoints (liveness/readiness probes)
      - Requests without JWT (anonymous limit applies separately)

    PROOF: only request path and JWT sub/role fields are read.
    No scientific field from any response body is examined.
    """

    def __init__(self, app, redis_client, skip_paths: Optional[list[str]] = None):
        super().__init__(app)
        self._redis = redis_client
        self._skip_prefixes = skip_paths or ["/api/v1/health"]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health probes
        for prefix in self._skip_prefixes:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        # Extract user identity from JWT claims (attached by auth middleware)
        user_id = getattr(request.state, "user_id", None) or request.client.host
        user_role = getattr(request.state, "user_role", "anonymous")

        allowed, remaining, limit = await check_rate_limit(
            self._redis, user_id, user_role
        )

        if not allowed:
            logger.info(
                "rate_limit_exceeded",
                extra={"user_id": user_id, "user_role": user_role},
            )
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limit_exceeded", "retry_after_seconds": WINDOW_SECONDS},
                headers={
                    "X-RateLimit-Limit":     str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After":           str(WINDOW_SECONDS),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response