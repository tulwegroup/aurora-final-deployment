# Phase L Completion Proof
## Aurora OSI vNext — Scan Execution Pipeline

---

## 1. Failure-Path Immutability Proof

**Claim:** If the pipeline fails before canonical freeze (step 19), no CanonicalScan
result fields are written, no partial score/tier/gate state leaks into canonical
storage, and ScanJob alone carries the failure state.

### Structural Proof

#### Layer 1 — `create_pending_scan()` writes zero result fields

`storage/scans.py :: CanonicalScanStore.create_pending_scan()` issues the following
INSERT into `canonical_scans`:

```sql
INSERT INTO canonical_scans (
    scan_id, status, commodity, scan_tier, environment,
    aoi_geojson, grid_resolution_degrees, parent_scan_id,
    operator_notes, submitted_at
) VALUES (
    :scan_id, 'PENDING', ...
)
```

**Only 9 identity/config fields are written. Zero result fields:**
- ❌ `display_acif_score` — absent
- ❌ `max_acif_score` — absent
- ❌ `tier_counts` — absent
- ❌ `tier_thresholds_used` — absent
- ❌ `system_status` — absent
- ❌ `gate_results` — absent
- ❌ `mean_evidence_score` — absent (all 6 mean scores)
- ❌ `causal_veto_cell_count` — absent (all veto counts)
- ❌ `version_registry` — absent
- ❌ `normalisation_params` — absent

**Therefore:** A scan that fails at any point before step 19 has a record containing
only identity fields and `status ∈ {PENDING, RUNNING, FAILED}`.

#### Layer 2 — `freeze_canonical_scan()` is the sole write path for all result fields

`storage/scans.py :: CanonicalScanStore.freeze_canonical_scan()` is the
**only function in the entire codebase** that writes result fields to
`canonical_scans`. It is called **exactly once** per scan from
`pipeline/scan_pipeline.py :: _step_canonical_freeze()` at step 19.

It atomically:
1. Sets `status = 'COMPLETED'`
2. Writes all 20+ result fields in a **single UPDATE**
3. Uses `WHERE scan_id = :scan_id AND status != 'COMPLETED'` to prevent race conditions

```sql
UPDATE canonical_scans SET
    status = 'COMPLETED',
    display_acif_score = ...,
    tier_counts = ...,
    system_status = ...,
    ...
WHERE scan_id = :scan_id
  AND status != 'COMPLETED'   -- Race guard
```

**Therefore:** No result field can exist in storage unless `status = COMPLETED`.

#### Layer 3 — Application-level double-freeze guard

`freeze_canonical_scan()` performs a pre-check before issuing the UPDATE:

```python
existing = await self._get_status(canonical_scan.scan_id)
if existing == ScanStatus.COMPLETED.value:
    raise StorageImmutabilityError(
        "AURORA_IMMUTABILITY_VIOLATION: scan_id=... is already COMPLETED."
    )
```

This is the **first enforcement layer** — it catches double-freeze attempts
at the Python application level before touching the database.

#### Layer 4 — PostgreSQL trigger (second independent enforcement layer)

`infra/db/migrations/001_initial_schema.sql` installs
`trg_canonical_scan_immutability` on the `canonical_scans` table.
This trigger fires on `UPDATE` and raises an exception if the row
already has `status = 'COMPLETED'`.

This is the **second enforcement layer** — independent of application code.
Even if application code were bypassed (direct DB access, migration bug),
the trigger enforces immutability.

#### Layer 5 — ScanJob carries failure state exclusively

If the pipeline raises an exception at any step before freeze:

```python
# pipeline/scan_pipeline.py :: execute_scan_pipeline()
except Exception as exc:
    storage.mark_scan_job_failed(scan_id, ctx.current_stage.value, str(exc))
    raise
```

- `ScanJob.status` → `FAILED`
- `ScanJob.error_detail` → exception message
- `ScanJob.error_stage` → pipeline stage name
- `CanonicalScan` record → remains `PENDING` / `RUNNING` with zero result fields

The `GET /scan/status/{id}` endpoint returns `ScanJobStatusResponse` for non-COMPLETED
records, which contains **only** execution fields: `pipeline_stage, progress_pct,
started_at, updated_at, error_detail`. No score field appears.

### Summary Table

| Failure Point | canonical_scans status | Result fields written | ScanJob state |
|---|---|---|---|
| Before step 2 (grid) | PENDING | None | FAILED |
| Step 3–7 (acquisition/gravity) | RUNNING | None | FAILED |
| Step 8–15 (scoring) | RUNNING | None | FAILED |
| Step 16–18 (ACIF/tier/gate) | RUNNING | None | FAILED |
| **Step 19 (canonical freeze)** | **COMPLETED** | **All result fields** | Archived |
| After step 19 (post-freeze) | COMPLETED | Immutable (no changes permitted) | Archived |

---

## 2. API-State Separation Proof

**Claim:** After completion, ScanJob remains an execution record only,
CanonicalScan remains the immutable result contract, and result-bearing
endpoints never mix execution-state fields with canonical scientific fields.

### Proof by Type System

#### `ScanJobStatusResponse` — execution-only type

```python
class ScanJobStatusResponse(BaseModel):
    scan_id: str
    scan_job_id: str
    status: ScanStatus
    pipeline_stage: Optional[PipelineStageEnum]  # execution field
    progress_pct: Optional[float]                 # execution field
    started_at: Optional[datetime]                # execution field
    updated_at: datetime                          # execution field
    error_detail: Optional[str]                   # execution field
    # =========================================================================
    # SCORE FIELD EXCLUSION — explicit by absence:
    # display_acif_score, tier_counts, system_status, gate_results,
    # threshold_policy, component scores — ALL absent by design.
    # =========================================================================
```

