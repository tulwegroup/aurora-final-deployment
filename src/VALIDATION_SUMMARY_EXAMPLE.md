# Validation Summary Example: Suspicious Scan

**Scan ID:** scan_20260329_gold_mali_001  
**Commodity:** gold  
**AOI:** Mali – Kédougou-Kéniéba greenstone belt  
**Status:** COMPLETED  

---

## Executive Summary

```
VALIDATION STATUS: ⚠️ INSUFFICIENT_SPECTRAL_SUPPORT

Alert Messages:
  ❌ Sentinel-2 coverage only 31.2%. Spectral alteration indices unavailable.
  ❌ 42 observables have zero coverage (all cells null). Spectral indices may be missing.
  ⚠️ Multi-modal coverage only 43.5%. Evidence score may be unreliable.

Recommendation:
  DO NOT RANK this scan alongside production results.
  Present tier assignments with explicit warning to users.
```

---

## Detailed Reports

### 1. SENSOR COVERAGE REPORT

| Modality | Valid Cells | Coverage | Alert |
|----------|-------------|----------|-------|
| **Sentinel-2 (S2)** | 28 / 90 | **31.2%** | ❌ Below 50% |
| Sentinel-1 (SAR) | 78 / 90 | 86.7% | ✓ OK |
| Landsat 8 Thermal | 42 / 90 | 46.7% | ⚠️ Near threshold |
| SRTM DEM | 88 / 90 | 97.8% | ✓ OK |
| **All 4 Modalities** | 18 / 90 | **20.0%** | ❌ Critical |

**Cloud Coverage (S2):**
- Mean: 28.4%
- Max: 62.1% (cell_042)
- Min: 0.3% (cell_001)

**Interpretation:**
- S2 is severely limited due to cloud cover during acquisition window
- Only 20 cells have complete multi-modal data
- SAR and DEM compensate for missing spectral information

---

### 2. OBSERVABLE DISTRIBUTION REPORT

**Spectral Observables (x_spec_1..x_spec_8):**
```
x_spec_1 (Clay Index)      : 0 / 90 cells valid | 0.0% coverage | ❌ ZERO COVERAGE
x_spec_2 (Ferric Ratio)    : 0 / 90 cells valid | 0.0% coverage | ❌ ZERO COVERAGE
x_spec_3 (NDVI)            : 24 / 90 cells valid | 26.7% coverage | ⚠️ LOW COVERAGE
x_spec_4 (NDBI)            : 24 / 90 cells valid | 26.7% coverage | ⚠️ LOW COVERAGE
x_spec_5..x_spec_8         : All null (missing from satellite data)
```

**SAR Observables (x_sar_1..x_sar_6):** ✓ 78/90 cells valid (86.7%)

**Thermal Observables (x_therm_1..x_therm_4):** ⚠️ 42/90 cells valid (46.7%)

**Summary:**
```
Total Observables: 42
├─ Zero Coverage: 28 (including all 8 spectral indices — CRITICAL)
├─ Low Coverage (<50%): 8
└─ Good Coverage (≥50%): 6
```

**Alert:** Clay and ferric indices are entirely absent. This suggests either:
1. **Raw S2 bands were not retrieved** by GEE worker
2. **Spectral index computation is not implemented** in normalisation pipeline
3. **Both:** combining to silently fail

---

### 3. VECTOR INTEGRITY REPORT

```
Raw Vector Uniqueness:      62.2% (56/90 unique)
├─ Duplicated vectors:      1 pair (2 cells with identical raw observables)
└─ Near-duplicates (<0.05): 4 clusters of 2-3 cells

Normalized Vector Uniqueness: 58.9% (53/90 unique)
├─ Duplicated vectors:      3 pairs
└─ Near-duplicates:         6 clusters

Broadcasting Detected:      ❌ NO
  (Uniqueness > 20%, so vectors are not uniformly identical)
```

