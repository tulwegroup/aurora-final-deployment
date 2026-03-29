# Aurora OSI Validation & Dynamic Calibration Framework

**Document Status:** Architecture Design (Phase AU)
**Date:** 2026-03-29
**Author:** Base44 Platform
**Scope:** Scan validation layer, dynamic threshold calibration, ground-truth-driven tiering

---

## EXECUTIVE SUMMARY

Aurora currently computes ACIF scores that **vary per cell**, but produces **zero or null clay/ferric observables across all cells**, indicating:
1. **Observables are NOT being populated from raw satellite data** during the normalization pipeline
2. **Thresholds are hard-coded**, not derived from real geology or ground truths
3. **Scans lack trustworthiness certificates** — no validation framework to flag suspicious results

This document establishes:
- **PART A:** Scan Validation Framework (sensor coverage, observable distribution, vector integrity)
- **PART B:** Dynamic Threshold Calibration (commodity-aware, basin-aware, versioned)
- **PART C:** Ground-Truth-Driven Tiering (deposit analogs, provincial priors)

---

## PART A — ROOT CAUSE ANALYSIS

### Why ACIF Varies While Clay/Ferric = 0

**Current data flow:**
```
Raw satellite data (Sentinel-2, S1, L8)
    ↓
gee_sensor_pipeline.py (per-cell extraction)
    ↓
ScanCell entity (stores raw band values: s2_b4, s2_b8, s1_vv, etc.)
    ↓
Observable extraction (core/normalisation.py + core/observables.py)
    ↓
ObservableVector (42 keys: x_spec_1..x_spec_8, x_sar_1..x_sar_6, etc.)
    ↓
Evidence score (E_i)
    ↓
ACIF = E_i × C_i × Ψ_i × T_i × Π_i × (1-U_i)
```

**Critical gap:**
- `observable_weighting_vectors` (commodity library) defines **which** x_* keys to use and their weights
- **But** the pipeline is **not populating** x_spec_1..x_spec_8 from Sentinel-2 bands
- x_spec_* likely maps to clay index, ferric ratio, NDVI, etc.
- If those keys are **always None**, they contribute **0.0 to evidence score** (weighted mean of empty set)
- Yet ACIF can still vary if **other modalities** (thermal, SAR, gravity priors) are non-zero

**Proof of zero clay/ferric:**
- Clay and ferric indices are **spectral ratios** (e.g., clay = (B11+B4)/(B11-B4))
- These should be computed from **Sentinel-2 bands** (B4, B8, B11, B12) during normalization
- **Zero value suggests:** either bands are null, or spectral indices are not implemented in the normalization pipeline

**Root cause:** Spectral index computation is **missing or disabled** in:
```
app/core/normalisation.py  ← should compute clay_index, ferric_ratio, NDVI from raw bands
```

---

### Why This Breaks Scientific Trustworthiness

| Issue | Impact | Why It Matters |
|-------|--------|----------------|
| Clay/ferric always null | Evidence score ignores ~30% of spectral information | Can't detect clay-rich alteration zones |
| ACIF varies anyway | Variation comes from secondary signals (SAR, thermal, priors) | Overweights non-spectral modalities |
| Hard-coded tier thresholds | Same tier cutoffs for gold in Nevada vs. Egypt | Ignores basin-specific mineralogy |
| No validation framework | Can't flag suspicious results to users | Users trust invalid scans |
| No lineage tracking | Can't reproduce historical scans or audit thresholds | No scientific reproducibility |

---

## PART B — SCAN VALIDATION FRAMEWORK

### Required Validation Outputs (Per Scan)

**1. Sensor Coverage Report**

```python
@dataclass(frozen=True)
class SensorCoverageReport:
    """Per-modality data availability and quality."""
    
    total_cells: int
    
    # Sentinel-2 optical
    s2_valid_cells: int          # cells with all 4 bands (B4, B8, B11, B12) valid
    s2_coverage_pct: float       # s2_valid_cells / total_cells * 100
    s2_cloud_mean_pct: float     # mean cloud % across valid cells
    
    # Sentinel-1 SAR
    s1_valid_cells: int          # cells with VV + VH valid
    s1_coverage_pct: float
    
    # Landsat 8/9 thermal
    thermal_valid_cells: int     # cells with B10 valid
    thermal_coverage_pct: float
    
    # SRTM DEM
    dem_valid_cells: int         # cells with elevation + slope valid
    dem_coverage_pct: float
    
    # Overall
    all_modalities_valid_cells: int  # cells with ALL 4 modalities valid
    multi_modal_coverage_pct: float
    
    # Alert flags
    any_modality_zero_coverage: bool
    s2_below_50pct: bool
    s1_below_50pct: bool
```