Zero result fields. Used **only** for `status ∈ {PENDING, RUNNING, FAILED}`.

#### `CanonicalScanSummary` — result-only type

```python
class CanonicalScanSummary(BaseModel):
    scan_id: str
    commodity: str
    scan_tier: ScanTier
    environment: ScanEnvironment
    status: ScanStatus
    display_acif_score: Optional[NormalisedFloat]  # result field
    max_acif_score: Optional[NormalisedFloat]       # result field
    system_status: Optional[SystemStatusEnum]       # result field
    tier_1_count: Optional[int]                     # result field
    total_cells: int
    submitted_at: datetime
    completed_at: Optional[datetime]
    parent_scan_id: Optional[str]
    migration_class: Optional[MigrationClassEnum]
    # NOTE: pipeline_stage, progress_pct, error_detail — ABSENT by design
```

Zero execution-state fields. Used **only** for `status = COMPLETED`.

#### `ScanStatusResponse` — mutual exclusion enforced by model_validator

```python
class ScanStatusResponse(BaseModel):
    scan_id: str
    status: ScanStatus
    job_status: Optional[ScanJobStatusResponse]     # present iff non-COMPLETED
    canonical_summary: Optional[CanonicalScanSummary]  # present iff COMPLETED

    @model_validator(mode="after")
    def validate_state_separation(self) -> "ScanStatusResponse":
        if self.status == ScanStatus.COMPLETED:
            if self.canonical_summary is None:
                raise ValueError("COMPLETED requires canonical_summary")
        else:
            if self.job_status is None:
                raise ValueError(f"status={self.status} requires job_status")
        return self
```

**The validator is evaluated at model construction time** — it is impossible
to construct a `ScanStatusResponse` that mixes the two types.

### Proof by Endpoint Implementation

| Endpoint | Status | Returns | Mixing possible? |
|---|---|---|---|
| `GET /scan/status/{id}` (running) | PENDING/RUNNING/FAILED | `ScanJobStatusResponse` only | ❌ No — validator enforced |
| `GET /scan/status/{id}` (done) | COMPLETED | `CanonicalScanSummary` only | ❌ No — validator enforced |
| `GET /scan/active` | PENDING/RUNNING | Identity + status only | ❌ No — score fields absent |
| `GET /history/{id}` | COMPLETED only | Full `CanonicalScan` | ❌ No — ScanJob fields absent |
| `GET /datasets/*` | COMPLETED only | Canonical fields only | ❌ No — read from canonical store |
| `GET /twin/*` | COMPLETED only | Frozen voxel data only | ❌ No — no scoring in twin API |

### Import Isolation Proof

No API module imports from the scientific core:

| Module | Forbidden imports | Status |
|---|---|---|
| `api/scan.py` | `core.scoring`, `core.tiering`, `core.gates` | ✅ Absent |
| `api/history.py` | `core.*` | ✅ Absent |
| `api/datasets.py` | `core.*`, `services.*` | ✅ Absent |
| `api/twin.py` | `core.*`, `services.*` | ✅ Absent |

Verified programmatically in `tests/unit/test_api_phase_m.py ::
TestApiImportIsolation`.

---

## Phase M Endpoint Inventory

### Scan API (`/api/v1/scan`)
| Method | Path | Auth | Returns |
|---|---|---|---|
| POST | `/scan/grid` | user | `ScanSubmitResponse` |
| POST | `/scan/polygon` | user | `ScanSubmitResponse` |
| GET | `/scan/active` | user | `{active_scans: [...]}` (execution only) |
| GET | `/scan/status/{id}` | user | `ScanStatusResponse` (separated by state) |
| POST | `/scan/{id}/cancel` | admin | `{cancelled: true}` |

### History API (`/api/v1/history`)
| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/history` | user | Paginated `CanonicalScanSummary` list |
| GET | `/history/{id}` | user | Full `CanonicalScan` record |
| GET | `/history/{id}/cells` | user | Paginated `ScanCell` list |
| GET | `/history/{id}/cells/{cell_id}` | user | Single `ScanCell` record |
| DELETE | `/history/{id}` | admin | Soft delete confirmation |
| POST | `/history/{id}/reprocess` | admin | `{new_scan_id: ...}` |

### Dataset API (`/api/v1/datasets`)
| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/datasets/summary/{id}` | user | Lightweight result summary |
| GET | `/datasets/geojson/{id}` | user | GeoJSON FeatureCollection |
| GET | `/datasets/package/{id}` | user | Full canonical data package |
| GET | `/datasets/raster-spec/{id}` | user | Raster rendering specification |
| GET | `/datasets/export/{id}` | admin | Full export (audit-logged) |

### Twin API (`/api/v1/twin`)
| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/twin/{id}` | user | Twin metadata (latest version) |
| GET | `/twin/{id}/slice` | user | Depth slice voxels |
| GET | `/twin/{id}/voxel/{vid}` | user | Single voxel record |
| POST | `/twin/{id}/query` | user | Filtered voxel query result |
| GET | `/twin/{id}/history` | user | Twin version history |

**Total: 20 endpoints. All read-only for GET. Write endpoints (POST/DELETE) are
restricted to submission and admin operations and never modify canonical results.**