**Interpretation:**
- Vectors vary naturally across the AOI
- No evidence of fallback/mock data
- But: Spectral uniformity (all x_spec_* = null) reduces effective diversity

---

### 4. COMPONENT CONTRIBUTION REPORT

**ACIF Component Means (Scan Level):**
```
Evidence Score (Ẽ)        : 0.38 (40-90% weighting from SAR + thermal only)
Causal Score (C)          : 0.71
Physics Score (Ψ)         : 0.65
Temporal Score (T)        : 0.52
Province Prior (Π)        : 0.48 (Mali craton setting, below expected for gold)
Certainty (1-U)           : 0.61
─────────────────────────
Mean ACIF                 : 0.06 (LOW — driven by low evidence + province prior)
```

**ACIF Distribution:**
```
Percentile   Value
p25          0.01
p50          0.04
p75          0.11
p90          0.28

Std Dev:     0.07
```

**Correlations (Pearson r):**
```
Evidence ↔ ACIF       : +0.82 (strong — evidence drives ACIF)
Physics ↔ ACIF        : +0.45 (moderate)
Temporal ↔ ACIF       : +0.34 (weak)
Province Prior ↔ ACIF : +0.12 (very weak — prior doesn't vary much)
```

**Veto Counts:**
```
Causal Veto Fired        : 0 cells
Physics Veto Fired       : 12 cells
Province Veto Fired      : 0 cells
Any Veto                 : 12 cells (13.3%)
```

**Modality Contributions (Mean):**
```
Spectral (x_spec_*)      : NULL (unavailable)
SAR (x_sar_*)            : 0.71 (primary signal)
Thermal (x_therm_*)      : 0.48 (secondary)
Gravity (not in this commodity)
Magnetic (not in this commodity)
```

**Interpretation:**
- Evidence score is **entirely driven by SAR** (clay/ferric missing)
- Province prior is low → depresses ACIF further
- Final ACIF (0.06 mean) is below typical gold exploration threshold
- Missing spectral signal likely suppresses true prospectivity signal

---

## Validation Status Decision

### Status: `INSUFFICIENT_SPECTRAL_SUPPORT`

**Criteria Met:**
- ✗ Sentinel-2 coverage: 31.2% < 50% threshold
- ✗ Spectral observable coverage: 0% (all clay/ferric null)
- ✓ SAR coverage: 86.7% (good)
- ✓ Vector integrity: No broadcasting (58.9% uniqueness)

**Recommendation:**
```
This scan CAN be presented to users with EXPLICIT WARNINGS:

❌ "Spectral Alteration Signal Unavailable"
   This scan lacks Sentinel-2 spectral data due to cloud cover.
   Tier assignments are based on SAR and thermal data only and may
   not accurately represent true gold prospectivity. Do not compare
   tier distributions directly with spectral-supported scans.

✅ Recommendation: Resubmit with:
   • Different date range (dry season, lower cloud probability)
   • Finer resolution (more cells, higher chance of cloud-free)
   • Larger AOI (statistical averaging across more cells)
```

---

## Comparison: Valid Scan vs. This Scan

**Valid Scan (scan_20260315_gold_ghana_002):**
```
S2 Coverage:              88.3% ✓
Spectral Observables:     7/8 > 50% coverage ✓
SAR Coverage:             92.1% ✓
Thermal Coverage:         61.2% ✓
Multi-Modal:              78% all 4 ✓
Vector Uniqueness:        94.2% ✓
─────────────────────────
Evidence Score:           0.58 (balanced modalities)
Mean ACIF:                0.31 (typical for greenstone belt)
─────────────────────────
Validation Status:        ✅ VALID_FOR_RANKING
Recommendation:           Present without warnings. Suitable for ranking.
```

