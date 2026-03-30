# Aurora OSI vNext — Backend Data Contracts

**Version:** 1.0  
**Date:** 2026-03-30  
**Status:** LOCKED

---

## CONTRACT 1: Scan Submission

### Endpoint
```
POST /api/v1/scan/polygon
POST /api/v1/aoi/{aoi_id}/submit-scan
```

### Request (Polygon)
```json
{
  "commodity": "gold",
  "scan_tier": "BOOTSTRAP|SMART|PREMIUM",
  "environment": "ONSHORE|OFFSHORE",
  "aoi_polygon": {
    "type": "Polygon",
    "coordinates": [[[lon, lat], [lon, lat], ...]]
  }
}
```

### Request (AOI)
```json
{
  "commodity": "gold",
  "resolution": "BOOTSTRAP|SMART|PREMIUM"
}
```

### Response
```json
{
  "scan_id": "string (UUID or scan identifier)",
  "status": "queued",
  "created_at": "2026-03-30T12:00:00Z"
}
```

### Frontend Usage
```javascript
const res = await scansApi.submitPolygon({...});
const scanId = res.scan_id;
navigate(`/scan/live/${scanId}`);
```

---

## CONTRACT 2: Job Status Polling

### Endpoint
```
GET /api/v1/scan/status/{scan_id}
```

### Response (Queued/Running)
```json
{
  "scan_id": "string",
  "status": "queued|running|completed|failed",
  "cell_count": 256,
  "cells_processed": 142,
  
  "tier_1_count": 45,
  "tier_2_count": 67,
  "tier_3_count": 30,
  "data_missing_count": 0,
  
  "display_acif_score": 0.625,
  "max_acif_score": 0.891,
  
  "elapsed_seconds": 320,
  "estimated_seconds_remaining": 180,
  
  "created_at": "2026-03-30T12:00:00Z",
  "started_at": "2026-03-30T12:00:15Z"
}
```

### Response (Completed)
```json
{
  "scan_id": "string",
  "status": "completed",
  "cell_count": 256,
  "cells_processed": 256,
  
  "tier_1_count": 89,
  "tier_2_count": 134,
  "tier_3_count": 33,
  "data_missing_count": 0,
  
  "display_acif_score": 0.645,
  "max_acif_score": 0.891,
  
  "created_at": "2026-03-30T12:00:00Z",
  "started_at": "2026-03-30T12:00:15Z",
  "completed_at": "2026-03-30T12:10:00Z"
}
```

### Response (Failed)
```json
{
  "scan_id": "string",
  "status": "failed",
  "cell_count": 256,
  "cells_processed": 142,
  "error_message": "Insufficient satellite imagery for AOI",
  "created_at": "2026-03-30T12:00:00Z",
  "failed_at": "2026-03-30T12:05:00Z"
}
```

### Frontend Usage
```javascript
const status = await scansApi.status(scanId);

if (status.status === 'completed') {
  // Transition to canonical detail
  navigate(`/history/${scanId}`);
} else if (status.status === 'failed') {
  setError(status.error_message);
} else {
  // Update live metrics
  setMetrics({
    cells_processed: status.cells_processed,
    cells_total: status.cell_count,
    mean_acif: status.display_acif_score,
    max_acif: status.max_acif_score,
    tier_1: status.tier_1_count,
    tier_2: status.tier_2_count,
    tier_3: status.tier_3_count
  });
}
```

---

## CONTRACT 3: Canonical Scan Detail

### Endpoint
```
GET /api/v1/history/{scan_id}
```

