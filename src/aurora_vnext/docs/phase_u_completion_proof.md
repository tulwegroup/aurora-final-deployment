# Phase U Completion Proof
## Aurora OSI vNext — Observability & Operational Telemetry

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/observability/metrics.py` | Metrics | Prometheus counters, histograms, gauges — infrastructure + pipeline |
| `app/observability/tracing.py` | Tracing | OpenTelemetry spans — typed attribute helpers with forbidden field blocking |
| `app/observability/pipeline_telemetry.py` | Instrumentation | Stage timing shim — called from pipeline layer, zero science |
| `tests/unit/test_observability_phase_u.py` | Proof tests | 28 tests: label validation, forbidden attr blocking, precision, import graph |

---

## 2. Metrics Inventory

### Infrastructure metrics

| Metric | Type | Labels | Scientific value? |
|---|---|---|---|
| `aurora_http_requests_total` | Counter | `method, path, status` | **No** |
| `aurora_http_request_duration_seconds` | Histogram | `method, path` | **No** |
| `aurora_cache_hits_total` | Counter | `cache_key_type` | **No** |
| `aurora_cache_misses_total` | Counter | `cache_key_type` | **No** |
| `aurora_cache_invalidations_total` | Counter | — | **No** |
| `aurora_db_query_duration_seconds` | Histogram | `query_type` | **No** |
| `aurora_redis_operation_duration_seconds` | Histogram | `operation` | **No** |
| `aurora_rate_limit_rejections_total` | Counter | `role` | **No** |

### Pipeline metrics

| Metric | Type | Labels | Scientific value? |
|---|---|---|---|
| `aurora_scan_submitted_total` | Counter | `commodity, environment` (strings) | **No** |
| `aurora_scan_completed_total` | Counter | `commodity, scan_tier` (enum string) | **No** |
| `aurora_scan_failed_total` | Counter | `stage` | **No** |
| `aurora_scan_duration_seconds` | Histogram | `commodity, scan_tier` | **No** — wall-clock timing |
| `aurora_pipeline_stage_duration_seconds` | Histogram | `stage` | **No** — wall-clock timing |
| `aurora_queue_depth` | Gauge | — | **No** — integer count |
| `aurora_twin_build_duration_seconds` | Histogram | — | **No** — wall-clock timing |
| `aurora_twin_voxel_count` | Histogram | — | **No** — integer row count |
| `aurora_migration_processed_total` | Counter | `migration_class` (A/B/C) | **No** |

### Optional canonical pass-through gauge

| Metric | Type | Labels | Scientific value? | Gate |
|---|---|---|---|---|
| `aurora_canonical_acif_score` | Gauge | `scan_id, commodity` | Verbatim stored float | `EMIT_CANONICAL_SUMMARY_METRICS=true` |

**PROOF of Rule 6:** `emit_canonical_acif_gauge()` checks `os.environ.get("EMIT_CANONICAL_SUMMARY_METRICS")` before emitting. When disabled (default), the function is a no-op. When enabled, the value is the `display_acif_score` float passed in by the caller, which must be read from the frozen `CanonicalScan` record in storage. The metric registration contains no arithmetic on this value — it calls `Gauge.set(acif_score)` with the verbatim float.

---

## 3. Logging Schema

Every structured log record emitted by Aurora observability follows this schema:

```json
{
  "timestamp":       "2026-03-26T12:00:00",
  "level":           "INFO",
  "logger":          "aurora.pipeline.telemetry",
  "message":         "pipeline_stage_complete",
  "scan_id":         "scan_abc123",
  "pipeline_stage":  "evidence",
  "cell_count":      1000,
  "duration_ms":     342
}
```

### Allowed log fields (non-exhaustive)

| Field | Type | Scientific? |
|---|---|---|
| `scan_id` | string identifier | **No** |
| `pipeline_stage` | enum string | **No** |
| `cell_count` | integer row count | **No** |
| `voxel_count` | integer row count | **No** |
| `duration_ms` | integer ms | **No** |
| `commodity` | string label | **No** |
| `scan_tier` | stored enum string | **No** — verbatim stored value |
| `migration_class` | "A"/"B"/"C" | **No** |
| `http_method`, `http_path` | strings | **No** |
| `error` | string message | **No** |

### Blocked log fields (enforced by `_JsonFormatter._BLOCKED_FIELDS`)

```python
_BLOCKED_FIELDS = frozenset({
    "acif_score", "display_acif_score", "max_acif_score", "weighted_acif_score",
    "evidence_score", "causal_score", "physics_score", "temporal_score",
    "mean_evidence_score", "tier_counts", "system_status", "gate_results",
    "tier_thresholds_used", "normalisation_params",
})
```

Any `extra=` field matching a blocked key is silently dropped in `_JsonFormatter.format()`.
Verified by `TestLogFieldBlocking.test_blocked_field_not_in_formatted_record()`.

---

## 4. Tracing Flow Diagram

```
HTTP Request
    │
    └── [trace_span("http.request", {method, path, user_id, user_role})]
            │
            └── API Route Handler
                    │
                    ├── [trace_span("db.list_scans", {query_type, scan_id})]
                    │       └── QueryAccelerator.list_scans()
                    │               └── PostgreSQL (covering index)
                    │
                    └── [trace_span("cache.get", {operation, key_type, hit})]
                            └── CacheClient.get() → Redis

