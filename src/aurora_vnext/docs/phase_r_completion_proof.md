# Phase R Completion Proof
## Aurora OSI vNext — Legacy Migration + Data Room Packaging

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/data_room_model.py` | Schema | `DataRoomManifest`, `ArtifactRecord`, `ScanLineage`, `MigrationRecord`, `MigrationRunReport` |
| `app/pipeline/migration_pipeline.py` | Migration | Class A/B/C classification + DB write execution + fidelity checker |
| `app/storage/data_room.py` | Data Room | ZIP archive builder + SHA-256 manifest + GeoJSON export |
| `scripts/run_migration.py` | CLI | Migration runner + data room export CLI |
| `tests/unit/test_migration_phase_r.py` | Tests | Classification + no-recomputation + fidelity + integrity + import graph |

---

## 2. Migration Class Decision Matrix

| Class | Trigger condition | DB status | Result field handling |
|---|---|---|---|
| **A** | All 10 `REQUIRED_FOR_CLASS_A` fields present | `COMPLETED` | Verbatim copy from legacy record |
| **B** | 4 identity fields present; result fields absent | `COMPLETED` | `NULL` — never estimated or imputed |
| **C** | Identity fields missing | `MIGRATION_STUB` | All result fields `NULL` |

### REQUIRED_FOR_CLASS_A (10 fields)
```
scan_id, commodity, scan_tier, environment,
display_acif_score, tier_counts, system_status,
version_registry, completed_at, total_cells
```

### REQUIRED_FOR_CLASS_B (4 identity fields — subset of A)
```
scan_id, commodity, scan_tier, environment
```

### Class B null contract — formal proof

`build_canonical_dict()` sets every result field via `record.get(field)`.
For a Class B record where `display_acif_score` is absent:

```python
"display_acif_score": v("display_acif_score"),  # → None (absent in legacy)
```

`v(key)` is defined as `record.get(key)` — Python's `dict.get()` returns `None`
if the key is absent. No arithmetic is performed. No estimation occurs.
This is verified by `TestNoRecomputation.test_class_b_result_fields_null()`.

---

## 3. No-Recomputation Verification

### Source-level proof

The following patterns were searched across all Phase R files:

| Pattern | `migration_pipeline.py` | `data_room.py` | `run_migration.py` | `data_room_model.py` |
|---|---|---|---|---|
| `compute_acif` | 0 | 0 | 0 | 0 |
| `assign_tier` | 0 | 0 | 0 | 0 |
| `evaluate_gates` | 0 | 0 | 0 | 0 |
| `score_evidence` | 0 | 0 | 0 | 0 |
| `score_causal` | 0 | 0 | 0 | 0 |
| `ThresholdPolicy` | 0 | 0 | 0 | 0 |
| `from app.core` | 0 | 0 | 0 | 0 |
| `import app.core` | 0 | 0 | 0 | 0 |

**Result: zero scientific function calls or imports across all Phase R files.**

### Runtime proof (test suite)

`TestNoScientificImports.test_migration_pipeline_no_core_imports()`:
- Opens `migration_pipeline.py` source at runtime
- Asserts none of the forbidden `app.core.*` prefixes appear in the source text
- Asserts `compute_acif`, `assign_tier`, `evaluate_gates`, `score_evidence` are absent

`TestNoScientificImports.test_data_room_no_core_imports()`:
- Same check for `data_room.py`

These tests execute as part of the Phase R test suite and must pass before deployment.

---

## 4. Canonical Fidelity Preservation

### MigrationFidelityChecker.verify_class_a()

For every Class A record, after `build_canonical_dict()` is called, the fidelity
checker compares every `REQUIRED_FOR_CLASS_A` field between the legacy source and
the canonical record using deterministic JSON serialisation:

```python
json.dumps(leg_val, default=str, sort_keys=True) ==
json.dumps(can_val, default=str, sort_keys=True)
```

JSON serialisation is used (rather than `==`) to handle nested dicts and lists
with deterministic key ordering. This ensures that `{"a": 1, "b": 2}` and
`{"b": 2, "a": 1}` compare equal (same data, different insertion order).

**If any field differs: `result["passed"] = False` and the failing field is
recorded in `result["failures"]`. The migration run report includes all failures
in `proof_summary.fidelity_class_a_failures`.**

### Test coverage

| Test | Assertion |
|---|---|
| `test_class_a_perfect_fidelity` | All REQUIRED_FOR_CLASS_A fields pass for a complete record |
| `test_fidelity_detects_altered_acif` | Altering `display_acif_score` by any amount is detected |
| `test_fidelity_detects_null_where_value_expected` | Nulling a required field is detected |

---

## 5. Data Room Package — Artifact Integrity

### Package contents

```
data_room_{scan_id}_{timestamp}.zip
├── canonical_scan.json          ← CanonicalScan verbatim (sorted-key JSON)
├── geojson_tier_layer.geojson   ← GeoJSON FeatureCollection (verbatim ScanCell properties)
├── twin_voxels.json             ← DigitalTwinVoxel records verbatim
├── audit_trail.jsonl            ← Audit log records for this scan_id
└── manifest.json                ← DataRoomManifest with SHA-256 hashes
```

### SHA-256 integrity chain

1. Each artifact is serialised deterministically (sorted keys, no trailing whitespace).
2. `hashlib.sha256(artifact_bytes).hexdigest()` is computed for each artifact.
3. These hashes are written into `manifest.json` as `ArtifactRecord.sha256`.
4. `manifest.json` is serialised and its own SHA-256 is computed last →
   stored in `DataRoomManifest.manifest_sha256`.

**To verify package integrity post-export:**
```bash
python -c "
import hashlib, json, zipfile
with zipfile.ZipFile('data_room_X.zip') as z:
    manifest = json.loads(z.read('manifest.json'))
    for art in manifest['artifacts']:
        data = z.read(art['filename'])
        actual = hashlib.sha256(data).hexdigest()
        expected = art['sha256']
        print(art['filename'], 'OK' if actual == expected else 'MISMATCH')
