# Phase AU Quick Reference

## The Problem (One Diagram)

```
Raw GEE Data (S2 B4, B8, B11, B12)
    ↓ Retrieved ✓
ScanCell (s2_b4, s2_b8, s2_b11, s2_b12)
    ↓ 
Normalization Pipeline ❌ MISSING: compute spectral indices
    ↓
ObservableVector (x_spec_1..8 should be clay, ferric, ndvi)
    ↓ All null (because not computed)
Evidence Score (E_i = weighted mean of observables)
    ↓ Computed from SAR + thermal only (~70% of information)
ACIF (varies, but incomplete)
    ↓
Users see: "Gold prospectivity score: 0.42"
    but don't know: "Missing 30% of spectral data"
```

---

## The Solution (Three Parts)

### Part A: Validate Scans (Phase AU.1) ✅ DONE

**Models:** `scan_validation_model.py`
```python
@dataclass
class ScanValidationSummary:
    validation_status: ScanValidationStatus  # enum
    sensor_coverage: SensorCoverageReport    # per-modality %
    observable_distribution: ...             # per-observable stats
    vector_integrity: ...                    # uniqueness detection
    component_contributions: ...             # ACIF breakdown
    alert_messages: list[str]                # for users
```

**Service:** `scan_validator.py`
```python
validate_scan(scan_id, commodity, scan_cells, 
              observable_vectors, cell_results, 
              scan_aggregates) → ScanValidationSummary
```

**Output (Example):**
```
Status: INSUFFICIENT_SPECTRAL_SUPPORT ⚠️
Alerts:
  ❌ Sentinel-2 coverage only 31%
  ❌ Spectral indices missing for 100% of cells
Warning:
  ⚠️ Do not rank alongside production scans
```

---

### Part B: Fix Spectral Indices (Phase AU.2) ⏳ TODO

**Problem:** Clay/ferric = 0 across all cells

**Solution:** Implement spectral index computation

```python
def compute_spectral_indices(b4, b8, b11, b12):
    """Derive from S2 raw bands → normalized [0, 1]"""
    clay_index = (b11 + b4) / (b11 - b4 + 1e-8)
    ferric_ratio = b4 / b8 if b8 > 0 else 0
    ndvi = (b8 - b4) / (b8 + b4 + 1e-8)
    return {'x_spec_1': clay, 'x_spec_2': ferric, ...}
```

**Where?**
- Option A: In `gee_sensor_pipeline.py` (Python)
- Option B: In `core/normalisation.py` (after raw band retrieval)

**Impact:**
- Clay/ferric go from 0% to > 50% coverage
- Evidence scores improve (30% more information)
- ACIF values more accurate

---

### Part C: Dynamic Thresholds (Phase AU.3–AU.4) ⏳ TODO

**Problem:** Hard-coded tier thresholds same for gold everywhere

**Solution:** Calibrate per commodity + geological context

```python
CalibrationVersion(
    version_id="gold_orogenic_waf_v1",
    commodity="gold",
    geological_context="orogenic_lode",
    basin_code="waf_craton",
    source_ground_truths=[12 approved deposits],
    threshold_set=ThresholdSet(
        t1=0.68,  # from p90 of real deposits
        t2=0.42,  # from p70
        t3=0.18,  # from p40
    ),
    derivation_method="ground_truth_percentile_90_70_40",
)
```

**Impact:**
- Thresholds adapt to local geology
- Tier assignments more accurate
- Full audit trail (lineage tracking)
- Immutable historical scans (reprocessing creates new versions)

---

## Implementation Order

### Week 1: Validation (Low Risk)
```
Day 1-2:
  ✅ Models ready: scan_validation_model.py
  ✅ Service ready: scan_validator.py
  → Extend CanonicalScan.validation_summary
  → Call validate_scan() at pipeline step 19
  → Add API endpoint
  → Display badge on frontend

Risk: Minimal (observational only, no changes to ACIF/tiers)
```

### Week 2: Spectral Indices (Medium Risk)
```
Day 1-2:
  → Diagnose: Are S2 bands in ScanCell?
  → Find: Where spectral indices should be computed
  → Implement: compute_spectral_indices()
  → Test: Verify clay/ferric populate

Risk: Moderate (changes raw input, could affect ACIF)
       Mitigation: Reprocess small test set first
```

