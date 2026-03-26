# Phase P Completion Proof
## Aurora OSI vNext — Render-Only Web UI

---

## 1. Frontend Module Inventory

| File | Purpose |
|---|---|
| `src/lib/auroraApi.js` | Thin HTTP client — zero scientific logic |
| `src/components/Layout.jsx` | Sidebar nav, role-aware menu, /auth/me guard |
| `src/components/MissingValue.jsx` | Explicit null/missing field UI — no fallbacks |
| `src/components/ScanStatusBadge.jsx` | Status/tier/system-status badges from API enum values |
| `src/components/ScoreGrid.jsx` | Component score bars from canonical mean_* fields |
| `src/components/TierDistribution.jsx` | Tier bar + legend from tier_counts + tier_thresholds_used |
| `src/pages/Login.jsx` | Credential entry, token storage |
| `src/pages/Dashboard.jsx` | Active scans from GET /scan/active |
| `src/pages/ScanHistory.jsx` | Completed CanonicalScanSummary list |
| `src/pages/ScanDetail.jsx` | Full CanonicalScan record view |
| `src/pages/DatasetView.jsx` | Dataset summary + ScanCell table |
| `src/pages/TwinView.jsx` | Digital twin voxel query interface |
| `src/pages/AdminPanel.jsx` | Users + audit log (admin role only) |

---

## 2. Page / Component Tree

```
App.jsx
├── /login                  → Login
└── Layout (sidebar + outlet)
    ├── /                   → Dashboard
    │   └── ScanStatusBadge
    ├── /history            → ScanHistory
    │   ├── ScanStatusBadge
    │   ├── SystemStatusBadge
    │   └── MissingValue / ValueOrMissing
    ├── /history/:scanId    → ScanDetail
    │   ├── ScanStatusBadge + SystemStatusBadge
    │   ├── TierDistribution  (tier_counts + tier_thresholds_used from API)
    │   ├── ScoreGrid         (mean_evidence_score … mean_uncertainty from API)
    │   └── MissingValue / ValueOrMissing
    ├── /datasets/:scanId   → DatasetView
    │   ├── TierDistribution
    │   ├── TierBadge         (tier label from API, not computed)
    │   └── MissingValue / ValueOrMissing
    ├── /twin/:scanId       → TwinView
    │   └── MissingValue / ValueOrMissing
    └── /admin              → AdminPanel  (admin role only)
        ├── User list + role selector
        └── Audit log table (read-only)
```

---

## 3. Proof That No Scoring Arithmetic Exists in Frontend Code

Exhaustive search across all frontend files for scoring patterns:

| Pattern | Result |
|---|---|
| `acif_score *`, `acif_score +`, `acif_score -` | **Absent** — no arithmetic on ACIF |
| `evidence_score *`, `causal_score *` | **Absent** |
| `Math.sqrt`, `Math.log`, `Math.pow` on score fields | **Absent** |
| `reduce(`, `map(` producing score aggregates | **Absent** |
| Any custom weighting formula | **Absent** |

The only numeric operation on score fields is display formatting:
```js
// Display formatting ONLY — not arithmetic
const fmtPct = v => `${(v * 100).toFixed(1)}%`
```
This converts a [0,1] float to a display string. It does not combine, weight, or
re-derive any score. The input is always a single verbatim API field.

`ScoreGrid.jsx` renders `value * 100` as a CSS `width` percentage — this is
a visual bar width, not a score computation.

---

## 4. Proof That No Threshold Literals/Fallbacks Exist in Frontend Code

| Pattern searched | Result |
|---|---|
| `t1:`, `t2:`, `t3:` threshold literals | **Absent** |
| `>= 0.8`, `>= 0.6`, `>= 0.4` threshold comparisons | **Absent** |
| `TIER_1: 0.`, `TIER_2: 0.` | **Absent** |
| Any `if (score >= X)` tier assignment | **Absent** |
| Fallback: `score || 0`, `score ?? 0` for display | **Absent** (uses `MissingValue` instead) |

`TierDistribution.jsx` displays thresholds verbatim:
```jsx
// tier_thresholds_used is from the API response — never derived in UI
T1 ≥ {tierThresholds.t1 ?? "—"} · T2 ≥ {tierThresholds.t2 ?? "—"}
```
The `?? "—"` is a display fallback for the label, not a numeric threshold substitution.

`DatasetView.jsx` cell table colours cells using `<TierBadge tier={cell.tier} />` —
where `cell.tier` is the string label from the API (`"TIER_1"`, `"TIER_2"`, etc.).
The UI does not compare `cell.acif_score` against any threshold to assign a tier label.

---

## 5. Canonical Field Mapping Table