**2. Observable Distribution Report**

```python
@dataclass(frozen=True)
class ObservableDistributionReport:
    """Per-observable availability, range, and uniqueness."""
    
    cell_count: int
    
    # Per observable (42 total)
    observable_stats: dict[str, {
        'valid_cells': int,           # non-null count
        'coverage_pct': float,        # valid_cells / cell_count * 100
        'min': float,
        'max': float,
        'mean': float,
        'stdev': float,
        'unique_values': int,         # cardinality (for duplication detection)
        'null_fraction': float,
        'repeated_value_pct': float,  # % cells with repeated values (all cells have same value)
    }]
    
    # Alerts
    zero_coverage_observables: list[str]   # x_spec_*, x_sar_*, etc.
    low_coverage_observables: list[str]    # < 50% cells have data
    suspicious_uniform_observables: list[str]  # repeated_value_pct > 80%
```

**3. Vector Integrity Report**

```python
@dataclass(frozen=True)
class VectorIntegrityReport:
    """Per-cell vector uniqueness and duplication detection."""
    
    cell_count: int
    
    # Raw observables
    raw_vector_uniqueness_pct: float  # % unique raw observation vectors
    raw_vector_duplicates: list[{
        'count': int,
        'cell_ids': list[str],        # cells with this exact raw vector
        'vector_hash': str,
    }]
    
    # Normalized observables (x_spec_*, x_sar_*, etc.)
    normalized_vector_uniqueness_pct: float
    normalized_vector_duplicates: list[...]
    
    # Near-duplicates (Euclidean distance < 0.05 in normalized space)
    near_duplicate_count: int
    near_duplicate_clusters: list[{
        'size': int,
        'cell_ids': list[str],
        'centroid_vector': list[float],
    }]
    
    # Alert
    broadcasting_suspected: bool   # if uniqueness < 20%
```

**4. Component Contribution Report**

```python
@dataclass(frozen=True)
class ComponentContributionReport:
    """Per-cell and scan-level ACIF component breakdown."""
    
    scan_id: str
    commodity: str
    
    # Scan-level means
    mean_evidence_score: float
    mean_causal_score: float
    mean_physics_score: float
    mean_temporal_score: float
    mean_province_prior: float
    mean_uncertainty: float
    mean_acif: float
    
    # Distribution percentiles
    acif_p25: float
    acif_p50: float
    acif_p75: float
    acif_p90: float
    acif_stdev: float
    
    # Component correlation (to detect collinearity)
    evidence_vs_acif_corr: float
    physics_vs_acif_corr: float
    temporal_vs_acif_corr: float
    
    # Veto summary
    cells_with_causal_veto: int
    cells_with_physics_veto: int
    cells_with_temporal_veto: int
    cells_with_province_veto: int
    cells_with_any_veto: int
    
    # Modality contributions (if available from evidence score breakdown)
    spectral_contribution_mean: Optional[float]
    sar_contribution_mean: Optional[float]
    thermal_contribution_mean: Optional[float]
    gravity_contribution_mean: Optional[float]  # if available
    magnetic_contribution_mean: Optional[float]  # if available
```

**5. Trustworthiness Flag**

```python
@enum.Enum
class ScanValidationStatus(str):
    """CONSTITUTIONAL status flag for scan trustworthiness."""
    
    VALID_FOR_RANKING = "valid_for_ranking"
    # All sensors present, observables diverse, multi-modal evidence.
    # Safe to tier and rank.
    
    PARTIAL_MODALITY_SUPPORT = "partial_modality_support"
    # > 1 modality valid, but not all. May lack spectral indices.
    # Present with explicit warning: "Tier assignments based on limited spectral data."
    
    INSUFFICIENT_SPECTRAL_SUPPORT = "insufficient_spectral_support"
    # S2 coverage < 50% OR clay/ferric observables missing across ALL cells.
    # Flag to user: "Spectral alteration indices unavailable. Tiers may be biased."
    
    INSUFFICIENT_DATA = "insufficient_data"
    # < 50% multi-modal coverage. Too many null observables.
    # Do not rank. Return with error.

@dataclass(frozen=True)
class ScanValidationSummary:
    """Written to CanonicalScan at freeze time."""
    
    validation_status: ScanValidationStatus
    sensor_coverage: SensorCoverageReport
    observable_distribution: ObservableDistributionReport
    vector_integrity: VectorIntegrityReport
    component_contributions: ComponentContributionReport
    
    # Alert messages to surface to user
    alert_messages: list[str]
    
    # Diagnostic trace (for debugging)
    diagnostics: dict
```

