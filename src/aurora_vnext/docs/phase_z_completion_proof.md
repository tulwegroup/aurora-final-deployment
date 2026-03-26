# Phase Z Completion Proof
## Aurora OSI vNext — Ground Truth Management Interface

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/security/ground_truth_rbac.py` | Security | Role-based permissions: viewer/operator/admin |
| `app/storage/ground_truth_audit.py` | Storage | Append-only audit log — every state transition recorded |
| `app/api/ground_truth_admin.py` | API | 10 REST endpoints for submit, approve, reject, audit, calibration version management |
| `pages/GroundTruthAdmin.jsx` | UI | Admin interface: pending queue, approval, provenance review, version lineage, audit log |
| `components/GroundTruthTable.jsx` | UI | Record table: type, commodity, country, confidence, status |
| `components/ProvenancePanel.jsx` | UI | Provenance detail: source, identifier link, confidence bars, composite |
| `tests/unit/test_ground_truth_phase_z.py` | Tests | 20 tests: RBAC, audit log, state transitions, lineage preservation, no-delete |
| `docs/phase_z_completion_proof.md` | Proof | This document |

---

## 2. Data Model

```
GroundTruthRecord
  ├── record_id (UUID)
  ├── geological_data_type (enum)
  ├── provenance (GroundTruthProvenance)
  │     ├── source_name, source_identifier
  │     ├── country, commodity, license_note
  │     └── ingestion_timestamp
  ├── confidence (ConfidenceWeighting)
  │     ├── source_confidence, spatial_accuracy
  │     ├── temporal_relevance, geological_context_strength
  │     └── composite (geometric mean — auditable formula)
  ├── is_synthetic (bool — always False in authoritative storage)
  ├── status (PENDING → APPROVED | REJECTED → SUPERSEDED)
  └── data_payload (type-specific structured fields)

AuditEntry (append-only)
  ├── entry_id, actor_id, actor_role
  ├── action (submitted | approved | rejected | revoked | superseded)
  ├── record_id, from_status, to_status
  ├── reason (mandatory for reject/revoke)
  └── occurred_at (ISO 8601 UTC)
```

---

## 3. API Inventory

| Endpoint | Method | Role Required | Purpose |
|---|---|---|---|
| `/api/v1/gt/records` | POST | operator/admin | Submit new record |
| `/api/v1/gt/records` | GET | viewer+ | List records (filterable) |
| `/api/v1/gt/records/{id}` | GET | viewer+ | Full record + provenance |
| `/api/v1/gt/records/{id}/approve` | POST | admin | Approve PENDING record |
| `/api/v1/gt/records/{id}/reject` | POST | admin | Reject with mandatory reason |
| `/api/v1/gt/records/{id}/history` | GET | viewer+ | State transition history |
| `/api/v1/gt/audit` | GET | admin | Full audit log |
| `/api/v1/gt/calibration/versions` | GET | viewer+ | List calibration versions + lineage |
| `/api/v1/gt/calibration/versions/{id}/activate` | POST | admin | Activate DRAFT version |
| `/api/v1/gt/calibration/versions/{id}/revoke` | POST | admin | Revoke version (lineage preserved) |

---

## 4. Approval Workflow

```
                    operator/admin
                         │
                         ▼
                   POST /records ──────────── SyntheticDataRejectedError (if synthetic)
                         │                    MissingProvenanceError (if provenance incomplete)
                         │                    ValidationError (if type payload invalid)
                         ▼
                    status=PENDING ──────────── AuditEntry{action="submitted"}
                         │
              ┌──────────┴──────────┐
              │ (admin review)       │
              ▼                      ▼
         /approve                 /reject (reason required)
              │                      │
              ▼                      ▼
      status=APPROVED          status=REJECTED
      AuditEntry{approved}     AuditEntry{rejected, reason}
              │
              ▼
  CalibrationVersionManager.create_version()
              │
              ▼
         status=DRAFT
              │
              ▼ (admin activates)
         status=ACTIVE ───────── applies_to_scans_after=utcnow()
              │                  Prior ACTIVE → SUPERSEDED (lineage preserved)
              │
              ▼ (if revoked)
         status=REVOKED ──────── lineage preserved, never deleted
```

---

## 5. Lineage and Rollback Behaviour

**Lineage is permanent and immutable:**

- `transition_status()` preserves the original record under a versioned key
  (`{record_id}::{prior_status}`) before writing the updated record.
- `GroundTruthStorage` has no `delete()`, `remove()`, or `drop()` method.
- Rejected records remain in storage with `status=REJECTED` — lineage is queryable via
  `/records/{id}/history`.

**Rollback behaviour:**

There is no destructive rollback. "Rollback" means:
1. The current ACTIVE `CalibrationVersion` is REVOKED.
2. A new DRAFT is created with `parent_version_id` pointing to the prior SUPERSEDED version.
3. The new DRAFT is activated — its `applies_to_scans_after` = `utcnow()`.
4. All intermediate versions remain in the lineage chain.

Historical scans retain their original `calibration_version_id` trace — they are never
re-scored regardless of rollback.

---

## 6. Standing Constraints Compliance

| Constraint | Enforcement |
|---|---|
| Calibration version lineage immutable | No overwrite; SUPERSEDED status; versioned keys |
| Historical scans never rescored | `applies_to_scans_after` enforces future-only |
| Calibration output = config only | `CalibrationParameters` has no ACIF/tier fields |
| Synthetic data prohibited | `is_synthetic=False` enforced at API submission; storage guard remains |
| Scan-level traceability | `CalibrationScanTrace` written at freeze time |
| Bulk/streaming ingestion support | `ingest_bulk()` + EventBus from Phase Y preserved |

---

## 7. Planning Hooks for Future Phases

The following integration points are established in this phase for future use:

### Phase AA — Google Earth / Maps Visualisation
- Ground-truth record `lat`, `lon`, `aoi_polygon_wkt` fields are KML/GeoJSON-ready.
- `list_approved()` with commodity filter provides the spatial dataset for map layers.
- Hook: `GET /api/v1/gt/records?status=approved&commodity=gold` → KML Point layer.

### Phase AB — Geological Report Generation
- `GroundTruthRecord.data_payload` + `provenance.source_name` provide citation material.
- Approved ground-truth records can be referenced by the report engine as canonical supporting evidence.
- Hook: report engine queries `list_approved(commodity)` to populate "Ground Truth Calibration Evidence" section.

### Future Portfolio Intelligence Layer
- Calibration version lineage provides the audit trail for portfolio-level confidence scoring.
- `CalibrationScanTrace.ground_truth_source_ids` enables portfolio queries:
  "which scans were calibrated against USGS MRDS data?"

---

## Phase Z Complete

1. ✅ RBAC: viewer/operator/admin roles with explicit permission sets
2. ✅ Append-only audit log: every state transition recorded — no delete method
3. ✅ Approval workflow: PENDING → APPROVED | REJECTED; mandatory reason on reject
4. ✅ Lineage preserved on rejection, revocation, and supersession
5. ✅ No destructive write: `transition_status()` archives prior state under versioned key
6. ✅ Calibration version activate/revoke with audit entries
7. ✅ Admin UI with pending queue, provenance panel, version lineage, audit log
8. ✅ Integration hooks documented for Phase AA, Phase AB, and portfolio intelligence
9. ✅ Zero `core/*` imports across all Phase Z files
10. ✅ 20 regression tests