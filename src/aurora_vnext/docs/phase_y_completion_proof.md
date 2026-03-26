# Phase Y Completion Proof
## Aurora OSI vNext — Real-World Ground Truth Calibration Layer

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/ground_truth_model.py` | Model | `GroundTruthRecord`, `GroundTruthProvenance`, `ConfidenceWeighting`, `CalibrationScanTrace` |
| `app/services/ground_truth_ingestion.py` | Service | Validation pipeline, type routing, bulk/streaming ingestion, event emission |
| `app/services/calibration_version.py` | Service | `CalibrationVersion` manager, lineage chain, DRAFT→ACTIVE→SUPERSEDED lifecycle |
| `app/storage/ground_truth.py` | Storage | Append-only storage, second synthetic guard, immutability enforcement |
| `app/events/event_bus.py` (extended) | Events | `ground_truth.ingested`, `ground_truth.bulk_ingested`, `calibration.version_created` |
| `docs/real_sources_registry.md` | Registry | 25+ real-world sources mapped to `GeologicalDataType` taxonomy |
| `tests/unit/test_ground_truth_phase_y.py` | Tests | 30 tests across all directives |
| `docs/phase_y_completion_proof.md` | Proof | This document |

---

## 2. Provenance Schema Example

Every `GroundTruthRecord` requires a fully-populated `GroundTruthProvenance`:

```python
GroundTruthProvenance(
    source_name       = "USGS Mineral Resources Data System",
    source_identifier = "https://mrdata.usgs.gov/mrds/record/10009247",
    country           = "ZA",
    commodity         = "gold",
    license_note      = "Public domain — United States Government work",
    ingestion_timestamp = "2026-03-26T09:00:00.000000",
)
```

Any empty field raises `ValueError` at construction — ingestion fails before storage.

---

## 3. Calibration Version Lineage Diagram

```
[ROOT — version_id: uuid-v0]
  status: SUPERSEDED
  parent: None
  applies_to_scans_after: 2026-01-15T08:00:00
  ground_truth_source_ids: ["r-usgs-001"]
  calibration_effect_flags: ["province_prior_updated"]
       │
       ▼
[version_id: uuid-v1]
  status: SUPERSEDED
  parent: uuid-v0
  applies_to_scans_after: 2026-02-20T14:00:00
  ground_truth_source_ids: ["r-usgs-001", "r-bgs-042"]
  calibration_effect_flags: ["lambda_1_updated", "province_prior_updated"]
       │
       ▼
[version_id: uuid-v2]  ← CURRENTLY ACTIVE
  status: ACTIVE
  parent: uuid-v1
  applies_to_scans_after: 2026-03-26T09:00:00
  ground_truth_source_ids: ["r-usgs-001", "r-bgs-042", "r-ga-019"]
  calibration_effect_flags: ["tau_phys_veto_updated"]

Historical scans:
  scan_2026_01_10 → calibration_version_id: uuid-v0  ← FROZEN, never re-scored
  scan_2026_02_18 → calibration_version_id: uuid-v1  ← FROZEN, never re-scored
  scan_2026_03_27 → calibration_version_id: uuid-v2  ← scored under active version
```

**DIRECTIVE 1 PROOF:** `applies_to_scans_after` is set to `utcnow()` at activation.
Scans started before this timestamp are never re-scored. Historical scans are frozen.

**DIRECTIVE 2 PROOF:** uuid-v0 and uuid-v1 are `SUPERSEDED` — not deleted. The full
chain is queryable via `CalibrationVersionManager.get_lineage(uuid-v2)`.

---

## 4. Ingestion Validation Flow

```
GroundTruthRecord
       │
       ▼
[STEP 1] is_synthetic check ──────────── is_synthetic=True → SyntheticDataRejectedError
       │                                                       (REJECTED — logged)
       ▼
[STEP 2] Provenance completeness ──────── any empty field → MissingProvenanceError
       │
       ▼
[STEP 3] Confidence bounds check ──────── any field ∉ [0,1] → MissingConfidenceError
       │
       ▼
[STEP 4] Type-specific payload check ──── missing required key → ValueError
       │                                  (type-routing: 6 types × required keys)
       ▼
[STEP 5] Spatial plausibility ─────────── lat ∉ [-90,90] or lon ∉ [-180,180] → ValueError
       │
       ▼
[STORAGE LAYER] Second synthetic guard ── is_synthetic=True → SyntheticStorageViolation
       │                                  (independent enforcement — cannot be bypassed)
       ▼
[DOMAIN EVENT] ground_truth.ingested ───── emitted to EventBus for downstream consumers
       │
       ▼
