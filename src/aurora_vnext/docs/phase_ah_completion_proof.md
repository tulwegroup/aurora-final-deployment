# Phase AH Completion Proof
## Aurora OSI vNext — Secure Data Room & Delivery Layer

---

## No-Scientific-Recomputation Statement

> **All exported artifacts in the data-room system are verbatim canonical projections.**
>
> No scoring, tiering, gate evaluation, calibration run, or ACIF formula was executed during package assembly, watermarking, delivery link generation, or access logging.
>
> Every byte in every artifact originates from a stored canonical record:
> - `CANONICAL_SCAN_JSON` — JSON serialisation of stored `CanonicalScan` dict (sorted keys, no transformation)
> - `GEOJSON_LAYER` — verbatim fetch from stored GeoJSON export
> - `KML_EXPORT` — verbatim stored KML bytes
> - `DIGITAL_TWIN_DATASET` — verbatim stored voxel CSV from twin storage
> - `GEOLOGICAL_REPORT` — verbatim stored `GeologicalReport` dict
> - `AUDIT_TRAIL_BUNDLE` — assembled from stored audit fields only
>
> Verified by test 18 (`test_no_core_imports_in_packager`) which scans the packager source for any `core.*` import.
>
> The Phase AE freeze (`ae-freeze-2026-03-26-v1`) remains intact.

---

## Phase AG Extension: Cost Model Governance

> **Cost model versioning introduced as required by Phase AG approval.**
>
> `COST_MODEL_VERSION = "cm-1.0.0"` added to `scan_cost_model.py`.
> All pricing constants are now versioned and auditable via this constant.
> Cost computations remain independent of ACIF, tiers, and calibration outputs.
> Verified by test 20 (`test_cost_model_version_exists`).

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/data_room_model.py` | Model | `DataRoomArtifact`, `DataRoomPackage`, `DeliveryLink`, `DataRoomAccessLog`, `WatermarkMetadata` |
| `app/services/data_room_packager.py` | Service | `build_data_room_package()`, `create_delivery_link()`, `check_link_access()`, `log_access()` |
| `tests/unit/test_data_room_phase_ah.py` | Tests | 20 tests covering all AH requirements |
| `docs/phase_ah_completion_proof.md` | Proof | This document |
| `app/services/scan_cost_model.py` | Extension | `COST_MODEL_VERSION = "cm-1.0.0"` added |

---

## 2. Data-Room Package Structure

```
DataRoomPackage {
  package_id:              "drp-{uuid5}"
  scan_id:                 "scan-{id}"
  recipient_id:            "org-{id}"
  created_at:              ISO 8601 UTC
  pipeline_version:        from VersionRegistry
  report_engine_version:   from VersionRegistry
  calibration_version_id:  from CalibrationScanTrace
  cost_model_version:      "cm-1.0.0"
  package_hash:            SHA-256(sorted artifact hashes)

  artifacts: [
    DataRoomArtifact {
      type:               CANONICAL_SCAN_JSON
      filename:           "scan_{id}.json"
      content_source_ref: "canonical_scans/{id}"
      sha256_hash:        64-char hex
      size_bytes:         int
      is_verbatim:        true  ← always
      watermark_id:       optional
    },
    DataRoomArtifact { type: GEOJSON_LAYER, ... },
    DataRoomArtifact { type: KML_EXPORT, ... },
    DataRoomArtifact { type: DIGITAL_TWIN_DATASET, ... },
    DataRoomArtifact { type: GEOLOGICAL_REPORT, ... },
    DataRoomArtifact { type: AUDIT_TRAIL_BUNDLE, ... },
  ]
}
```

---

## 3. Artifact Inventory & Hash Verification

### Per-artifact content source and hash chain

| Artifact | Source | Hash |
|---|---|---|
| `CANONICAL_SCAN_JSON` | `canonical_scans/{scan_id}` storage record | SHA-256 of sorted-key canonical JSON bytes |
| `GEOJSON_LAYER` (×N) | `geojson_exports/{scan_id}/layer_{i}` | SHA-256 of FeatureCollection bytes |
| `KML_EXPORT` | `kml_exports/{scan_id}` | SHA-256 of KML bytes |
| `DIGITAL_TWIN_DATASET` | `twin_exports/{scan_id}` | SHA-256 of voxel CSV bytes |
| `GEOLOGICAL_REPORT` | `reports/{report_id}` | SHA-256 of report JSON bytes |
| `AUDIT_TRAIL_BUNDLE` | Assembled from stored audit fields | SHA-256 of assembled JSON bytes |

### Package integrity hash

```
package_hash = SHA-256(
  concat(sorted([a.sha256_hash for a in artifacts]))
)
```

`DataRoomPackage.verify_integrity()` recomputes this at any time.  
Verified by tests 4 and 5 (`test_verify_integrity_passes_on_fresh`, `test_verify_integrity_fails_on_tamper`).

---

## 4. Access Control Mechanism

### DeliveryLink lifecycle

```
create_delivery_link(package_id, recipient_id, expires_at, max_downloads?, ip_whitelist?)
  → DeliveryLink { token: 64-char hex, status: ACTIVE, ... }