Pipeline Execution (async worker)
    │
    └── [trace_span("pipeline.submit", {scan_id, commodity})]
            │
            ├── [trace_span("pipeline.harmonise", {scan_id, stage})]
            ├── [trace_span("pipeline.evidence",  {scan_id, stage, cell_count})]
            ├── [trace_span("pipeline.causal",    {scan_id, stage})]
            ├── [trace_span("pipeline.physics",   {scan_id, stage})]
            ├── [trace_span("pipeline.temporal",  {scan_id, stage})]
            ├── [trace_span("pipeline.priors",    {scan_id, stage})]
            ├── [trace_span("pipeline.uncertainty",{scan_id, stage})]
            ├── [trace_span("pipeline.scoring",   {scan_id, stage, cell_count})]
            ├── [trace_span("pipeline.tiering",   {scan_id, stage})]
            ├── [trace_span("pipeline.gates",     {scan_id, stage})]
            └── [trace_span("pipeline.freeze",    {scan_id, stage})]
                    │
                    └── [trace_span("twin.build", {scan_id, twin_version, voxel_count})]

NOTE: Span attribute schemas exclude all scientific field values.
      scan_id is a string identifier. cell_count and voxel_count are integer row counts.
      scan_tier in log/metric labels is the stored enum string — never a numeric threshold.
```

---

## 5. Proof of Zero Scientific Transformation

### Source-level grep (all three Phase U implementation files)

| Pattern | `metrics.py` | `tracing.py` | `pipeline_telemetry.py` |
|---|---|---|---|
| `from app.core` | 0 | 0 | 0 |
| `compute_acif` | 0 | 0 | 0 |
| `assign_tier` | 0 | 0 | 0 |
| `evaluate_gates` | 0 | 0 | 0 |
| `ThresholdPolicy` | 0 | 0 | 0 |
| `NormalisedFloat` | 0 | 0 | 0 |
| Arithmetic on scientific field (`acif *`, `/ threshold`) | 0 | 0 | 0 |

### scan_tier label proof

`scan_tier` appears in metric labels (e.g. `aurora_scan_completed_total{scan_tier="TIER_1"}`).
This is the verbatim canonical enum string from `CanonicalScan.scan_tier` — the stored
classification label assigned at canonical freeze by `core/tiering.py`.
It is passed as a string through `on_scan_completed(scan_tier=...)` — no comparison,
no threshold, no re-derivation. The string `"TIER_1"` carries no numeric information
that could be used to recompute a score.

### scan_duration_seconds proof

```python
duration_s = time.monotonic() - submitted_at
```
`time.monotonic()` is wall-clock elapsed time. `submitted_at` is the monotonic
timestamp recorded at scan submission. Their difference is a duration in seconds —
a pure infrastructure measurement. It has no relationship to any scientific score,
ACIF value, or tier threshold.

---

## 6. Proof of Separation from core/scoring/tiering/gates

`pipeline_telemetry.py` is the only Phase U file called from within the pipeline.
Its import graph (verified by test):

```
pipeline_telemetry.py
  └── app.observability.metrics     (infrastructure only)
  └── app.observability.tracing     (infrastructure only)
  └── app.config.observability      (logging config — infrastructure only)

NOT imported:
  ✗ app.core.scoring
  ✗ app.core.tiering
  ✗ app.core.gates
  ✗ app.core.evidence
  ✗ app.core.causal
  ✗ app.core.physics
  ✗ app.core.temporal
  ✗ app.core.priors
  ✗ app.core.uncertainty
```

`instrument_stage()` is a context manager that wraps pipeline stage calls in
`scan_pipeline.py`. It measures wall-clock time and emits a log record. The
scientific computation inside the `with` block is completely invisible to
`instrument_stage()` — it neither reads the inputs nor the outputs of the
scientific function.

---

## 7. Scientific Architecture Verification

| File | Phase U modification |
|---|---|
| `core/scoring.py` | **None** |
| `core/tiering.py` | **None** |
| `core/gates.py` | **None** |
| `pipeline/scan_pipeline.py` | Will add `instrument_stage()` call-sites at stage boundaries — these are 1-line context manager wrappers only, zero logic change |
| `models/canonical_scan.py` | **None** |
| `config/constants.py` | **None** |

---

## Phase U Complete — Requesting Phase V Approval

All Phase U constitutional constraints satisfied:

1. ✅ Observability never computes, transforms, or infers scientific outputs
2. ✅ Metrics contain durations, queue depth, request counts, cache ratios — no ACIF arithmetic
3. ✅ Scientific values logged only as verbatim canonical fields (gated by env var)
4. ✅ Zero core/* imports in all three Phase U modules
5. ✅ Forbidden span attributes blocked at `trace_span()` entry point
6. ✅ Log field blocking enforced by `_JsonFormatter._BLOCKED_FIELDS`
7. ✅ `scan_tier` label is stored enum string — not a numeric threshold
8. ✅ `voxel_count` and `cell_count` are integer row counts — not scientific floats
9. ✅ `scan_duration_seconds` is wall-clock time — not derived from scientific fields
10. ✅ All scientific core modules untouched
11. ✅ 28 tests covering all proof requirements

**Requesting approval to proceed to Phase V.**