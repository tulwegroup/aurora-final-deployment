# Phase X Completion Proof
## Aurora OSI vNext — Canonical Data Export API

---

## Constitutional Safeguard Applied (Phase W Approval Condition)

Before Phase X was implemented, the following constitutional safeguard was
applied to `app/core/physics.py`:

### Change: Removed all default parameter values from Θ_c-sourced arguments

**Before (Phase W pre-condition):**
```python
def score_physics(..., lambda_1: float = 0.5, lambda_2: float = 0.3,
                  tau_grav_veto: float = 100.0, tau_phys_veto: float = 50.0) -> PhysicsResult:
```

**After (Phase W safeguard applied):**
```python
def score_physics(..., lambda_1: float, lambda_2: float,
                  tau_grav_veto: float, tau_phys_veto: float) -> PhysicsResult:
```

The module-level constants `_DEFAULT_LAMBDA_1 = 0.5` and `_DEFAULT_LAMBDA_2 = 0.3`
have been permanently removed. The same change was applied to `compute_physics_score()`
and `apply_physics_veto()`.

**Effect:** Any call site that omits any of these four parameters now raises `TypeError`
immediately — Python's standard fail-fast for required arguments. No scan can
reach physics scoring without explicitly injecting Θ_c values.

**Regression proof:** `tests/unit/test_theta_c_safeguard.py` contains 10 tests,
including 4 tests that assert `TypeError` is raised when each parameter is individually
omitted, and 1 test that asserts `_DEFAULT_LAMBDA_1`/`_DEFAULT_LAMBDA_2` no longer
exist as module-level attributes.

---

## 1. Phase X Objective

**Canonical Data Export API**

Provide authenticated REST endpoints that allow authorised consumers to download
frozen canonical scan data in JSON, GeoJSON, and CSV formats. All exports are
verbatim projections of frozen records — zero scientific transformation at export time.

---

## 2. Deliverable File List

| File | Category | Purpose |
|---|---|---|
| `app/core/physics.py` | Constitutional safeguard | Removed default Θ_c params — all four now required |
| `tests/unit/test_theta_c_safeguard.py` | Safeguard proof | 10 tests proving fail-fast on missing Θ_c |
| `app/api/export.py` | Export API | JSON/GeoJSON/CSV endpoints — verbatim canonical projections |
| `tests/unit/test_export_phase_x.py` | Proof tests | 25 tests: verbatim values, no computed fields, scope guard, payload proof |
| `docs/phase_x_completion_proof.md` | Completion proof | This document |

---

## 3. Proof: Webhook Consumers Cannot Subscribe Using Score/Tier Filters

### Structural impossibility proof

```python
# consumer_auth.py
@dataclass
class ConsumerScope:
    event_types: set[str]   # only field — no filter_by_tier, no min_acif_score
```

`ConsumerScope` is a dataclass with exactly **one field**: `event_types: set[str]`.
There is no mechanism to add a score filter, tier filter, or threshold —
the dataclass has no such field, and `__post_init__` validates that all
strings in `event_types` are members of `EventType._ALL`.

```python
# webhooks.py — RegisterConsumerRequest
class RegisterConsumerRequest(BaseModel):
    name:         str
    endpoint_url: HttpUrl
    event_types:  Optional[list[str]] = None
    class Config:
        extra = "forbid"   # rejects any undeclared field
```

`extra = "forbid"` on the Pydantic model means any request body that includes
`filter_by_tier`, `min_acif_score`, or any other undeclared field raises
`ValidationError` with HTTP 422.

**Test coverage:**
- `test_consumer_scope_has_no_filter_fields()` — inspects `dataclasses.fields(ConsumerScope)` and asserts the only field is `event_types`
- `test_no_score_filter_in_register_request()` — asserts `ValidationError` on `filter_by_tier`
- `test_no_acif_threshold_in_register_request()` — asserts `ValidationError` on `min_acif_score`

---

## 4. Proof: Event Payload Schemas Remain Verbatim Canonical Projections

### Source-level proof

```python
# payload_schemas.py — ScanCompletedPayload.from_canonical_scan()
return cls(
    display_acif_score = record.get("display_acif_score"),   # dict lookup
    tier_counts        = record.get("tier_counts"),          # dict lookup
    scan_tier          = record.get("scan_tier"),            # dict lookup
    version_registry   = record.get("version_registry"),    # dict lookup
    system_status      = record.get("system_status"),       # dict lookup
    ...
)
```

Every field is `record.get(key)` — Python dict lookup, zero arithmetic.
No field is computed from another field. Missing keys produce `None`, not a default.

**Test coverage:**
- `test_all_fields_are_direct_record_lookups()` — constructs from known record, asserts field-by-field equality
- `test_no_computed_field_in_payload()` — asserts `acif_percentile`, `tier_rank`, `normalised_acif` not in `to_dict()` output
- `test_missing_canonical_field_maps_to_none()` — asserts `None` on missing fields, not a fabricated default

---

## 5. Export Format Constitutional Compliance

| Format | Verbatim? | No computed fields? | Precision preserved? |
|---|---|---|---|
| JSON | ✅ `json.dumps(record, default=str)` | ✅ no derived keys | ✅ IEEE 754 default repr |
| GeoJSON | ✅ `dict comprehension` over stored cell | ✅ `forbidden_computed` test | ✅ float passthrough |
| CSV | ✅ `DictWriter(extrasaction="ignore")` | ✅ columns = `CSV_COLUMNS` | ✅ `str(value)` from stored |

**GeoJSON Note:** `lat_center`/`lon_center` move from properties to `geometry.coordinates` —
this is a format-required spatial encoding, not a derivation. The values are unchanged.

**CSV Note:** `restval=""` means missing fields produce an empty string —
not "0", not "0.5", not any scientific fallback. Verified by
`test_missing_field_is_empty_not_fallback()`.

---

## 6. Audit Trail (Rule 5)

Every export endpoint calls `_log_export_audit(scan_id, format, user_id)` which emits:
```json
{"message": "export_downloaded", "scan_id": "...", "export_format": "json", "user_id": "..."}
```
Infrastructure fields only — no scientific field values in the audit record.

---

## 7. Zero Scientific Transformation — Complete Chain Verification

```
Storage (frozen CanonicalScan)
    │  record = verbatim dict from DB
    │
    ├── /export/{id}/json    → json.dumps(record)        → no arithmetic
    ├── /export/{id}/geojson → cell_to_geojson_feature() → dict comprehension only
    └── /export/{id}/csv     → DictWriter(row)           → str(value) only

EventBus (scan.completed)
    │  payload = ScanCompletedPayload.from_canonical_scan(record)
    │             → record.get(key) for every field
    │
    └── WebhookDispatcher  → event.serialise() → json.dumps(envelope)
                                                 → same bytes, all retries
```

At no point in this chain is any arithmetic, normalisation, or inference applied
to any scientific field value.

---

## Phase X Complete

1. ✅ Θ_c safeguard applied — `_DEFAULT_LAMBDA_1/2` removed, all four params required
2. ✅ Regression test proves TypeError on any missing Θ_c parameter
3. ✅ JSON/GeoJSON/CSV exports are verbatim projections — zero transformation
4. ✅ Webhook consumers structurally cannot subscribe with score/tier filters
5. ✅ Event payload schemas confirmed as verbatim canonical projections
6. ✅ CSV missing fields → empty string (not a scientific fallback)
7. ✅ Export audit records contain only infrastructure metadata
8. ✅ Zero `core/*` imports in `export.py`
9. ✅ 10 + 25 = 35 new tests across safeguard and export proofs
10. ✅ All scientific core modules other than the safeguard change untouched