### Response (Completed Canonical)
```json
{
  "scan_id": "string",
  "status": "completed",
  
  "commodity": "gold|copper|lithium|...",
  "resolution": "BOOTSTRAP|SMART|PREMIUM",
  "environment": "ONSHORE|OFFSHORE",
  
  "cell_count": 256,
  "tier_1_count": 89,
  "tier_2_count": 134,
  "tier_3_count": 33,
  "data_missing_count": 0,
  
  "display_acif_score": 0.645,
  "max_acif_score": 0.891,
  
  "min_lat": -5.3,
  "min_lon": -1.5,
  "max_lat": -5.1,
  "max_lon": -1.2,
  
  "pipeline_version": "vnext-1.0",
  
  "geological_gates": {
    "clay_alteration_gate": {
      "status": "PASS|WEAK|FAIL",
      "confidence": 0.87,
      "pass_rate": 0.92,
      "description": "Kaolin/illite clay absorption minimum"
    },
    "iron_oxide_gate": {
      "status": "PASS|WEAK|FAIL",
      "confidence": 0.78,
      "pass_rate": 0.85,
      "description": "Ferric iron absorption feature"
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
          "tier": "TIER_1|TIER_2|TIER_3|DATA_MISSING",
          "data_sources": ["S2", "S1", "L8", "DEM"],
          
          "clay_index": 0.78,
          "iron_index": 0.82,
          "sar_ratio": 0.65,
          "coherence": 0.71,
          "thermal_flux": 0.58,
          "ndvi": -0.12,
          
          "s2_b4": 0.123,
          "s2_b8": 0.456,
          "s2_b11": 0.789,
          "s2_b12": 0.234,
          "s2_cloud_pct": 5.0,
          "s2_valid": true,
          
          "s1_vv": -10.5,
          "s1_vh": -15.3,
          "s1_valid": true,
          
          "l8_b10": 305.2,
          "l8_valid": true,
          
          "dem_elevation": 1245,
          "dem_slope": 12.5,
          "dem_valid": true
        }
      }
      // ... 255 more cells
    ]
  },
  
  "created_at": "2026-03-30T12:00:00Z",
  "started_at": "2026-03-30T12:00:15Z",
  "completed_at": "2026-03-30T12:10:00Z"
}
```

### Frontend Usage
```javascript
const canonical = await historyApi.get(scanId);

// ScanDetail renders:
// - title: commodity + ' Scan'
// - KPIs: cell_count, display_acif_score, tier counts
// - Geological Gates: from geological_gates object
// - Modality Averages: from modality_contributions object
// - Top Cells: from results_geojson.features
// - Map: from results_geojson geometry
```

---

## CONTRACT 4: Canonical Cell Details (Optional)

### Endpoint
```
GET /api/v1/history/{scan_id}/cells
GET /api/v1/history/{scan_id}/cells/{cell_id}
```

### Response
```json
{
  "features": [
    {
      "type": "Feature",
      "id": "cell-0001",
      "geometry": {
        "type": "Point",
        "coordinates": [-1.45, -5.25]
      },
      "properties": {
        "cell_id": "cell-0001",
        "acif_score": 0.891,
        "tier": "TIER_1",
        "data_sources": ["S2", "S1", "L8", "DEM"]
      }
    }
  ]
}
```

---

## CONTRACT 5: Digital Twin Metadata (Optional, Phase N)

### Endpoint
```
GET /api/v1/twin/{scan_id}
```

### Response
```json
{
  "scan_id": "string",
  "voxel_size_m": 100,
  "voxel_count": 45000,
  "max_depth_m": 2500,
  "grid_x": 50,
  "grid_y": 40,
  "grid_z": 22.5,
  
  "download_url": "https://api.aurora-osi.com/api/v1/twin/{scan_id}/download",
  "metadata": {
    "created_at": "2026-03-30T12:10:00Z",
    "model_version": "vnext-1.0"
  }
}
```

### Frontend Usage
```javascript
const twin = await base44.functions.invoke("auroraProxy", {
  method: "GET",
  path: `/api/v1/twin/${scanId}`
});

// ScanDetail renders:
// - Voxel dimensions
// - Total voxels
// - Max depth
// - Download link
```

---

## CONTRACT 6: Datasets / Raster Spec (Optional, Phase AA)

### Endpoint
```
GET /api/v1/datasets/summary/{scan_id}
GET /api/v1/datasets/raster-spec/{scan_id}
```