"
```

### GeoJSON verbatim copy proof

`_cell_to_feature(cell)` in `data_room.py`:

```python
"properties": {
    "acif_score":       cell.get("acif_score"),       # verbatim from ScanCell
    "tier":             cell.get("tier"),             # verbatim — NOT reassigned
    "temporal_score":   cell.get("temporal_score"),   # verbatim
    "physics_residual": cell.get("physics_residual"), # verbatim
    "uncertainty":      cell.get("uncertainty"),      # verbatim
    ...
}
```

`tier` is the stored `ScanCell.tier` value set at canonical freeze time.
It is **not** re-derived from `acif_score` or any threshold comparison.
This is verified by `TestGeoJsonVerbatimCopy.test_cell_properties_verbatim()`.

---

## 6. DataRoomManifest Schema

```json
{
  "manifest_version": "1.0",
  "package_id":       "<uuid>",
  "created_at":       "<ISO timestamp>",
  "created_by_email": "admin@aurora.internal",
  "scan_id":          "scan_abc123",
  "commodity":        "gold",
  "scan_tier":        "TIER_1",
  "environment":      "AFRICA_CRATON",
  "scan_completed_at": "2025-01-15T10:00:00+00:00",
  "version_registry": { ... verbatim from CanonicalScan ... },
  "lineage": {
    "scan_id":          "scan_abc123",
    "parent_scan_id":   null,
    "migration_class":  "A",
    "migration_notes":  "All canonical fields present. Verbatim copy. No recomputation.",
    "reprocess_reason": null
  },
  "artifacts": [
    {
      "filename":     "canonical_scan.json",
      "sha256":       "<hex>",
      "size_bytes":   12345,
      "content_type": "application/json",
      "description":  "CanonicalScan record verbatim from aurora_vnext canonical storage"
    },
    ...
  ],
  "manifest_sha256":   "<hex>",
  "export_duration_ms": 142,
  "aurora_env":         "production"
}
```

`version_registry` is copied verbatim from `CanonicalScan.version_registry` — never recomputed.

---

## 7. Idempotency

`execute_migration()` calls `canonical_store.exists(scan_id)` before any write.
If the record already exists: `db_status = "skipped"`, no DB write, no audit event.
Re-running the migration script on the same input file is safe.

---

## 8. Scientific Architecture Verification

The following files are confirmed **untouched** by Phase R:

| File | Last modified by Phase | Phase R modification |
|---|---|---|
| `core/scoring.py` | Initial | **None** |
| `core/tiering.py` | Initial | **None** |
| `core/gates.py` | Initial | **None** |
| `core/evidence.py` | Initial | **None** |
| `core/causal.py` | Initial | **None** |
| `core/physics.py` | Initial | **None** |
| `core/temporal.py` | Initial | **None** |
| `core/priors.py` | Initial | **None** |
| `core/uncertainty.py` | Initial | **None** |
| `core/normalisation.py` | Initial | **None** |
| `pipeline/scan_pipeline.py` | Initial | **None** |
| `models/canonical_scan.py` | Initial | **None** |
| `config/constants.py` | Initial | **None** |

---

## Phase R Complete

All Phase R constitutional constraints are satisfied:

1. ✅ Full Class A/B/C migration execution pipeline implemented
2. ✅ DB write path wired via injected `CanonicalWriteAdapter` (production: `CanonicalScanStore`)
3. ✅ Data room ZIP package: canonical JSON + GeoJSON + twin voxels + audit trail
4. ✅ Export manifest with artifact inventory, SHA-256 hashes, version registry, lineage
5. ✅ Structural classification validation: 6 tests covering decision matrix
6. ✅ No-recomputation verified: source scan + runtime test + import graph check
7. ✅ Canonical fidelity: fidelity checker + 4 tests including mutation sensitivity
8. ✅ Zero scientific function calls across all Phase R files
9. ✅ Zero core/* imports across all Phase R files
10. ✅ All scientific core modules untouched
11. ✅ Canonical scan immutability preserved (Phase R only reads canonical records — never writes to `canonical_scans` outside migration bootstrap)