| UI Location | UI Element | API Source | Field Path |
|---|---|---|---|
| ScanDetail — ACIF card | "Display (mean)" | GET /history/{id} | `display_acif_score` |
| ScanDetail — ACIF card | "Max" | GET /history/{id} | `max_acif_score` |
| ScanDetail — ACIF card | "Weighted" | GET /history/{id} | `weighted_acif_score` |
| ScanDetail — ScoreGrid | Evidence bar | GET /history/{id} | `mean_evidence_score` |
| ScanDetail — ScoreGrid | Causal bar | GET /history/{id} | `mean_causal_score` |
| ScanDetail — ScoreGrid | Physics bar | GET /history/{id} | `mean_physics_score` |
| ScanDetail — ScoreGrid | Temporal bar | GET /history/{id} | `mean_temporal_score` |
| ScanDetail — ScoreGrid | Province Prior bar | GET /history/{id} | `mean_province_prior` |
| ScanDetail — ScoreGrid | Uncertainty bar | GET /history/{id} | `mean_uncertainty` |
| ScanDetail — TierDistribution | Stacked bar | GET /history/{id} | `tier_counts.tier_1/2/3/below` |
| ScanDetail — TierDistribution | Thresholds text | GET /history/{id} | `tier_thresholds_used.t1/t2/t3` |
| ScanDetail — System status | Badge | GET /history/{id} | `system_status` |
| ScanDetail — Veto counts | Row values | GET /history/{id} | `causal/physics/province/offshore_blocked_cell_count` |
| ScanDetail — Version registry | Key-value table | GET /history/{id} | `version_registry.*` |
| DatasetView — Cell table | ACIF column | GET /history/{id}/cells | `cell.acif_score` |
| DatasetView — Cell table | Tier column | GET /history/{id}/cells | `cell.tier` (string label) |
| DatasetView — Cell table | Evidence column | GET /history/{id}/cells | `cell.evidence_score` |
| TwinView — Voxel table | Probability | POST /twin/{id}/query | `voxel.commodity_probs[commodity]` |
| TwinView — Voxel table | Density | POST /twin/{id}/query | `voxel.expected_density` |
| TwinView — Voxel table | Temporal | POST /twin/{id}/query | `voxel.temporal_score` |
| TwinView — Voxel table | Physics residual | POST /twin/{id}/query | `voxel.physics_residual` |
| TwinView — Voxel table | Uncertainty | POST /twin/{id}/query | `voxel.uncertainty` |
| TwinView — Voxel table | Kernel weight | POST /twin/{id}/query | `voxel.kernel_weight` |
| AdminPanel — Audit log | All columns | GET /admin/audit | verbatim `AuditRecord` fields |

---

## 6. Missing-Data Rendering Proof

`MissingValue` and `ValueOrMissing` components enforce the missing-data contract:

```jsx
// MissingValue — explicit ⊘ No data indicator
export default function MissingValue({ label, inline }) { ... }

// ValueOrMissing — inline: value if present, MissingValue if null/undefined
export function ValueOrMissing({ value, format, label }) {
  if (value === null || value === undefined) {
    return <MissingValue inline label={label} />;  // never returns a number
  }
  return <span>{format ? format(value) : String(value)}</span>;
}
```

Usage examples across the UI:

| Location | Field | Null behaviour |
|---|---|---|
| ScanDetail ACIF card | `display_acif_score` | Renders "⊘ ACIF unavailable" |
| ScanDetail ACIF card | `max_acif_score` | Renders "⊘ Max unavailable" |
| ScanDetail veto table | `causal_veto_cell_count` | Renders "⊘ Count unavailable" |
| ScanHistory list | `display_acif_score` | Renders "⊘ ACIF score not available" |
| DatasetView cell table | `acif_score`, `evidence_score` | Renders "—" inline |
| TwinView voxel table | `temporal_score`, `uncertainty` | Renders "—" inline |

**No fallback substitution exists anywhere in the UI.** A null canonical field
always results in an explicit missing-data indicator, never in a substitute number
or default threshold.

---

## 7. Role-Aware Admin UI Proof

### Guard mechanism

`AdminPanel.jsx` applies two independent role checks:

```jsx
// Check 1 — navigation-level: redirect non-admins before render
useEffect(() => {
  if (user && user.role !== "admin") {
    navigate("/");
  }
}, [user]);

// Check 2 — data-level: admin API calls are only made when role=admin
useEffect(() => {
  if (!user || user.role !== "admin") return;
  Promise.all([admin.listUsers(), admin.auditLog(...)]) ...
}, [user]);
```

`user.role` is sourced from `GET /auth/me` (called in `Layout.jsx`), which returns
the role from the validated JWT payload — not from localStorage or a client-side claim.

### Sidebar navigation

`Layout.jsx` filters nav items by role:
```jsx
const visibleNav = NAV.filter(n => !user || n.roles.includes(user.role));
```
The Admin nav item has `roles: ["admin"]` — operators and viewers never see the link.

### API-level enforcement

Even if a non-admin user navigates to `/admin` directly:
- `GET /admin/users` returns HTTP 403 (server-side `require_admin_user` guard)
- `GET /admin/audit` returns HTTP 403
- The UI receives an error and renders the error state — no data is shown

### Audit log in admin UI

The audit log table is **read-only**:
- No delete button
- No edit control
- No PATCH/DELETE call in `auroraApi.js` for audit records
- A notice banner reads: "Audit log is append-only. Records cannot be edited or deleted."

---

## Phase P Complete — Approval Request for Phase Q

All seven Phase P requirements are satisfied:

1. ✅ Frontend is strictly render-only — `auroraApi.js` issues requests and returns verbatim responses
2. ✅ No scientific logic in UI — no scoring formulas, no probability calculations, no physics
3. ✅ No ACIF arithmetic, threshold derivation, tier recounting, or gate recomputation
4. ✅ No alternate score vocabulary — only canonical field names from `CanonicalScan` schema
5. ✅ UI consumes canonical API fields directly — field mapping table above
6. ✅ Null fields render `MissingValue` — never substituted with fallback numbers
7. ✅ Admin views gated on `user.role === "admin"` from `/auth/me` — server enforces HTTP 403

**Phase Q — 3D Voxel Visualisation** is ready to begin pending approval.

Phase Q scope (proposed):
- Bind the `TwinView` to a three.js 3D voxel renderer
- Voxel colour sourced from `commodity_probs` verbatim (no re-scoring)
- Depth axis from `depth_m` / `depth_range_m` verbatim
- Camera controls, depth slice animation
- All rendering parameters from DepthKernelConfig stored values
- Constitutional rule: renderer reads pre-computed voxel records only