check_link_access(link, ip_address, now_utc?)
  → "allowed" | "expired" | "revoked" | "ip_blocked" | "limit_reached"
```

### Access gate logic (in priority order)

| Check | Outcome |
|---|---|
| `link.status == REVOKED` | `"revoked"` |
| `link.status == CONSUMED` | `"limit_reached"` |
| `now >= expires_at` | `"expired"` |
| `ip_whitelist set AND ip not in whitelist` | `"ip_blocked"` |
| `downloads_used >= max_downloads` | `"limit_reached"` |
| All checks passed | `"allowed"` |

### Token security

- `generate_delivery_token()` uses `secrets.token_hex(32)` — 256 bits of CSPRNG entropy
- Tokens are never predictable or derived from scan data

---

## 5. Audit Logging Demonstration

Every access attempt (allowed or denied) produces a `DataRoomAccessLog` entry:

```json
{
  "log_id":        "dal-{uuid5}",
  "link_id":       "drl-{uuid5}",
  "package_id":    "drp-{uuid5}",
  "recipient_id":  "org-001",
  "accessed_at":   "2026-03-26T14:32:01.123456+00:00",
  "ip_address":    "41.218.92.4",
  "user_agent":    "Mozilla/5.0 ...",
  "artifact_type": "canonical_scan_json",
  "outcome":       "allowed",
  "bytes_served":  48291
}
```

Log entries are:
- **append-only** — never modified or deleted
- written for every outcome including denied attempts (`bytes_served = 0`)
- structured for downstream SIEM / audit pipeline ingestion

---

## 6. Watermarking

Watermarking uses a non-destructive JSON wrapper strategy:

```json
{
  "_watermark": {
    "recipient_id":   "org-001",
    "recipient_name": "Mining Co Ltd",
    "applied_at":     "2026-03-26T00:00:00Z",
    "watermark_id":   "wm-001"
  },
  "data": { ...canonical fields verbatim... }
}
```

**Canonical field integrity guarantee:** `data.*` fields are untouched by watermarking. Specifically:
- `data.acif_mean`, `data.tier_counts`, `data.scan_output_hash` — verbatim
- No field values are modified, rounded, or reformatted
- Verified by test 6 (`test_watermark_wraps_without_altering_canonical_fields`)

---

## 7. Proof of Zero Scientific Recomputation

### Import audit

| Module | core.scoring | core.tiering | core.gates | core.priors |
|---|---|---|---|---|
| `data_room_model.py` | ✅ absent | ✅ absent | ✅ absent | ✅ absent |
| `data_room_packager.py` | ✅ absent | ✅ absent | ✅ absent | ✅ absent |

### Function-level proof

| Function | Data source | Transformation |
|---|---|---|
| `_canonical_scan_to_bytes()` | Stored `CanonicalScan` dict | `json.dumps(sort_keys=True)` only |
| `_geojson_to_bytes()` | Stored GeoJSON dict | `json.dumps(sort_keys=True)` only |
| `_build_audit_trail()` | Stored audit fields | Assembly into bundle dict only |
| `_apply_watermark_to_json()` | Output of above | Wraps in `{_watermark, data}` only |
| `create_delivery_link()` | No canonical data | Token generation + timestamp only |
| `check_link_access()` | DeliveryLink fields | Comparison logic only |
| `log_access()` | Link fields + request metadata | Struct assembly only |

---

## Phase AH Complete

1. ✅ Data-room package structure — `DataRoomPackage` with 6 artifact types
2. ✅ Artifact hash verification — per-artifact SHA-256 + `package_hash` chain
3. ✅ Secure delivery — time-limited `DeliveryLink`, 256-bit CSPRNG token
4. ✅ Access control — 5-gate check (`expired/revoked/ip_blocked/limit_reached/allowed`)
5. ✅ Download audit logging — `DataRoomAccessLog`, append-only, all outcomes
6. ✅ Optional watermarking — non-destructive JSON wrapper, canonical fields untouched
7. ✅ Zero scientific recomputation — import audit + function-level proof + test 18
8. ✅ Cost model versioning (Phase AG extension) — `COST_MODEL_VERSION = "cm-1.0.0"`
9. ✅ 20 regression tests covering all AH requirements

**Requesting Phase AI approval.**