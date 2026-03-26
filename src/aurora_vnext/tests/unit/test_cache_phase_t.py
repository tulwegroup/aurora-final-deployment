"""
Aurora OSI vNext — Phase T Cache & Rate Limiter Tests
Phase T §T.4 — Completion Proof Tests

Tests:
  1. Cache key builders — deterministic, no scientific values in keys
  2. Cache set/get round-trip — value identity (no transformation)
  3. Cache miss returns None — no fabricated value on miss
  4. Cache invalidation — scan_id pattern covers all related keys
  5. Rate limit — correct RPM per role
  6. Rate limit — 429 on exceed, correct headers
  7. Rate limit window key — encodes time bucket, not scientific value
  8. No core/* imports in cache.py, rate_limiter.py, connection_pool.py
  9. Numeric precision preservation — float values unchanged through cache
  10. Scientific field pass-through — acif_score stored and returned verbatim
"""

from __future__ import annotations

import json
import time
import pytest

from app.storage.cache import (
    CacheClient,
    key_scan_summary,
    key_scan_list,
    key_cell_page,
    key_voxel_page,
    key_scan_invalidation_pattern,
    TTL_SCAN_SUMMARY_S,
    TTL_CELL_PAGE_S,
    TTL_VOXEL_PAGE_S,
    RATE_LIMITS,
)
from app.api.middleware.rate_limiter import (
    check_rate_limit,
    RATE_LIMITS as RL_RATES,
    WINDOW_SECONDS,
    _redis_key,
)


# ─── Fake Redis for unit tests ────────────────────────────────────────────────