[RESULT] IngestionResult(success=True, record_id=..., warnings=[...])
```

---

## 5. Rejection Paths

| Rejection Type | Raised By | Enforcement Layer |
|---|---|---|
| `SyntheticDataRejectedError` | `validate_ground_truth_record()` | Ingestion service (first) |
| `SyntheticStorageViolation` | `GroundTruthStorage.write()` | Storage adapter (second, independent) |
| `MissingProvenanceError` | `validate_ground_truth_record()` | Ingestion service |
| `MissingConfidenceError` | `validate_ground_truth_record()` | Ingestion service |
| `InvalidGeologicalTypeError` | `validate_ground_truth_record()` | Ingestion service |
| `ValueError` (spatial) | `validate_ground_truth_record()` | Ingestion service |
| `ValueError` (type payload) | `_validate_type_payload()` | Ingestion service |
| `DestructiveWriteViolation` | `GroundTruthStorage.write()` | Storage adapter |

---

## 6. Synthetic Data Enforcement Proof

**Three independent enforcement barriers:**

```
1. INGESTION SERVICE (validate_ground_truth_record):
   if record.is_synthetic:
       raise SyntheticDataRejectedError(...)
   # Cannot be bypassed without modifying the record

2. STORAGE ADAPTER (GroundTruthStorage.write):
   if record.is_synthetic:
       raise SyntheticStorageViolation(...)
   # Independent barrier — active even if ingestion service is bypassed

3. CALIBRATION EXECUTOR (GroundTruthStorage.list_approved):
   Returns only records with status == APPROVED.
   Synthetic records are rejected at step 1/2 and never reach APPROVED status.
   # Third implicit barrier — no synthetic record can reach calibration
```

**Permitted synthetic data use:**
Synthetic records may be constructed in test fixtures (see `test_ground_truth_phase_y.py`
`_make_record(is_synthetic=True)`) for testing the rejection paths themselves.
They are never passed to production storage.

---

## 7. Calibration-Scan Traceability Example

When a scan completes under an active calibration version, the pipeline writes:

```python
CalibrationScanTrace(
    scan_id                  = "scan_au_wa_20260327_001",
    calibration_version_id   = "uuid-v2",               # active at scoring time
    ground_truth_source_ids  = ("r-usgs-001", "r-ga-019"),  # GT records used
    calibration_effect_flags = ("lambda_1_updated", "province_prior_updated"),
    traced_at                = "2026-03-27T11:22:33.000000",
)
```

This trace is written once at scan-freeze time and is immutable.
A query for `get_trace("scan_au_wa_20260327_001")` returns this record,
proving exactly which calibration state produced this scan.

**Historical scan traceability is queryable but never modifiable.**

---

## 8. Calibration Output Is Model Configuration Only (Directive 5)

`CalibrationParameters` fields (complete list):

```
province_prior_updates      — dict[province_key, float] — province prior Π
lambda_1_updates            — dict[commodity, float]    — physics gravity penalty
lambda_2_updates            — dict[commodity, float]    — physics Poisson penalty
tau_grav_veto_updates       — dict[commodity, float]    — gravity veto threshold
tau_phys_veto_updates       — dict[commodity, float]    — Poisson veto threshold
uncertainty_model_updates   — dict[param_key, float]    — uncertainty component params
```

**No field in `CalibrationParameters` is:**
- An ACIF score
- A tier assignment
- A gate evaluation result
- Any output that bypasses or duplicates the canonical ACIF formula

Proven by `test_calibration_parameters_has_no_acif_field()` and
`test_calibration_parameters_contains_only_config()`.

---

## 9. Event-Driven Ingestion Architecture (Directive 7)

Three ingestion paths are supported:

| Path | Function | Use Case |
|---|---|---|
| Single record | `ingest_one(record)` | Interactive API upload, operator submission |
| Bulk batch | `ingest_bulk(records)` | National survey dataset sync, bulk import |
| Future streaming | Subscribe to `ground_truth.ingested` EventBus events | Satellite-derived feeds, real-time validation streams |

All paths emit `ground_truth.ingested` domain events, enabling downstream
consumers (calibration executor, audit log, notification) to react without
coupling to the ingestion service.

---

## Phase Y Complete

1. ✅ Directive 1: Calibration never modifies canonical scan outputs — `applies_to_scans_after` enforces future-only application
2. ✅ Directive 2: Immutable version lineage — `SUPERSEDED` not deleted, `get_lineage()` walks full chain
3. ✅ Directive 3: Geological data type taxonomy — 6 types, type-specific payload validation
4. ✅ Directive 4: Explicit confidence weighting — 4 required fields, geometric mean composite, fully auditable
5. ✅ Directive 5: Calibration output is model configuration only — `CalibrationParameters` has zero scoring fields
6. ✅ Directive 6: Synthetic prohibition at ingestion service + storage adapter (two independent barriers)
7. ✅ Directive 7: Event-driven architecture — `ingest_one()`, `ingest_bulk()`, EventBus for streaming
8. ✅ Directive 8: Completion proof delivered with lineage diagram, ingestion flow, provenance example, rejection paths, traceability example
9. ✅ 25+ real-world sources registered in `docs/real_sources_registry.md`
10. ✅ Zero `core/*` imports across all Phase Y files
11. ✅ 30 regression tests