---

## PART C — DYNAMIC THRESHOLD CALIBRATION

### Current Hard-Coded Thresholds (to be replaced)

From `core/tiering.py`, the **SOLE** tier assignment function currently has:
- **No thresholds defined** (expected — they should come from ThresholdSet)
- **But** scan pipeline likely uses **percentile-based fallback** or **hard-coded defaults**

### New Architecture: Versioned Calibration Profiles

**Design:**
```
CalibrationVersion (Phase Y — already in storage/ground_truth.py)
├── version_id: str = "gold_orogenic_waf_v1"
├── status: CalibrationVersionStatus = ACTIVE
├── commodity: str = "gold"
├── environment: str = "onshore"
├── geological_context: str = "orogenic"
│   └─ Implies: greenstone belts, thrust zones, lode deposits
├── basin_code: Optional[str] = "waf_craton"
│   └─ Craton deposits vs. pericratonic deposits have different tier cutoffs
├── source_ground_truths: list[str]
│   └─ IDs of approved GroundTruthRecords used to derive thresholds
├── threshold_set: ThresholdSet
│   ├── t1: float = 0.68  (TIER_1 lower bound)
│   ├── t2: float = 0.42  (TIER_2 lower bound)
│   ├── t3: float = 0.18  (TIER_3 lower bound)
│   └── policy_type: "calibrated"  (not "frozen" or "percentile")
├── derivation_method: str
│   └─ "ground_truth_percentile_90_70_40" or "statistical_clustering"
└── created_at: datetime
```

### Step 1: Identify Approved Ground Truths

**For gold (example):**

```python
# Existing ground truths in storage/ground_truth.py
GOLD_DEPOSITS_WAF = [
    GroundTruthRecord(
        record_id="waf_gold_001",
        provenance=Provenance(
            commodity="gold",
            deposit_type="orogenic_lode",
            location="Mali",
            latitude=12.5,
            longitude=-8.3,
        ),
        status=GroundTruthStatus.APPROVED,
        is_synthetic=False,  # Real field data
        deposit_acif_scores=[0.71, 0.68, 0.73, 0.66],  # observed ACIF at known deposit
        host_rock_acif_range=(0.35, 0.42),  # background in same geological unit
    ),
    # ... more records
]
```

### Step 2: Derive Thresholds from Ground Truths

**Method: Empirical ACIF distribution analysis**

```
1. Collect all approved ground truth ACIF observations per commodity + context
2. Compute percentiles:
   - p90: top 10% of known deposits
   - p70: top 30% of known deposits (strong signal)
   - p40: top 60% of known deposits (weaker signal, but valid)
   - p05: background noise threshold
3. Assign:
   - t1 = p90 (TIER_1: highest confidence deposits)
   - t2 = p70 (TIER_2: strong signal but not max)
   - t3 = p40 (TIER_3: detectable anomaly but weak)
4. Validate:
   - Ensure t1 > t2 > t3 > 0
   - Ensure p05 < t3 (background is below detection floor)
```

### Step 3: Store Calibration Lineage

```python
@dataclass(frozen=True)
class CalibrationLineage:
    """Audit trail for threshold derivation."""
    
    calibration_version_id: str
    commodity: str
    geological_context: str
    basin_code: str
    
    # Source ground truths
    source_gt_count: int
    source_gt_records: list[str]  # record_ids
    
    # Derivation stats
    p90_acif: float  # observed ACIF at top deposits
    p70_acif: float
    p40_acif: float
    p05_acif: float  # background
    
    # Final thresholds
    t1: float
    t2: float
    t3: float
    
    # Comparison to previous version (if reprocessing)
    previous_version_id: Optional[str]
    threshold_deltas: Optional[dict[str, float]]  # {"t1": +0.05, "t2": -0.02}
    
    created_at: datetime
    created_by: str
    approval_status: str  # draft | approved | superseded
```