### Week 3-4: Calibration (Low-Medium Risk)
```
Day 1-7:
  → Seed ground truth DB with 50+ deposits
  → Build threshold_calibrator.py
  → Calibrate gold (WAF + greenstone)
  → Deploy calibrated versions
  → Reprocess 10 historical scans (new versions, old immutable)
  → Compare before/after tier distributions

Risk: Low (new feature, doesn't affect old scans)
```

---

## Files Delivered

### Code (Production-Ready)
```
aurora_vnext/app/models/scan_validation_model.py      (8 KB)
├─ SensorCoverageReport
├─ ObservableDistributionReport
├─ VectorIntegrityReport
├─ ComponentContributionReport
└─ ScanValidationStatus enum + ScanValidationSummary

aurora_vnext/app/services/scan_validator.py           (21 KB)
├─ compute_sensor_coverage()
├─ compute_observable_distribution()
├─ compute_vector_integrity()
├─ compute_component_contributions()
└─ validate_scan()  ← Main entry point
```

### Documentation (Specification)
```
VALIDATION_CALIBRATION_ARCHITECTURE.md    (20 KB)
  Parts A–F: Complete design (validation + calibration)

PHASE_AU_ROOT_CAUSE_AND_ROADMAP.md        (9 KB)
  Root cause analysis + step-by-step roadmap

VALIDATION_SUMMARY_EXAMPLE.md              (10 KB)
  Concrete example of suspicious scan validation

DELIVERABLES_SUMMARY.md                   (14 KB)
  Overview of all deliverables + success criteria

QUICK_REFERENCE.md                        (This file)
  Visual guide + quick links
```

---

## Validation Status Enum (Constitutional)

```python
class ScanValidationStatus(str, Enum):
    VALID_FOR_RANKING = "valid_for_ranking"
    # ✅ All sensors present, high coverage, diverse vectors
    # Tier assignments safe for ranking / analysis
    
    PARTIAL_MODALITY_SUPPORT = "partial_modality_support"
    # ⚠️ 2-3 modalities present, explicit warning required
    # "Tier assignments based on limited data"
    
    INSUFFICIENT_SPECTRAL_SUPPORT = "insufficient_spectral_support"
    # ⚠️ S2 < 50% OR spectral indices missing
    # "Spectral alteration signal unavailable"
    
    INSUFFICIENT_DATA = "insufficient_data"
    # ❌ Multi-modal coverage < 50%
    # DO NOT rank. Return with error.
```

---

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Validation status on scans | None | 100% have status | VALID or flagged |
| Clay/ferric coverage | 0% | > 50% | ✓ |
| Hard-coded thresholds | 1 global set | 5+ calibrated | ✓ |
| Ground truth records | ? | 50+ | ✓ |
| Scan reproducibility | None | Full lineage | ✓ |
| User trust | ❓ | Explicit warnings | ✓ |

---

## Critical Questions for Implementation

1. **Spectral Indices:**
   - Are S2 bands (b4, b8, b11, b12) in ScanCell? (grep confirm)
   - Where do they go? (find compute_spectral_indices or create)

2. **Ground Truth DB:**
   - Are there approved GroundTruthRecords with ACIF scores?
   - How many per commodity?

3. **Calibration Versions:**
   - Can we mark a CalibrationVersion as ACTIVE?
   - How does scan_pipeline.py fetch active version?

4. **Integration Points:**
   - Where in scan_pipeline.py should we call validate_scan()?
   - Which API router for `/scan/{id}/validation` endpoint?

---

## Timeline

```
Today:        Architecture complete ✅ (delivered)
Tomorrow:     Merge validation code into pipeline
              Diagnose spectral indices
Day 3:        Validation framework live on new scans
Day 4-7:      Fix spectral indices
Week 2:       Validation + spectral working, tested
Week 3:       Build calibration infrastructure
Week 4:       Deploy calibrated thresholds, reprocess
```

---

## Contact

**Specification & Code:** Complete  
**Ready to Merge:** scan_validation_model.py + scan_validator.py  
**Next Step:** Integration into scan_pipeline.py + spectral index diagnosis

---