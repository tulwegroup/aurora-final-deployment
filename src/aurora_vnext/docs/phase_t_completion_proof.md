# Phase T Completion Proof
## Aurora OSI vNext — API Response Caching, Connection Pool Management, Rate Limiting

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/storage/cache.py` | Caching | Redis-backed response cache — verbatim store/retrieve, scan invalidation |
| `app/api/middleware/rate_limiter.py` | Rate limiting | Token bucket middleware — per-role RPM limits via Redis INCR |
| `app/config/connection_pool.py` | Connection pooling | SQLAlchemy async engine + Redis client pool factories + FastAPI lifespan |
| `tests/unit/test_cache_phase_t.py` | Proof tests | 28 tests: round-trip fidelity, precision, invalidation, rate limits, import graph |

---

## 2. Constitutional Compliance Proof

### Zero scientific transformations

| Operation | File | Scientific transformation? |
|---|---|---|
| `cache.set(key, value, ttl)` | `cache.py` | **None** — `json.dumps(value)` stores verbatim |
| `cache.get(key)` | `cache.py` | **None** — `json.loads(raw)` restores verbatim |
| `cache.invalidate_scan(scan_id)` | `cache.py` | **None** — Redis SCAN + DELETE on key pattern |
| `check_rate_limit(redis, user_id, role)` | `rate_limiter.py` | **None** — Redis INCR on request counter |
| `create_db_engine()` | `connection_pool.py` | **None** — SQLAlchemy engine configuration |

### Source-level grep results (all Phase T files)

| Pattern | `cache.py` | `rate_limiter.py` | `connection_pool.py` |
|---|---|---|---|
| `from app.core` | 0 | 0 | 0 |
| `compute_acif` | 0 | 0 | 0 |
| `assign_tier` | 0 | 0 | 0 |
| `evaluate_gates` | 0 | 0 | 0 |
| `ThresholdPolicy` | 0 | 0 | 0 |
| `NormalisedFloat` | 0 | 0 | 0 |
| Numeric literal on scientific field | 0 | 0 | 0 |

---

## 3. Numeric Precision Preservation Proof

`CacheClient.set()` uses:
```python
json.dumps(value, default=str, sort_keys=True)
```

Python's `json.dumps` without `float` argument uses the default float repr,
which is the shortest string that round-trips to the same IEEE 754 value.
For `display_acif_score = 0.812`:
- Stored as `"0.812"` (exact round-trip)
- Retrieved as `0.812` (identical float)

For `display_acif_score = 0.8120000000000001` (IEEE 754 representation artefact):
- Stored as `"0.8120000000000001"`
- Retrieved as `0.8120000000000001` (identical — no rounding applied)

`sort_keys=True` is for deterministic byte output (same dict → same hash on manifests).
It does not alter numeric values.

**Test coverage:** `TestCacheRoundTrip.test_float_precision_preserved()` explicitly
asserts that `0.8120000000000001` survives a cache round-trip unchanged.

---

## 4. No Scientific Constants Introduced

### Rate limit constants

| Constant | Value | Justification |
|---|---|---|
| `RATE_LIMITS["admin"]` | 300 | Infrastructure RPM — not a scientific value |
| `RATE_LIMITS["operator"]` | 120 | Infrastructure RPM |
| `RATE_LIMITS["viewer"]` | 60 | Infrastructure RPM |
| `WINDOW_SECONDS` | 60 | Sliding window duration (seconds) — standard rate limit convention |

None of these are related to ACIF scores, tier thresholds, evidence weights,
or any physics/scoring parameter. They are request throughput controls.

### Connection pool constants

| Constant | Value | Justification |
|---|---|---|
| `DB_POOL_SIZE` | 10 | One connection per worker (infrastructure) |
| `DB_MAX_OVERFLOW` | 20 | Burst headroom (infrastructure) |
| `DB_POOL_TIMEOUT` | 30 | HTTP timeout alignment (infrastructure) |
| `DB_POOL_RECYCLE` | 3600 | AWS RDS idle TCP drop prevention (infrastructure) |
| `REDIS_POOL_SIZE` | 20 | Async worker concurrency (infrastructure) |

All documented in `connection_pool.py` docstring. None are physics-justified.
None require version registration. None appear in any scientific computation path.

### TTL constants

| Constant | Value | Justification |
|---|---|---|
| `TTL_SCAN_SUMMARY_S` | 300 | 5 min — scan summaries rarely change post-completion |
| `TTL_SCAN_LIST_S` | 60 | 1 min — new scans arrive regularly |
| `TTL_CELL_PAGE_S` | 600 | 10 min — cells immutable post-freeze |
| `TTL_VOXEL_PAGE_S` | 600 | 10 min — voxels immutable post-twin-build |
| `TTL_AUDIT_PAGE_S` | 120 | 2 min — audit log is append-only |

All are cache expiry durations in seconds — not scientific parameters.

---

## 5. Cache Key Design — No Scientific Values in Keys

Cache keys are composed exclusively of:
- Namespace prefix: `aurora:v1:`
- Entity type: `scan`, `scans`, `cells`, `voxels`
- Identifier: `scan_id`, `twin_version`
- Filter strings: `status`, `commodity`, `tier_filter` — string equality values only
- Pagination cursor: timestamp string or entity ID
- Limit: integer

No ACIF score, tier threshold, kernel weight, or scientific constant is used
as a cache key component. Verified by `TestCacheKeyBuilders.test_no_scientific_value_in_key()`.

---

## 6. Cache Invalidation — Stale Output Prevention (Rule 6)

When a scan is reprocessed:
1. `pipeline/scan_pipeline.py` writes new canonical record (existing mechanism)
2. On twin rebuild: `cache.invalidate_scan(scan_id)` is called
3. All `aurora:v1:*{scan_id}*` keys are deleted via SCAN + DEL (non-blocking)
4. Next request falls through to storage → fresh canonical record returned

This ensures frozen canonical outputs remain byte-stable from the storage
perspective, while stale cache entries never serve outdated scientific outputs.

---

## 7. Architectural Separation Verification

| Layer | Phase T modification |
|---|---|
| `core/scoring.py` | **None** |
| `core/tiering.py` | **None** |
| `core/gates.py` | **None** |
| `pipeline/scan_pipeline.py` | **None** |
| `models/canonical_scan.py` | **None** |
| `config/constants.py` | **None** |
| Storage/query layer | Cache added as pass-through wrapper — values unchanged |
| API layer | Rate limiter added as middleware — response bodies unchanged |

---

## 8. Version Registry Propagation

`version_registry` from `CanonicalScan` passes through the cache unchanged:
- Storage layer writes it to DB at canonical freeze (existing pipeline)
- Query layer reads it verbatim (Phase S `QueryAccelerator`)
- Cache layer stores and returns it verbatim (Phase T `CacheClient`)
- Data room manifest copies it verbatim (Phase R `DataRoomManifest`)
- Twin builder reads it for lineage (Phase N `TwinBuildManifest`)

At no layer is `version_registry` altered, recomputed, or defaulted.
Verified by `TestCacheRoundTrip.test_version_registry_verbatim()`.

---

## Phase T Complete

All constitutional constraints satisfied:

1. ✅ Zero scientific transformations in all Phase T files
2. ✅ Zero core/* imports
3. ✅ No scientific constants introduced (rate limits and pool sizes are infrastructure)
4. ✅ Float precision preserved through cache round-trip (IEEE 754 full precision)
5. ✅ `display_acif_score`, `tier_counts`, `version_registry`, `system_status` verbatim in cache
6. ✅ Cache miss returns None — no fabricated default values
7. ✅ Scan invalidation ensures stale scientific outputs are never served
8. ✅ All scientific core modules untouched
9. ✅ Architectural separation preserved — storage/query/API layers remain zero-math
10. ✅ 28 tests covering round-trip fidelity, precision, invalidation, rate limits, import graph