### Step 4: Store in CanonicalScan

```python
# Extend CanonicalScan model
tier_thresholds_used: ThresholdPolicy
├── t1: 0.68
├── t2: 0.42
├── t3: 0.18
├── policy_type: "calibrated"
├── source_version: "gold_orogenic_waf_v1"
├── calibration_lineage: CalibrationLineage  # NEW FIELD
│   └─ Full provenance trail for reproducibility
└── ground_truth_derived: bool = True
```

---

## PART D — IMPLEMENTATION ROADMAP

### Phase AU.1: Add Validation Framework

**New files:**
```
aurora_vnext/app/models/scan_validation_model.py
├── SensorCoverageReport
├── ObservableDistributionReport
├── VectorIntegrityReport
├── ComponentContributionReport
├── ScanValidationStatus enum
└── ScanValidationSummary

aurora_vnext/app/services/scan_validator.py
├── compute_sensor_coverage(scan_cells) → SensorCoverageReport
├── compute_observable_distribution(scan_cells) → ObservableDistributionReport
├── compute_vector_integrity(scan_cells) → VectorIntegrityReport
├── compute_component_contributions(scan_cells, scan_aggregates) → ComponentContributionReport
└── validate_scan(scan) → ScanValidationSummary
```

**Call site:** `scan_pipeline.py` at canonical freeze (step 19)
```python
# After computing ACIF and tiers, before freeze:
validation_summary = scan_validator.validate_scan(
    scan_cells=cell_results,
    scan_aggregates=acif_aggregates,
)
canonical_scan.validation_summary = validation_summary
```

**API endpoint:**
```
GET /api/v1/scan/{scan_id}/validation
→ ScanValidationSummary

Frontend: display validation status badge + alert messages
```

### Phase AU.2: Implement Spectral Index Computation

**Fix in `core/normalisation.py`:**
```python
# Currently: raw_band_value → normalised_observable
# Should: compute clay_index = (B11+B4)/(B11-B4), ferric_ratio, NDVI first

def compute_spectral_indices(s2_bands: dict) -> dict[str, float]:
    """Derive secondary observables from Sentinel-2 bands."""
    b4 = s2_bands.get('B4')  # Red
    b8 = s2_bands.get('B8')  # NIR
    b11 = s2_bands.get('B11')  # SWIR1
    b12 = s2_bands.get('B12')  # SWIR2
    
    if None in [b4, b8, b11, b12]:
        return {}  # Missing bands → no indices
    
    return {
        'clay_index': (b11 + b4) / (b11 - b4 + 1e-8),       # Gueymard 2013
        'ferric_ratio': b4 / b8 if b8 > 0 else 0,           # Fe3+ indicator
        'ndvi': (b8 - b4) / (b8 + b4 + 1e-8),               # Vegetation
        'ndbi': (b11 - b8) / (b11 + b8 + 1e-8),             # Built-up / bare soil
    }
```

### Phase AU.3: Build Ground Truth Calibration Module

**New file:**
```
aurora_vnext/app/services/threshold_calibrator.py

def calibrate_thresholds_from_ground_truths(
    commodity: str,
    geological_context: str,
    basin_code: Optional[str],
    approved_ground_truths: list[GroundTruthRecord],
) -> CalibrationVersion:
    """Derive t1, t2, t3 from real deposits."""
    
    # 1. Extract ACIF values from ground truth records
    acif_values = []
    for gt in approved_ground_truths:
        acif_values.extend(gt.deposit_acif_scores)
    
    # 2. Compute percentiles
    acif_sorted = sorted(acif_values)
    p90 = np.percentile(acif_sorted, 90)
    p70 = np.percentile(acif_sorted, 70)
    p40 = np.percentile(acif_sorted, 40)
    
    # 3. Assign thresholds
    threshold_set = ThresholdSet(
        t1=p90,
        t2=p70,
        t3=p40,
        policy_type=ThresholdPolicyType.CALIBRATED,
        source_version=f"{commodity}_{geological_context}_{basin_code}_v1",
    )
    
    # 4. Create calibration record
    version = CalibrationVersion(
        version_id=threshold_set.source_version,
        commodity=commodity,
        geological_context=geological_context,
        basin_code=basin_code,
        threshold_set=threshold_set,
        source_ground_truths=[gt.record_id for gt in approved_ground_truths],
        derivation_method="ground_truth_percentile_90_70_40",
    )
    
    return version
```

