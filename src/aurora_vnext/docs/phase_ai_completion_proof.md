# Phase AI Completion Proof
## Aurora OSI vNext — UX Finalisation (Client Workflow)

---

## No-Scientific-Computation Statement

> **Zero scientific computation occurs in any Phase AI UI component.**
>
> All values displayed in the client workflow are read verbatim from canonical stored outputs delivered by backend API responses. No ACIF formula, tier derivation, gate evaluation, calibration run, or probability transformation is performed in the frontend.
>
> Specifically:
> - `ScanResultsView` displays `scan.acif_mean`, `scan.tier_counts`, `scan.system_status` — all verbatim from stored `CanonicalScan`
> - `ExportStep` displays `pkg.package_hash`, `pkg.artifacts[].sha256_hash` — verbatim from `DataRoomPackage`
> - `ScanParamsStep` displays `cost_est.estimated_cost_usd` — advisory infrastructure cost from `scan_cost_model` (not from ACIF)
> - No component imports or calls `core/scoring`, `core/tiering`, `core/gates`, or `core/priors`

---

## Phase AH Extension: Export Determinism & Delivery Security Hardening

### Export determinism
- `DataRoomPackage.package_hash = SHA-256(sorted artifact hashes)` — deterministic for identical inputs
- `DataRoomPackage.verify_integrity()` recomputes hash at any time for any environment
- Artifact serialisation uses `json.dumps(sort_keys=True)` — byte-identical across Python environments

### Delivery security hardening
| Feature | Implementation |
|---|---|
| Token revocation | `revokeDeliveryLink` function sets `status=REVOKED` — immediate, checked at access time |
| Single-use links | `max_downloads=1` + `status=CONSUMED` after first download |
| Secure default TTLs | 48h standard, 24h sensitive (displayed in ExportStep UI) |
| Token generation | `secrets.token_hex(32)` — 256-bit CSPRNG, never derived from scan data |

---

## 1. UI Component Inventory

| Component | File | Purpose |
|---|---|---|
| `ClientWorkflow` | `pages/ClientWorkflow.jsx` | Root workflow page — 4-step navigator |
| `AOIStep` | `components/workflow/AOIStep.jsx` | Step 1: AOI input (bbox/upload/draw link), validation |
| `ScanParamsStep` | `components/workflow/ScanParamsStep.jsx` | Step 2: commodity, resolution, cost estimate, submit |
| `ScanResultsView` | `components/workflow/ScanResultsView.jsx` | Step 3: live poll, tier counts, links to twin/report/map |
| `ExportStep` | `components/workflow/ExportStep.jsx` | Step 4: data room build, delivery link, revocation |

---

## 2. End-to-End User Flow

```
Step 1 — Define AOI
  ├── Select input mode: Bounding Box | Upload KML/GeoJSON | Draw (→ Map Builder)
  ├── Enter bbox coords or upload file
  ├── Click "Validate AOI"
  │     → POST /validateAoi → {aoi_id, area_km2, geometry_hash, environment_type}
  ├── Preview: AOI ID, area, geometry hash
  └── Click "Continue" → Step 2

Step 2 — Scan Parameters
  ├── Select commodity (gold/copper/nickel/lithium/petroleum)
  ├── Select resolution (low/standard/high)
  │     → POST /estimateScanCost → {estimated_cells, cost_per_km2, cost_tier} [advisory]
  ├── Cost estimate card (infrastructure only — not ACIF-derived)
  └── Click "Submit Scan"
        → POST /submitScan → {scan_id}
        → Step 3

Step 3 — View Outputs
  ├── Auto-poll /getScanStatus every 4s
  ├── On completion: display tier_counts, acif_mean (stored), system_status
  ├── Tabs:
  │   ├── Summary — tier distribution cards
  │   ├── Map Layers → link to /datasets/{scanId} and /map-export/{scanId}
  │   ├── Digital Twin → link to /twin/{scanId}
  │   └── Report → link to /reports/{scanId}
  └── Click "Proceed to Export" → Step 4

Step 4 — Export / Share
  ├── Configure: TTL (24h/48h/7d/30d), single-use toggle, watermark toggle
  ├── Click "Build Data Room Package"
  │     → POST /buildDataRoom → {package: DataRoomPackage, link: DeliveryLink}
  ├── Display: package_id, package_hash, artifact list with truncated hashes
  ├── Display: delivery link status, expiry, max_downloads
  ├── Copy link button
  ├── Revoke button → POST /revokeDeliveryLink → immediate invalidation
  └── "Start New Scan" button → resets workflow to Step 1
```

---

## 3. Proof of No Scientific Computation in Frontend

### Component-level audit

| Component | API calls | Data displayed | Any formula? |
|---|---|---|---|
| `AOIStep` | `validateAoi` | `aoi_id`, `area_km2`, `geometry_hash` | ❌ None |
| `ScanParamsStep` | `estimateScanCost`, `submitScan` | `estimated_cells`, `cost_per_km2`, `cost_tier` | ❌ None — cost model is infrastructure |
| `ScanResultsView` | `getScanStatus` (poll) | `tier_counts`, `acif_mean`, `system_status` | ❌ None — verbatim stored values |
| `ExportStep` | `buildDataRoom`, `revokeDeliveryLink` | `package_hash`, `artifact.sha256_hash`, link status | ❌ None |

### Import audit (all workflow components)

No component imports from:
- `../lib/auroraApi` core scoring modules
- Any formula utility
- Any calibration or prior computation

All data fetched via `base44.functions.invoke()` from backend functions that are themselves constitutional-rule-compliant.

---

## 4. Performance Metrics for User Interactions

| Interaction | Target | Notes |
|---|---|---|
| AOI validation | < 500ms | Geometry-only backend call |
| Cost estimate | < 300ms | Pure arithmetic on infrastructure constants |
| Scan submission | < 200ms | Queue insertion only |
| Status poll interval | 4s | Reduces load while providing responsive feedback |
| Package build | < 3s | 6 verbatim reads + 7 SHA-256 computations |
| Delivery link generation | < 100ms | Token generation + record creation |
| Link copy to clipboard | < 50ms | Browser API |
| Link revocation | < 200ms | Status field update only |

Step navigation uses React state only — zero latency between steps.

---

## 5. Navigation Integration

Route added to `App.jsx`: `/workflow` → `<ClientWorkflow />`

The workflow is also accessible from the Dashboard via a "New Scan" entry point. All existing routes (`/history`, `/datasets`, `/twin`, `/reports`, `/portfolio`) remain unchanged. The workflow links to these pages for deep-dive views rather than duplicating functionality.

---

## Phase AI Complete

1. ✅ 4-step client workflow — AOI → Params → Results → Export
2. ✅ AOIStep — bbox, upload, map-builder link, validation preview
3. ✅ ScanParamsStep — commodity, resolution, advisory cost display
4. ✅ ScanResultsView — live polling, tier counts, verbatim stored ACIF, links to all viewers
5. ✅ ExportStep — data room build, TTL config, single-use, watermark, copy, revoke
6. ✅ Zero scientific computation in frontend — verified by component audit
7. ✅ Export determinism — `package_hash` reproducible across environments
8. ✅ Delivery security hardening — revocation, single-use, CSPRNG tokens, TTL defaults

**Requesting Phase AJ approval.**