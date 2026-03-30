# Aurora OSI vNext — Scan Lifecycle System

**Version: 1.0**  
**Status: LOCKED**  
**Date: 2026-03-30**

---

## EXECUTIVE SUMMARY

The scan lifecycle system enforces strict separation of **execution jobs** (queued/running/failed) and **completed canonical scans** (frozen, publicly readable). All displayed values originate from real backend sources. No client-side scoring, tier computation, or fake animations.

---

## PART 1: BACKEND LIFECYCLE CONTRACT

### 1.1 Scan Submission
**Endpoint:** `POST /api/v1/scan/polygon` or `POST /api/v1/aoi/{aoiId}/submit-scan`

**Request:**
```json
{
  "commodity": "gold",
  "scan_tier": "SMART",
  "environment": "ONSHORE",
  "aoi_polygon": { "type": "Polygon", "coordinates": [...] }
}
```

**Response:**
```json
{
  "scan_id": "uuid-scan-identifier",
  "status": "queued",
  "created_at": "2026-03-30T12:00:00Z"
}
```

**Action:** Frontend stores `scan_id` and redirects to `/scan/live/{scan_id}`

---

### 1.2 Live Job Status Polling
**Endpoint:** `GET /api/v1/scan/status/{scan_id}`

**Response (Running):**
```json
{
  "status": "running",
  "cell_count": 256,
  "cells_processed": 142,
  "tier_1_count": 45,
  "tier_2_count": 67,
  "tier_3_count": 30,
  "data_missing_count": 0,
  "display_acif_score": 0.625,
  "max_acif_score": 0.891,
  "elapsed_seconds": 320,
  "estimated_seconds_remaining": 180
}
```

**Response (Completed):**
```json
{
  "status": "completed",
  "cell_count": 256,
  "tier_1_count": 45,
  "tier_2_count": 67,
  "tier_3_count": 30,
  "display_acif_score": 0.625,
  "max_acif_score": 0.891,
  "completed_at": "2026-03-30T12:10:00Z"
}
```

**Frontend Behavior:**
- Poll every 2 seconds while `status !== "completed"` and `status !== "failed"`
- Update real-time metrics and cell grid
- On completion → auto-redirect to `/history/{scan_id}` (canonical detail page)

---

### 1.3 Canonical Scan Retrieval
**Endpoint:** `GET /api/v1/history/{scan_id}`

**Response (Canonical):**
```json
{
  "scan_id": "uuid-scan-identifier",
  "status": "completed",
  "commodity": "gold",
  "resolution": "SMART",
  "cell_count": 256,
  "display_acif_score": 0.625,
  "max_acif_score": 0.891,
  "tier_1_count": 45,
  "tier_2_count": 67,
  "tier_3_count": 30,
  "min_lat": -5.3,
  "min_lon": -1.5,
  "max_lat": -5.1,
  "max_lon": -1.2,
  "geological_gates": {
    "clay_alteration_gate": {
      "status": "PASS",
      "confidence": 0.87,
      "pass_rate": 0.92
    },
    "iron_oxide_gate": {
      "status": "PASS",
      "confidence": 0.78,
      "pass_rate": 0.85
    }
  },
  "modality_contributions": {
    "clay_alteration": 0.23,
    "iron_oxide": 0.19,
    "sar_density": 0.15,
    "thermal_flux": 0.12,
    "ndvi_stress": 0.11,
    "structural": 0.10,
    "gravity": 0.05,
    "magnetic": 0.03,
    "sar_coherence": 0.02
  },
  "results_geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [-1.45, -5.25]
        },
        "properties": {
          "cell_id": "cell-0001",
          "acif_score": 0.891,
          "tier": "TIER_1",
          "data_sources": ["S2", "S1", "L8", "DEM"],
          "clay_index": 0.78,
          "iron_index": 0.82,
          "sar_ratio": 0.65,
          "coherence": 0.71,
          "thermal_flux": 0.58,
          "ndvi": -0.12
        }
      }
    ]
  },
  "completed_at": "2026-03-30T12:10:00Z"
}
```

**Critical Rule:** This endpoint is CANONICAL-ONLY. ScanDetail page must never render execution job data.

---

## PART 2: FRONTEND ROUTING & STATE SEPARATION

### 2.1 Execution Job Routes
```
/scan/live/:scanId  →  LiveScanConsole component
                       Polls /api/v1/scan/status/:scanId
                       Shows real-time grid with live metrics
                       Transitions to detail on completion
```

**LiveScanConsole Responsibilities:**
1. Poll backend job status every 2 seconds
2. Display cells in grid with tier coloring:
   - `TIER_1` = emerald-500 (green)
   - `TIER_2` = amber-400 (yellow)
   - `TIER_3` = red-500 (red)
   - `DATA_MISSING` = slate-300 (gray)