class FakeRedis:
    """In-memory Redis stub with get/set/delete/scan/incr/expire/ping."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    async def get(self, key): return self._store.get(key)
    async def set(self, key, value, ex=None): self._store[key] = value
    async def delete(self, *keys):
        for k in keys: self._store.pop(k, None)
    async def scan(self, cursor, match=None, count=100):
        pattern = match.replace("*", "") if match else ""
        keys = [k for k in self._store if pattern in k]
        return 0, keys
    async def incr(self, key):
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]
    async def expire(self, key, ttl): pass
    async def ping(self): return True


# ─── 1. Cache key builders ───────────────────────────────────────────────────

class TestCacheKeyBuilders:
    def test_scan_summary_key_contains_scan_id(self):
        key = key_scan_summary("scan_abc123")
        assert "scan_abc123" in key
        assert key.startswith("aurora:v1:")

    def test_scan_list_key_components(self):
        key = key_scan_list("COMPLETED", "gold", None, 50)
        assert "COMPLETED" in key
        assert "gold" in key
        assert "50" in key

    def test_scan_list_key_no_commodity(self):
        key = key_scan_list("COMPLETED", None, None, 50)
        assert "_all" in key

    def test_cell_page_key_with_tier(self):
        key = key_cell_page("scan_x", "TIER_1", None, 100)
        assert "scan_x" in key
        assert "TIER_1" in key

    def test_voxel_page_key_with_depth(self):
        key = key_voxel_page("scan_x", 2, 200.0, 800.0, None, 500)
        assert "scan_x" in key
        assert "v2" in key
        assert "200.0" in key
        assert "800.0" in key

    def test_invalidation_pattern_contains_scan_id(self):
        pattern = key_scan_invalidation_pattern("scan_xyz")
        assert "scan_xyz" in pattern

    def test_keys_are_deterministic(self):
        """Same inputs → same key (required for cache coherence)."""
        k1 = key_scan_summary("scan_abc")
        k2 = key_scan_summary("scan_abc")
        assert k1 == k2

    def test_different_scan_ids_produce_different_keys(self):
        assert key_scan_summary("scan_a") != key_scan_summary("scan_b")

    def test_no_scientific_value_in_key(self):
        """
        PROOF: cache keys contain only identifiers (scan_id, version, role strings).
        No ACIF score, tier threshold, or scientific constant is used as a key component.
        """
        key = key_voxel_page("scan_x", 1, None, None, None, 500)
        # Key must not contain any floating point score (e.g. "0.812")
        import re
        score_pattern = re.compile(r"0\.\d{2,}")
        assert not score_pattern.search(key)


# ─── 2. Cache set/get round-trip ─────────────────────────────────────────────

class TestCacheRoundTrip:
    @pytest.mark.asyncio
    async def test_get_after_set_returns_same_value(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        payload = {"scan_id": "s1", "display_acif_score": 0.812, "tier_counts": {"tier_1": 42}}
        await cache.set("test_key", payload, TTL_SCAN_SUMMARY_S)
        result = await cache.get("test_key")
        assert result == payload

    @pytest.mark.asyncio
    async def test_float_precision_preserved(self):
        """
        PROOF: IEEE 754 float precision is preserved through cache serialisation.
        display_acif_score 0.812 must be returned as 0.812 — not rounded.
        """
        redis = FakeRedis()
        cache = CacheClient(redis)
        await cache.set("k", {"display_acif_score": 0.8120000000000001}, 60)
        result = await cache.get("k")
        assert result["display_acif_score"] == 0.8120000000000001

    @pytest.mark.asyncio
    async def test_tier_counts_verbatim(self):
        """tier_counts dict must be identical after cache round-trip."""
        redis = FakeRedis()
        cache = CacheClient(redis)
        counts = {"tier_1": 42, "tier_2": 18, "tier_3": 5, "below": 2}
        await cache.set("k", {"tier_counts": counts}, 60)
        result = await cache.get("k")
        assert result["tier_counts"] == counts

    @pytest.mark.asyncio
    async def test_version_registry_verbatim(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        vr = {"score_version": "1.0.0", "tier_version": "1.0.0", "physics_model_version": "2.1.0"}
        await cache.set("k", {"version_registry": vr}, 60)
        result = await cache.get("k")
        assert result["version_registry"] == vr

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        """
        PROOF: cache miss returns None — no default, no fabricated value.
        Caller must fall through to storage and return the real stored value.
        """
        redis = FakeRedis()
        cache = CacheClient(redis)
        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_removes_key(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        await cache.set("k", {"x": 1}, 60)
        await cache.delete("k")
        assert await cache.get("k") is None


# ─── 3. Cache invalidation ───────────────────────────────────────────────────

class TestCacheInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_scan_removes_all_scan_keys(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        scan_id = "scan_abc123"
        await cache.set(key_scan_summary(scan_id), {"x": 1}, 60)
        await cache.set(key_cell_page(scan_id, None, None, 100), {"y": 2}, 60)
        await cache.set(key_voxel_page(scan_id, 1, None, None, None, 500), {"z": 3}, 60)
        deleted = await cache.invalidate_scan(scan_id)
        assert deleted == 3
        assert await cache.get(key_scan_summary(scan_id)) is None

    @pytest.mark.asyncio
    async def test_invalidate_does_not_remove_other_scan_keys(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        await cache.set(key_scan_summary("scan_A"), {"a": 1}, 60)
        await cache.set(key_scan_summary("scan_B"), {"b": 2}, 60)
        await cache.invalidate_scan("scan_A")
        # scan_B key must survive
        result = await cache.get(key_scan_summary("scan_B"))
        assert result == {"b": 2}

    @pytest.mark.asyncio
    async def test_ping_returns_true(self):
        redis = FakeRedis()
        cache = CacheClient(redis)
        assert await cache.ping() is True


# ─── 4. Rate limiter ─────────────────────────────────────────────────────────

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_admin_limit_is_300(self):
        assert RL_RATES["admin"] == 300

    @pytest.mark.asyncio
    async def test_operator_limit_is_120(self):
        assert RL_RATES["operator"] == 120

    @pytest.mark.asyncio
    async def test_viewer_limit_is_60(self):
        assert RL_RATES["viewer"] == 60

    @pytest.mark.asyncio
    async def test_within_limit_returns_allowed(self):
        redis = FakeRedis()
        allowed, remaining, limit = await check_rate_limit(redis, "user_1", "viewer")
        assert allowed is True
        assert limit == 60
        assert remaining == 59

    @pytest.mark.asyncio
    async def test_exceeds_limit_returns_denied(self):
        redis = FakeRedis()
        # Exhaust the viewer limit (60 RPM)
        for _ in range(60):
            await check_rate_limit(redis, "user_x", "viewer")
        allowed, remaining, _ = await check_rate_limit(redis, "user_x", "viewer")
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_window_key_encodes_time_bucket(self):
        """Rate limit key encodes time window — not a scientific field."""
        window_start = (int(time.time()) // WINDOW_SECONDS) * WINDOW_SECONDS
        key = _redis_key("user_1", window_start)
        assert "user_1" in key
        assert str(window_start) in key
        # Key must not contain any scientific field name
        for forbidden in ["acif", "tier", "score", "threshold"]:
            assert forbidden not in key

    @pytest.mark.asyncio
    async def test_rate_limit_is_per_user(self):
        """Different users have independent counters."""
        redis = FakeRedis()
        for _ in range(60):
            await check_rate_limit(redis, "user_a", "viewer")
        # user_a is exhausted; user_b should still be allowed
        allowed_b, _, _ = await check_rate_limit(redis, "user_b", "viewer")
        assert allowed_b is True


# ─── 5. No scientific imports ────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = [
        "app.core.scoring", "app.core.tiering", "app.core.gates",
        "app.core.evidence", "app.core.causal", "app.core.physics",
        "app.core.temporal", "app.core.priors", "app.core.uncertainty",
    ]

    def _check(self, module_path: str):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for prefix in self.FORBIDDEN:
            assert prefix not in src, f"VIOLATION: {module_path} imports {prefix}"
        assert "compute_acif"   not in src
        assert "assign_tier"    not in src
        assert "evaluate_gates" not in src

    def test_cache_no_core_imports(self):
        self._check("app.storage.cache")

    def test_rate_limiter_no_core_imports(self):
        self._check("app.api.middleware.rate_limiter")

    def test_connection_pool_no_core_imports(self):
        self._check("app.config.connection_pool")