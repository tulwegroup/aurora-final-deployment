"""
Aurora OSI vNext — Redis Response Cache
Phase T §T.1 — API Response Caching

Provides:
  - CacheClient: async Redis wrapper with get/set/invalidate
  - cache_scan_summary(): cache key strategy for canonical scan summaries
  - cache_cell_page(): cache key strategy for paginated cell lists
  - cache_voxel_page(): cache key strategy for progressive voxel pages
  - invalidate_scan(): invalidate all keys for a scan_id on reprocess

CONSTITUTIONAL RULES — Phase T:
  Rule 1: Cache stores and returns values VERBATIM. Zero transformation.
           Cached bytes are the serialised API response from storage — not
           recomputed, not re-serialised with different precision.
  Rule 2: Cache keys encode scan_id + version + query parameters only.
           No scientific field value is used as a cache key component.
  Rule 3: TTL values are infrastructure constants (seconds). They are NOT
           scientific constants and have no relation to scoring or thresholds.
  Rule 4: Cache miss falls through to the storage layer. The response returned
           on a cache miss is identical to the response returned on a cache hit —
           both are the same stored record. No scientific derivation on miss.
  Rule 5: No import from core/*.
  Rule 6: Cache invalidation on scan reprocess (entity mutation event) ensures
           stale scientific outputs are never served after a canonical update.

PROOF: This module contains no arithmetic on scientific fields.
No acif_score, tier_counts, system_status, or threshold value is read,
compared, or transformed here. Cache keys are string-concatenated identifiers.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.config.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# TTL constants — infrastructure timing, not scientific values
# ---------------------------------------------------------------------------

TTL_SCAN_SUMMARY_S   = 300     # 5 minutes — scan summary (rarely changes post-completion)
TTL_SCAN_LIST_S      = 60      # 1 minute  — history list (new scans arrive)
TTL_CELL_PAGE_S      = 600     # 10 minutes — cell pages (immutable post-freeze)
TTL_VOXEL_PAGE_S     = 600     # 10 minutes — voxel pages (immutable post-twin-build)
TTL_AUDIT_PAGE_S     = 120     # 2 minutes  — audit log (append-only, can grow)

# Cache key namespace prefix — separates Aurora keys from other Redis tenants
_NS = "aurora:v1:"


# ---------------------------------------------------------------------------
# Cache key builders — string identifiers only, no scientific values
# ---------------------------------------------------------------------------

def key_scan_summary(scan_id: str) -> str:
    return f"{_NS}scan:{scan_id}:summary"

def key_scan_list(status: str, commodity: Optional[str], cursor: Optional[str], limit: int) -> str:
    c = commodity or "_all"
    cur = cursor or "_start"
    return f"{_NS}scans:list:{status}:{c}:{cur}:{limit}"

def key_cell_page(scan_id: str, tier: Optional[str], cursor: Optional[str], limit: int) -> str:
    t = tier or "_all"
    cur = cursor or "_start"
    return f"{_NS}cells:{scan_id}:{t}:{cur}:{limit}"

def key_voxel_page(scan_id: str, version: int, depth_min: Optional[float],
                   depth_max: Optional[float], cursor: Optional[str], limit: int) -> str:
    dmin = str(depth_min) if depth_min is not None else "_"
    dmax = str(depth_max) if depth_max is not None else "_"
    cur  = cursor or "_start"
    return f"{_NS}voxels:{scan_id}:v{version}:{dmin}:{dmax}:{cur}:{limit}"

def key_scan_invalidation_pattern(scan_id: str) -> str:
    """Pattern to match ALL cache keys for a given scan_id."""
    return f"{_NS}*{scan_id}*"


# ---------------------------------------------------------------------------
# CacheClient
# ---------------------------------------------------------------------------

class CacheClient:
    """
    Async Redis wrapper for Aurora response caching.

    Stores serialised response dicts as JSON strings.
    Returns deserialised dicts on hit, None on miss.

    PROOF OF RULE 1:
      set(): stores json.dumps(value) — the caller's value unchanged.
      get(): returns json.loads(raw)  — the stored value unchanged.
      No arithmetic, no field access, no scientific transformation.
    """

    def __init__(self, redis_client):
        """
        Args:
            redis_client: async Redis client (e.g. redis.asyncio.Redis).
                          Injected — not constructed here.
        """
        self._redis = redis_client

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a cached value by key. Returns None on miss.
        Returned value is the exact object that was stored via set().
        """
        try:
            raw = await self._redis.get(key)
            if raw is None:
                logger.info("cache_miss", extra={"key": key})
                return None
            logger.info("cache_hit", extra={"key": key})
            return json.loads(raw)
        except Exception as e:
            logger.info("cache_error", extra={"key": key, "error": str(e)})
            return None   # Cache errors fall through to storage — never raise

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """
        Store a value by key with TTL.
        value is serialised with json.dumps(default=str, sort_keys=True).

        PROOF: sort_keys=True is for deterministic serialisation (same dict →
        same bytes on every call). It does not alter numeric precision.
        No float rounding is applied.
        """
        try:
            raw = json.dumps(value, default=str, sort_keys=True)
            await self._redis.set(key, raw, ex=ttl_seconds)
        except Exception as e:
            logger.info("cache_set_error", extra={"key": key, "error": str(e)})

    async def delete(self, key: str) -> None:
        """Delete a single cache key."""
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.info("cache_delete_error", extra={"key": key, "error": str(e)})

    async def invalidate_scan(self, scan_id: str) -> int:
        """
        Invalidate all cache keys associated with a scan_id.
        Called when a scan is reprocessed or its twin is rebuilt.

        Uses SCAN + DELETE pattern (not KEYS) to avoid blocking Redis.
        Returns count of deleted keys.

        RULE 6: Ensures stale outputs are not served after canonical update.
        """
        pattern = key_scan_invalidation_pattern(scan_id)
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.info("cache_invalidate_error", extra={"scan_id": scan_id, "error": str(e)})
        logger.info("cache_invalidated", extra={"scan_id": scan_id, "keys_deleted": deleted})
        return deleted

    async def ping(self) -> bool:
        """Health check — returns True if Redis is reachable."""
        try:
            return await self._redis.ping()
        except Exception:
            return False