3. Update metrics in real time:
   - Cells processed / total
   - Mean ACIF
   - Max ACIF
   - Tier counts
4. Show live event feed from backend events
5. Display top 5 cells by ACIF
6. On completion → auto-redirect to `/history/{scan_id}`

### 2.2 Canonical Scan Routes
```
/history/:scanId  →  ScanDetail component
                      Fetches /api/v1/history/:scanId
                      MUST be completed canonical scan
                      Rejects execution job data
```

**ScanDetail Responsibilities:**
1. Load ONLY canonical scan from `/api/v1/history/{scan_id}`
2. Render all required sections (see Part 3)
3. Never show partial/running job data
4. Provide action buttons: Generate Report, Map Export, Data Room

---

## PART 3: COMPLETED SCAN DETAIL SECTIONS

### Section 1: Scan Overview
- Commodity
- Timestamp
- Grid resolution
- Total cells
- Mean ACIF (display_acif_score × 100)
- Max ACIF
- Tier counts (with distribution bar)

### Section 2: Geographic Bounds / System Status
- Min/max lat/lon
- AOI bounds confirmation
- System status badge

### Section 3: Geological Gates
For each gate in `canonical.geological_gates`:
- Gate name (e.g., "clay_alteration_gate")
- Pass/Fail badge
- Confidence or pass rate percentage

### Section 4: ACIF Modality Averages
Display each modality from `canonical.modality_contributions`:
- Clay Alteration
- Iron Oxide / Ferric
- SAR Density / Backscatter
- Thermal Flux
- NDVI Stress
- Structural
- Gravity
- Magnetic
- SAR Coherence

### Section 5: Top Cells by ACIF
Ranked table from `results_geojson.features`:
- Rank #
- Tier color badge
- ACIF score (as %)
- Coordinates
- Dominant modality (optional)

### Section 6: Resource Estimate
If `canonical.resource_estimate` is present:
- Tonnage estimate
- Grade estimate
- Confidence level
- Include disclaimer: "Estimates are proxy only and not geological recommendations"

### Section 7: GIS / Raster Spec
Display from `/api/v1/datasets/summary/{scan_id}`:
- CRS (default: EPSG:4326)
- Pixel size (m)
- Available bands
- Export formats (links to JSON, GeoJSON, CSV)

### Section 8: Digital Twin
Display from `/api/v1/twin/{scan_id}`:
- Voxel dimensions
- Total voxels
- Max depth (m)
- Download link (if available)

### Section 9: Spatial ACIF Heatmap
Render cell grid colored by tier/score band

### Section 10: Cell Map / Grade Distribution
Map visualization from `results_geojson` with:
- Cell positions (GPS)
- Tier coloring
- Hover tooltips with ACIF, cell_id, coordinates

---

## PART 4: LIVE SCAN VISUALIZATION

### 4.1 Cell Grid Rendering
**Data Source:** Real backend cells from live polling and canonical freeze

**Cell State Machine:**
```
UNSCANNED → PROCESSING → SCORED → FINAL_TIER
   (gray)      (faint)    (color)   (bright)
```

**Tier Color Mapping:**
```
TIER_1:       background: bg-emerald-500, text: white, icon: ✓
TIER_2:       background: bg-amber-400,   text: dark,  icon: ◐
TIER_3:       background: bg-red-500,     text: white, icon: ✗
DATA_MISSING: background: bg-slate-300,   text: dark,  icon: ⊘
```

### 4.2 Real-Time Metrics Panel
Updates every 2 seconds from backend status:
- **Cells Processed:** `{cells_processed} / {cell_count}`
- **Progress:** `{(cells_processed/cell_count)*100}%`
- **Mean ACIF:** `{display_acif_score * 100}%`
- **Max ACIF:** `{max_acif_score * 100}%`
- **Tier Breakdown:**
  - Tier 1: `{tier_1_count}` (green)
  - Tier 2: `{tier_2_count}` (amber)
  - Tier 3: `{tier_3_count}` (red)
  - Missing: `{data_missing_count}` (gray)
- **System Status:** `{status}` badge

### 4.3 Live Event Feed
Show backend events (if available from job progress API):
- `cell_started`
- `observables_computed`
- `modality_bundle_assembled`
- `cell_scored`
- `cell_finalized`
- `scan_freeze_complete`

### 4.4 Top Targets Panel
Real-time ranked list:
1. Cell ID
2. ACIF score (as %)
3. Tier
4. Coordinates
5. Dominant modality

---

## PART 5: ENFORCEMENT & VALIDATION

### 5.1 Strict Separation Rules

**Execution Job:**
- Must have `status` in ["queued", "running", "failed"]
- Shown ONLY on `/scan/live/:scanId`
- Never rendered by ScanDetail

