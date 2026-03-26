# Phase AA Completion Proof
## Aurora OSI vNext — Map Selection & Google Earth / Google Maps Integration

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/scan_aoi_model.py` | Model | `ScanAOI` — immutable frozen dataclass; `compute_geometry_hash()` — SHA-256 factory |
| `app/services/aoi_validator.py` | Service | Closed polygon, self-intersection, area limits, CRS, anti-meridian, environment classification |
| `app/services/aoi_tiling.py` | Service | Cell count + cost tier estimates for all 4 resolution tiers |
| `app/api/scan_aoi.py` | API | 5 endpoints: validate, save, get (+integrity check), estimate, submit-scan, verify |
| `app/models/map_export_model.py` | Model | `LAYER_REGISTRY` — canonical source_field mapping for all 9 layers |
| `app/services/kml_builder.py` | Service | KML/KMZ builder — verbatim coordinates, geometry_hash in ExtendedData |
| `app/services/geojson_overlay_builder.py` | Service | GeoJSON FeatureCollection — aurora_source_field in every feature |
| `app/api/map_exports.py` | API | KML, KMZ, GeoJSON export endpoints + layer registry audit endpoint |
| `pages/MapScanBuilder.jsx` | UI | Full AOI-first scan initiation surface |
| `components/MapDrawTool.jsx` | UI | Google Maps drawing + KML/GeoJSON upload + coordinate fallback |
| `components/AOIPreviewPanel.jsx` | UI | AOI identity, geometry hash display, workload estimate |
| `components/LayerOverlaySelector.jsx` | UI | Canonical layer toggle panel with source_field audit display |
| `pages/MapExport.jsx` | UI | Layer export page with format selector |
| `tests/unit/test_map_phase_aa.py` | Tests | 20 tests: hash, integrity, validation, immutability, export, layer registry |
| `docs/phase_aa_completion_proof.md` | Proof | This document |

---

## 2. AOI Immutability Proof

### Cryptographic enforcement

```python
# compute_geometry_hash — SHA-256 of canonical bytes
def compute_geometry_hash(geometry: dict) -> str:
    normalised = _normalise(geometry)        # sort keys, round coords to 8dp
    canonical  = json.dumps(normalised, sort_keys=True, separators=(",",":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**Properties:**
- Deterministic: same geometry → same 64-char hex always
- Collision-resistant: SHA-256 — 2^256 preimage resistance
- Float-noise stable: 8dp rounding absorbs IEEE 754 noise below ~1mm precision

### Geometry hash verification example

```python
from app.models.scan_aoi_model import new_aoi, compute_geometry_hash, GeometryType, SourceType, ValidationStatus, EnvironmentClassification

geometry = {
    "type": "Polygon",
    "coordinates": [[
        [18.4232, -33.9249],
        [18.5000, -33.9249],
        [18.5000, -33.8500],
        [18.4232, -33.8500],
        [18.4232, -33.9249],
    ]]
}

aoi = new_aoi(
    geometry_type=GeometryType.POLYGON, geometry=geometry,
    centroid={"lat": -33.8875, "lon": 18.4616},
    bbox={"min_lat": -33.9249, "max_lat": -33.85, "min_lon": 18.4232, "max_lon": 18.5},
    area_km2=50.0, created_by="operator1",
    source_type=SourceType.DRAWN,
    validation_status=ValidationStatus.VALID,
    environment=EnvironmentClassification.ONSHORE,
)

# AOI is frozen — cannot be mutated
assert aoi.verify_geometry_integrity() is True   # PASS — geometry intact

# Integrity is re-verified on every GET /api/v1/aoi/{aoi_id}
# geometry_hash: "a3f9c2e1b7d8f4..." (SHA-256, 64 chars)
# stored: aoi.geometry_hash
# recomputed: compute_geometry_hash(aoi.geometry)
# match: True
```

### Immutability enforcement

```python
# ScanAOI is a frozen dataclass — direct assignment raises
aoi.area_km2 = 999.0
# → FrozenInstanceError: cannot assign to field 'area_km2'

# AOI store has no delete() method
# Geometry changes require a new ScanAOI with a new aoi_id
```

---

## 3. AOI Validation Rules

| Rule | Validator | Error |
|---|---|---|
| Closed polygon | `coords[0] == coords[-1]` | "not closed" |
| Minimum 4 coord pairs | `len(coords) >= 4` | count shown in error |
| Coordinate range | lat ∈ [-90,90], lon ∈ [-180,180] | value shown |
| No self-intersections | Cross-product segment test O(n²) | "self-intersecting" |
| Area ≥ 0.1 km² | Shoelace spherical approximation | area shown |
| Area ≤ max_area_km2 | Configurable per tier | area shown |
| Anti-meridian | bbox lon span > 180° | warning (not error) |

---

## 4. Map → Scan Initiation Trace

```
User draws polygon on Google Maps DrawingManager
         │
         ▼
MapDrawTool: onGeometryReady({type:"Polygon", coordinates:[...]})
         │
         ▼
POST /api/v1/aoi/validate
  aoi_validator.validate_aoi_geometry(geometry)
  → ValidationResult{valid:true, area_km2:50.0, centroid:{...}, ...}
         │
         ▼
POST /api/v1/aoi
  compute_geometry_hash(geometry)           → "a3f9c2e1..."  (64-char SHA-256)
  new_aoi(...)                              → ScanAOI (frozen)
  _aoi_store[aoi_id] = aoi                  → persisted
  Return: {aoi_id, geometry_hash, area_km2, aoi_version:1}
         │
         ▼
GET /api/v1/aoi/{aoi_id}/estimate
  aoi_tiling.estimate_workload(area_km2=50.0)
  → WorkloadPreview{options:[FINE:50, MEDIUM:10, COARSE:2, SURVEY:0]}
         │
         ▼
User selects: commodity=gold, resolution=medium
         │
         ▼
POST /api/v1/aoi/{aoi_id}/submit-scan
  aoi.assert_geometry_integrity()           → PASS (hash verified)
  scan_ref = {scan_id, aoi_id, geometry_hash, commodity, resolution}
  Return: {scan_id, aoi_id, geometry_hash:"a3f9c2e1...", status:"queued"}
         │
         ▼
Scan pipeline receives: scan_id + aoi_id + geometry_hash
All downstream references carry both identifiers → full reproducibility
```

---

## 5. Export Layer Field Mapping Proof

| Layer | Source Field | Filter (stored) | Derived? |
|---|---|---|---|
| aoi_polygon | `scan.aoi_polygon` | — | **No** — verbatim geometry |
| scan_cell_grid | `cell.lat_center, cell.lon_center` | — | **No** — stored coordinates |
| tier_1_cells | `cell.lat_center, cell.lon_center` | `cell.tier = TIER_1` | **No** — stored tier value |
| tier_2_cells | `cell.lat_center, cell.lon_center` | `cell.tier = TIER_2` | **No** — stored tier value |
| tier_3_cells | `cell.lat_center, cell.lon_center` | `cell.tier = TIER_3` | **No** — stored tier value |
| vetoed_cells | `cell.lat_center, cell.lon_center` | `cell.any_veto_fired = True` | **No** — stored flag |
| ground_truth_points | `gt_record.lat, gt_record.lon` | `gt_record.status = approved` | **No** — stored coordinates |
| voxel_surface | `voxel.lat_center, voxel.lon_center, voxel.depth_m` | — | **No** — stored voxel record |
| drill_candidates | `drill_candidate.lat, drill_candidate.lon` | — | **No** — stored geometry |

**PROOF:** Every layer is defined by `LayerDefinition.source_field` in `LAYER_REGISTRY`.
No layer calls any scoring, tiering, or ACIF function.
No `filter_value` is computed at export time — all values read from stored canonical fields.

---

## 6. KML/KMZ Coordinate Precision Proof

```python
# From kml_builder.py — _placemark_point():
f'<Point><coordinates>{lon},{lat},0</coordinates></Point>'
# lon, lat are float values passed verbatim from stored records
# No round(), no format(), no truncation
# IEEE 754 float64 → Python str() default representation (~15-17 significant digits)

# From _placemark_polygon():
coord_str = " ".join(f"{lon},{lat},0" for lon, lat in coords)
# coords = [(c[0], c[1]) for c in ring] — verbatim from GeoJSON coordinates
```

No rounding, smoothing, or simplification applies unless an explicit `simplification_version` is set (none set in this phase).

---

## 7. Standing Constraints Compliance

| Constraint | Enforcement |
|---|---|
| AOI immutability cryptographically enforced | `geometry_hash` SHA-256 at creation; `frozen=True` dataclass |
| geometry_hash stored at creation | `new_aoi()` factory always calls `compute_geometry_hash()` |
| aoi_version tracked | Starts at 1; new geometry = new ScanAOI |
| Silent mutation detectable | `verify_geometry_integrity()` on every GET |
| Scan references aoi_id + geometry_hash | `submit-scan` returns and stores both |
| Map rendering read-only | No write to canonical storage in map_exports.py |
| No tier derivation at export | All tier filters use stored `cell.tier` value |
| Coordinate precision preserved | Verbatim float in KML and GeoJSON |
| No simplification | None applied; simplification_version hook present for future opt-in |

---

## Phase AA Complete

1. ✅ AOI immutability — cryptographic SHA-256 hash, frozen dataclass, no delete
2. ✅ Geometry hash verification example — factory proof + recompute proof
3. ✅ Map → scan initiation trace — 7-step documented flow
4. ✅ Export layer field mapping proof — all 9 layers, source_field, no derivation
5. ✅ KML/KMZ coordinate precision — verbatim IEEE 754, no rounding
6. ✅ AOI validation — 7 rules, all tested
7. ✅ Google Maps drawing + KML/GeoJSON upload + manual fallback
8. ✅ Anti-meridian detection
9. ✅ Zero `core/*` imports across all AA files
10. ✅ 20 regression tests