# Aurora Observability Constitution — Permanent Lock
## Ratified: Phase U → Phase V Boundary

---

## Permanent Constitutional Constraint — Observability Scope

The following rule is hereby permanently added to the Aurora OSI vNext system constitution,
with equal authority to the Locked Physics & Mathematics Constitution and the
Architectural Separation Rules established in Phase L.

---

### CONST-OBS-1: Observability is Operational Telemetry Only

> Aurora observability infrastructure — including all files in `app/observability/`,
> all metrics emitted to Prometheus, all traces emitted to OpenTelemetry, and all
> structured log records — is **strictly operational telemetry**.
>
> It must never evolve into a secondary scientific analytics layer.

This constraint is **permanent and irrevocable**. It may not be relaxed by any
future phase, feature, or migration without explicit constitutional amendment
reviewed by the same authority that approved Phases Q through U.

---

### Specific Prohibitions (permanent)

| # | Prohibition | Rationale |
|---|---|---|
| OBS-P1 | No metric may aggregate, derive, normalise, or statistically analyse ACIF values | ACIF is a first-class scientific output produced exclusively by `core/scoring.py`. Any secondary aggregation would constitute an unauthorised re-scoring. |
| OBS-P2 | No metric may compute tier distributions, clustering strength, or prospect ranking | Tier distributions are produced by `core/tiering.py` at canonical freeze. Recomputing them in observability would violate the single-authority rule. |
| OBS-P3 | No metric may compute percentiles, histograms, or statistical moments of scientific floats | Prometheus histograms of infrastructure durations are permitted. Histograms of ACIF score populations are permanently forbidden. |
| OBS-P4 | `scan_tier` metric labels must remain verbatim canonical enum strings | `"TIER_1"`, `"TIER_2"`, `"TIER_3"` — the stored string, never a numeric threshold. If `core/tiering.py` renames the enum, the label string changes accordingly; no re-derivation occurs. |
| OBS-P5 | Canonical scientific floats may only ever be emitted as gated pass-through values | `emit_canonical_acif_gauge()` is the single permitted pathway. It is gated by `EMIT_CANONICAL_SUMMARY_METRICS=true` and calls `Gauge.set(verbatim_float)` — no arithmetic. |
| OBS-P6 | Telemetry code must remain permanently isolated from `core/` modules | No file under `app/observability/` may import from `app.core.*`. Verified by automated test in every phase. |
| OBS-P7 | Pipeline telemetry shims may only measure wall-clock time and integer counts | `instrument_stage()` wraps with `time.monotonic()` only. It must never read the scientific outputs of the stage it wraps. |

---

### Permitted observability operations

For the avoidance of doubt, the following are permanently **permitted**:

- Counting requests, errors, cache hits, queue depth, connection pool usage
- Measuring wall-clock durations (request latency, stage latency, twin build time)
- Emitting integer row counts (`cell_count`, `voxel_count`) as infrastructure metadata
- Logging `scan_id`, `commodity` (string), `environment` (string), `scan_tier` (stored enum) as identifiers
- Emitting verbatim stored canonical floats via the gated pass-through gauge (OBS-P5)
- Tracing infrastructure operations (DB queries, cache ops, HTTP requests, queue ops)

---

### Enforcement mechanism

1. **Automated test gate** — `test_observability_phase_u.py::TestNoScientificImports`
   verifies zero `app.core.*` imports in all three observability modules. This test
   must run in CI for every future phase.

2. **Formatter block** — `_JsonFormatter._BLOCKED_FIELDS` silently drops scientific
   field values from all structured log records. This list must be updated if new
   scientific fields are added to `CanonicalScan`.

3. **Span attribute guard** — `tracing._FORBIDDEN_SPAN_ATTRS` blocks scientific
   values from OTel span labels. Must be updated in parallel with `_BLOCKED_FIELDS`.

4. **Code review gate** — Any future PR touching `app/observability/` must demonstrate
   that no new metric computes a function of any scientific output field.

---

### Constitutional authority

This lock is co-equal with:
- `docs/phase_l_completion_proof.md` — Architectural separation (scientific core isolation)
- `docs/phase_p_completion_proof.md` — Canonical display rules (no fallback injection)
- `docs/phase_r_constitutional_confirmation.md` — Zero-transformation migration fidelity

It supersedes any informal convention or comment that might otherwise suggest
observability could be expanded to serve scientific analytics purposes.

**The Aurora observability layer is, and must remain, an operational mirror —
not a scientific inference engine.**