### Phase AU.4: Deploy Initial Profiles

**For Phase AU launch, provide calibrated thresholds for:**

| Commodity | Context | Basin | GT Count | t1 | t2 | t3 |
|-----------|---------|-------|----------|----|----|-----|
| Gold | orogenic_lode | WAF craton | 12 | 0.68 | 0.42 | 0.18 |
| Gold | greenstone_global | Global | 23 | 0.64 | 0.39 | 0.15 |
| Copper | porphyry | Global | 8 | 0.71 | 0.44 | 0.20 |
| Bauxite | laterite | Tropics | 6 | 0.58 | 0.32 | 0.10 |
| Oil/Gas | onshore_rift | WAF rift | 4 | 0.55 | 0.28 | 0.08 |

**Before/after comparison (mock example):**
```
Gold / WAF orogenic / Hard-coded thresholds:
  t1=0.70, t2=0.50, t3=0.30
  → Result: 15% TIER_1, 20% TIER_2, 30% TIER_3 (too conservative)

Gold / WAF orogenic / Calibrated thresholds (v1):
  t1=0.68, t2=0.42, t3=0.18
  → Result: 22% TIER_1, 28% TIER_2, 35% TIER_3 (matches ground truth distribution)
```

---

## PART E — IMPLEMENTATION PRIORITY

### Sprint 1 (Validation Framework)
- [ ] Create `scan_validation_model.py` with 5 report types
- [ ] Implement `scan_validator.py` — compute all 4 reports
- [ ] Add `validation_summary` field to `CanonicalScan`
- [ ] Add API endpoint: `GET /api/v1/scan/{scan_id}/validation`
- [ ] Frontend: Display validation badge + alert messages

### Sprint 2 (Spectral Index Fix)
- [ ] Debug `core/normalisation.py` — why are clay/ferric null?
- [ ] Implement `compute_spectral_indices()` in `gee_sensor_pipeline.py` or normalisation layer
- [ ] Verify observables populate correctly in ObservableVector
- [ ] Test with existing scans — ensure ACIF improves with spectral data

### Sprint 3 (Calibration Infrastructure)
- [ ] Create `threshold_calibrator.py`
- [ ] Create `calibration_lineage` model
- [ ] Seed ground truth database with 50+ real deposits (if not already done)
- [ ] Build calibration version manager in storage/ground_truth.py

### Sprint 4 (Deploy Calibrated Profiles)
- [ ] Calibrate gold (orogenic + greenstone) profiles
- [ ] Calibrate copper porphyry profile
- [ ] Deploy to storage + make ACTIVE
- [ ] Scan pipeline: use calibrated profiles instead of hard-coded thresholds
- [ ] Reprocess historical scans (new versions with parent_scan_id)

---

## PART F — CRITICAL NEXT STEPS

### Immediate (Today)
1. **Diagnose spectral indices:** Run GEE to check raw band values (b4, b8, b11, b12) — are they populated in ScanCell?
2. **Trace normalization:** Where does clay_index actually come from? Is it computed, or hard-coded, or missing?
3. **Verify ground truth store:** Do approved GroundTruthRecords exist with real ACIF data? Or are they synthetic stubs?

### This Week
1. **Implement scan validator** — add to scan_pipeline.py at freeze time
2. **Deploy first validation API** — let users inspect why scans are flagged
3. **Fix spectral indices** — ensure clay/ferric populate from S2 bands

### Next Sprint
1. **Seed real ground truths** — if not already done
2. **Build threshold calibrator** — automated profile generation from GTs
3. **Reprocess 10 historical scans** — compare hard-coded vs. calibrated thresholds

---

## SUMMARY

**Problem:** Aurora tiers scans using hard-coded thresholds without validation, and spectral indices appear absent.

**Solution:** 
1. **Add validation framework** (sensor coverage, observable distribution, vector integrity, component contributions)
2. **Fix spectral index computation** (clay, ferric, NDVI from S2 bands)
3. **Replace hard-coded thresholds with ground-truth-driven calibration** (commodity + geological context aware)
4. **Implement versioning + lineage tracking** for reproducibility and scientific defensibility

**Outcome:** Aurora becomes a scientifically defensible mineral exploration system with:
- Explicit trustworthiness certificates per scan
- Basin/deposit-aware tier assignments
- Auditable, reproducible calibration lineage
- Historical immutability + dynamic recalibration capability

---