**This Scan (scan_20260329_gold_mali_001):**
```
S2 Coverage:              31.2% ❌
Spectral Observables:     0/8 > 50% coverage ❌
SAR Coverage:             86.7% ✓
Thermal Coverage:         46.7% ⚠️
Multi-Modal:              20% all 4 ❌
Vector Uniqueness:        58.9% ⚠️
─────────────────────────
Evidence Score:           0.38 (SAR-dominated)
Mean ACIF:                0.06 (artificially low due to missing spectral)
─────────────────────────
Validation Status:        ⚠️ INSUFFICIENT_SPECTRAL_SUPPORT
Recommendation:           Present with warnings. Do not rank alongside valid scans.
```

---

## Diagnostic Trace

```json
{
  "scan_id": "scan_20260329_gold_mali_001",
  "validation_module_version": "phase_au_v1",
  "validation_timestamp": "2026-03-29T14:22:37Z",
  "diagnostics": {
    "s2_band_retrieval": {
      "b4_null_count": 62,
      "b8_null_count": 62,
      "b11_null_count": 62,
      "b12_null_count": 62,
      "hypothesis": "GEE worker returned null for all S2 bands in 69% of cells",
      "root_cause_likely": "Cloud masking filtered out cells above 20% cloud threshold"
    },
    "spectral_index_computation": {
      "clay_index_found": false,
      "ferric_ratio_found": false,
      "ndvi_found": true,
      "hypothesis": "Spectral indices not computed from raw bands; NDVI present suggests partial implementation"
    },
    "observable_population": {
      "x_spec_1_to_x_spec_8_status": "All null across all cells",
      "x_sar_status": "86.7% populated",
      "x_therm_status": "46.7% populated",
      "inference": "Spectral index computation is missing or disabled"
    }
  }
}
```

---

## API Response Example

```json
{
  "scan_id": "scan_20260329_gold_mali_001",
  "validation_status": "insufficient_spectral_support",
  "alert_messages": [
    "Sentinel-2 coverage only 31.2%. Spectral alteration indices unavailable.",
    "42 observables have zero coverage (all cells null). Spectral indices may be missing.",
    "Multi-modal coverage only 43.5%. Evidence score may be unreliable."
  ],
  "warning_messages": [
    "Thermal data only 46.7% coverage. Reprocessing with higher resolution recommended."
  ],
  "sensor_coverage": {
    "total_cells": 90,
    "s2_valid_cells": 28,
    "s2_coverage_pct": 31.2,
    "s2_cloud_mean_pct": 28.4,
    "s1_coverage_pct": 86.7,
    "thermal_coverage_pct": 46.7,
    "dem_coverage_pct": 97.8,
    "multi_modal_coverage_pct": 20.0
  },
  "observable_distribution": {
    "zero_coverage_observables": ["x_spec_1", "x_spec_2", ..., "x_grav_3"],
    "zero_coverage_count": 28,
    "low_coverage_count": 8,
    "suspicious_uniform_count": 0
  },
  "vector_integrity": {
    "raw_vector_uniqueness_pct": 62.2,
    "normalized_vector_uniqueness_pct": 58.9,
    "broadcasting_suspected": false
  },
  "component_contributions": {
    "mean_evidence_score": 0.38,
    "mean_acif": 0.06,
    "acif_stdev": 0.07,
    "cells_with_any_veto": 12
  }
}
```

---

## Summary

**Key Finding:**
This scan is **scientifically incomplete**. Spectral alteration signals (clay, ferric) are entirely absent, likely due to cloud cover or missing spectral index computation. Users should be warned not to compare tier distributions with production scans, and encouraged to resubmit with better imagery.

**The validation framework caught this automatically.**

Without Phase AU validation, users would silently receive:
- ACIF = 0.06 (misleadingly low)
- ~80% TIER_3 / BELOW (incorrect clustering)
- No explanation for why scores are anomalous

**With Phase AU:**
- Status flag: `INSUFFICIENT_SPECTRAL_SUPPORT` ✓
- Clear alert messages explaining why ✓
- Diagnostic trace for debugging ✓
- User guidance for resubmission ✓

---