**Canonical Scan:**
- Must have `status = "completed"`
- Sourced from `/api/v1/history/{scan_id}`
- Shown ONLY on `/history/:scanId`
- Complete geological gates and modality data

**Transition Rule:**
```
Execution Job (running) 
  → Backend status → "completed"
  → ScanDetail loads canonical /api/v1/history/{scan_id}
  → Completed scan appears in Scan History
```

### 5.2 Data Integrity Proof

For each displayed value, verify:
1. **Source:** Backend endpoint (not hardcoded)
2. **Scope:** Canonical scan only (no job inference)
3. **Transform:** Display × 100 for percentages (no recomputation)
4. **Fallback:** "—" if unavailable (no defaults)

---

## PART 6: COMPLETED LIFECYCLE EXAMPLE

```
1. User submits scan
   POST /api/v1/scan/polygon
   Response: { scan_id: "abc123", status: "queued" }

2. Redirect to live view
   /scan/live/abc123

3. LiveScanConsole starts polling
   GET /api/v1/scan/status/abc123
   Response: { status: "running", cells_processed: 0, ... }

4. User watches cells process
   Every 2s: poll status, update grid, update metrics
   Tier 1 cell → green
   Tier 2 cell → amber
   Tier 3 cell → red

5. Backend completes scan
   GET /api/v1/scan/status/abc123
   Response: { status: "completed", ... }

6. LiveScanConsole detects completion
   Auto-redirects to /history/abc123

7. ScanDetail loads canonical scan
   GET /api/v1/history/abc123
   Response: { status: "completed", geological_gates: {...}, ... }

8. ScanDetail renders all sections
   - Geological Gates (real backend data)
   - ACIF Modality Averages (real backend data)
   - Top Cells by ACIF (from results_geojson)
   - Digital Twin (from /api/v1/twin/abc123)
   - GIS/Raster Spec (from /api/v1/datasets/summary/abc123)
   - All values backend-sourced, no fabrication

9. Completed scan appears in Scan History
   ScanHistory queries /api/v1/history with filtering
   Shows "abc123" in canonical scans list
   Clicking opens ScanDetail (step 7)
```

---

## PART 7: PHYSICS DISCIPLINE

### Non-Negotiable Constraints

1. **No client-side ACIF recomputation**
   - Display values sourced from `display_acif_score` and `max_acif_score`
   - Never infer or approximate

2. **No fabricated gates**
   - Geological gates shown ONLY if present in canonical payload
   - Never guess gate status from tier counts

3. **No hardcoded modality values**
   - Modality contributions from `modality_contributions` object
   - Never synthesize missing modalities

4. **No tier invention**
   - Cell tier = `tier` field from `results_geojson.features[*].properties`
   - Never infer tier from ACIF threshold

5. **No UI-only metrics**
   - Every displayed number sourced from backend response
   - No derived calculations except display transforms (e.g., × 100)

---

## PART 8: DEPLOYMENT CHECKLIST

- [ ] LiveScanConsole polls `/api/v1/scan/status/{scanId}`
- [ ] ScanDetail loads ONLY from `/api/v1/history/{scanId}`
- [ ] ScanDetail rejects execution jobs
- [ ] Geological Gates section renders if present
- [ ] ACIF Modality Averages section renders with all 9 modalities
- [ ] Top Cells section sourced from `results_geojson`
- [ ] Digital Twin section renders if available
- [ ] GIS/Raster Spec renders if available
- [ ] Tier colors consistent: TIER_1=green, TIER_2=amber, TIER_3=red
- [ ] One successful scan lifecycle: submit → live → completion → history → detail
- [ ] All values backend-sourced, no hardcoding
- [ ] No 404s on canonical endpoints

---

## PART 9: KNOWN LIMITATIONS

1. **Phase Z Ground Truth:** Not yet implemented in backend
   - GroundTruthAdmin shows placeholder message
   - Will unlock when `/api/v1/gt/records` is mounted

2. **Live Event Feed:** Requires backend event stream
   - Currently using cell-level status polling
   - Real-time events (cell_started, scored, etc.) future enhancement

3. **Resource Estimate:** Conditional
   - Shown only if `canonical.resource_estimate` present
   - Include disclaimer if shown

4. **Datasets Summary:** Requires Phase AA completion
   - `/api/v1/datasets/summary/{scanId}` may return 404
   - Gracefully skip section if unavailable

---

## PART 10: VERSIONING & UPDATES

This document locks the scan lifecycle system as of **2026-03-30**.

Any changes to:
- Tier color scheme
- Section ordering
- Backend endpoint contracts
- Separation rules

Must be approved and re-versioned.

---

**Locked by:** Aurora System Design  
**Next Review:** 2026-04-30