### Response
```json
{
  "scan_id": "string",
  "crs": "EPSG:4326",
  "pixel_size_m": 30,
  
  "bands": [
    "S2_B2",    // Blue
    "S2_B3",    // Green
    "S2_B4",    // Red
    "S2_B8",    // NIR
    "S2_B11",   // SWIR1
    "S2_B12"    // SWIR2
  ],
  
  "export_formats": ["json", "geojson", "csv"],
  
  "metadata": {
    "created_at": "2026-03-30T12:10:00Z",
    "total_size_mb": 245.3
  }
}
```

### Frontend Usage
```javascript
const datasets = await base44.functions.invoke("auroraProxy", {
  method: "GET",
  path: `/api/v1/datasets/summary/${scanId}`
});

// ScanDetail renders:
// - CRS
// - Pixel size
// - Available bands
// - Export format links
```

---

## CONTRACT 7: Scan History List

### Endpoint
```
GET /api/v1/history
GET /api/v1/history?commodity=gold&limit=50
```

### Response
```json
{
  "scans": [
    {
      "scan_id": "scan-20260330-gold-001",
      "commodity": "gold",
      "resolution": "SMART",
      "cell_count": 256,
      "tier_1_count": 89,
      "tier_2_count": 134,
      "tier_3_count": 33,
      "display_acif_score": 0.645,
      "status": "completed",
      "completed_at": "2026-03-30T12:10:00Z",
      "created_at": "2026-03-30T12:00:00Z"
    }
  ],
  "total": 145,
  "page": 1,
  "limit": 50
}
```

### Frontend Usage
```javascript
const history = await historyApi.list();
// ScanHistory displays in "Canonical Scans" section
// Clicking a scan navigates to /history/{scan_id}
```

---

## ERROR HANDLING

### 404 (Scan Not Found)
```json
{
  "status": 404,
  "detail": "Scan not found"
}
```

### 404 (Incomplete Scan)
If accessing `/history/{scan_id}` for a queued/running job:
```json
{
  "status": 404,
  "detail": "Scan not completed"
}
```

### Frontend Response
```javascript
try {
  const canonical = await historyApi.get(scanId);
} catch (e) {
  if (e.status === 404) {
    setError("Scan not found or not yet completed");
  }
}
```

---

## SUMMARY TABLE

| Operation | Endpoint | Use Case | Frontend Component |
|-----------|----------|----------|-------------------|
| Submit | POST /api/v1/scan/polygon | New scan | MapScanBuilder |
| Poll Status | GET /api/v1/scan/status/{id} | Live monitoring | LiveScanConsole |
| Load Canonical | GET /api/v1/history/{id} | Detail view | ScanDetail |
| List History | GET /api/v1/history | History list | ScanHistory |
| Load Cells | GET /api/v1/history/{id}/cells | Cell details | ScanDetail |
| Twin Data | GET /api/v1/twin/{id} | 3D model | ScanDetail |
| Datasets | GET /api/v1/datasets/summary/{id} | GIS spec | ScanDetail |

---

## COMPLIANCE MATRIX

| Value | Source | Field | Transform | Display |
|-------|--------|-------|-----------|---------|
| Cells Processed | Status | `cells_processed` | None | As-is |
| Cell Count | Status | `cell_count` | None | As-is |
| Mean ACIF | Status | `display_acif_score` | × 100 | "64.5%" |
| Max ACIF | Status | `max_acif_score` | × 100 | "89.1%" |
| Tier Counts | Status | `tier_*_count` | None | As-is |
| Geological Gates | Canonical | `geological_gates[*]` | None | Pass/Weak |
| Gate Confidence | Canonical | `confidence` | × 100 | "87%" |
| Modalities | Canonical | `modality_contributions[*]` | × 100 | "23%" |
| Cell Tier | Canonical | `tier` | None | Color badge |
| Cell ACIF | Canonical | `acif_score` | × 100 | "89.1%" |
| Cell Coords | Canonical | `coordinates` | None | [lat, lon] |

---

**Status: LOCKED FOR PRODUCTION**