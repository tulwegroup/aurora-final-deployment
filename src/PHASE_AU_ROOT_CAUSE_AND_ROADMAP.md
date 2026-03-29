# Phase AU: Root Cause Analysis & Implementation Roadmap

**Status:** Architecture Complete + Initial Implementation  
**Date:** 2026-03-29  
**Scope:** Validation framework, threshold calibration, observable fix

---

## 1. ROOT CAUSE ANALYSIS

### Why ACIF Varies But Clay/Ferric = 0

**The Chain:**
```
Raw GEE data (S2 bands B4, B8, B11, B12)
   ↓
ScanCell.s2_b4, s2_b8, s2_b11, s2_b12 (stored ✓)
   ↓
Normalisation pipeline (core/normalisation.py)
   ↓
ObservableVector (42 keys: x_spec_1..x_spec_8, x_sar_1..6, etc.)
   ↓
Evidence score (E_i = weighted mean of observables)
   ↓
ACIF = E_i × C_i × Ψ_i × T_i × Π_i × (1-U)
```

**Why clay/ferric are zero:**
- Clay index = (B11+B4)/(B11-B4) — should be computed during normalisation
- Ferric ratio = B4/B8 — spectral ratio from raw bands
- **If x_spec_* keys are always null**, then evidence score is computed from secondary modalities (SAR, thermal, priors) only
- ACIF can still **vary per cell** if SAR/thermal/province are different → but **lacking ~30% of information**

**Critical Gap:**
`core/normalisation.py` likely does NOT compute spectral indices from raw bands.  
Check: Is there a function that transforms raw S2 bands → x_spec_1..x_spec_8?

### Why This Breaks Trust

| Issue | Impact | Fix |
|-------|--------|-----|
| Spectral indices missing | Can't detect clay-rich alteration | Implement `compute_spectral_indices()` in normalisation |
| Hard-coded tier thresholds | Same t1/t2/t3 for Nevada gold vs. Mali gold | Replace with ground-truth-driven calibration |
| No validation framework | Users can't tell if scan is trustworthy | Implement ScanValidationSummary (Phase AU.1 ✓) |
| No lineage tracking | Can't reproduce old scans or audit threshold changes | Store CalibrationLineage + CanonicalScan.validation_summary |

---

## 2. IMPLEMENTATION STATUS

### ✅ COMPLETED (Today)

**Phase AU.1 — Validation Framework:**
- [ ] `aurora_vnext/app/models/scan_validation_model.py` — All 5 model types
  - SensorCoverageReport (per-modality %)
  - ObservableDistributionReport (per-observable stats)
  - VectorIntegrityReport (uniqueness detection)
  - ComponentContributionReport (ACIF breakdown)
  - ScanValidationStatus enum + ScanValidationSummary
- [ ] `aurora_vnext/app/services/scan_validator.py` — Full validation pipeline
  - compute_sensor_coverage()
  - compute_observable_distribution()
  - compute_vector_integrity()
  - compute_component_contributions()
  - validate_scan() — main orchestrator

**Architecture Design:**
- [ ] `VALIDATION_CALIBRATION_ARCHITECTURE.md` — Complete design (Parts A–F)
- [ ] `PHASE_AU_ROOT_CAUSE_AND_ROADMAP.md` — This file

### 🔄 TODO (This Week)

**Phase AU.1 (continued) — Integration:**
- [ ] Add `validation_summary: Optional[ScanValidationSummary]` field to `CanonicalScan`
- [ ] Call `scan_validator.validate_scan()` in `scan_pipeline.py` at step 19 (before freeze)
- [ ] Add API endpoint: `GET /api/v1/scan/{scan_id}/validation`
- [ ] Frontend: Display validation badge + alert messages on scan detail page

**Phase AU.2 — Fix Spectral Indices:**
- [ ] Debug: Are raw S2 bands (b4, b8, b11, b12) populated in ScanCell? ✓ (likely yes from GEE)
- [ ] Identify: Where should spectral indices be computed?
  - Option A: In `gee_sensor_pipeline.py` (Python) — compute indices before returning
  - Option B: In `core/normalisation.py` (Python) — transform raw bands to indices
- [ ] Implement `compute_spectral_indices(b4, b8, b11, b12) → {clay_index, ferric_ratio, ndvi, ...}`
- [ ] Verify: ObservableVector.x_spec_* fields now populate with actual values
- [ ] Test: Re-run 3 historical scans — verify clay/ferric are no longer 0

### 📋 LATER (Next Sprint)

**Phase AU.3 — Calibration Infrastructure:**
- [ ] Create `threshold_calibrator.py` — derive t1, t2, t3 from ground truths
- [ ] Extend `ground_truth.py` — add CalibrationLineage model
- [ ] Seed ground truth database with 50+ real deposits per commodity
- [ ] Build calibration version manager + ACTIVE version tracking

**Phase AU.4 — Deploy Calibrated Profiles:**
- [ ] Calibrate gold (orogenic + greenstone)
- [ ] Calibrate copper porphyry
- [ ] Calibrate bauxite laterite
- [ ] Update scan_pipeline.py to use calibrated profiles instead of hard-coded thresholds
- [ ] Reprocess 10 historical scans (create new versions with parent_scan_id)
- [ ] Show before/after tier distribution changes

---

## 3. IMMEDIATE ACTION PLAN (Next 2 Days)

### Day 1: Validation Framework Integration

```bash
# 1. Add validation models (DONE ✓)
# 2. Add validator service (DONE ✓)
# 3. Extend CanonicalScan model
   - Add: validation_summary: Optional[ScanValidationSummary] = None

# 4. Update scan_pipeline.py (step 19 — canonical freeze)
   from app.services.scan_validator import validate_scan
   
   validation = validate_scan(
       scan_id=canonical_scan.scan_id,
       commodity=canonical_scan.commodity,
       scan_cells=cell_results,  # from DB query
       observable_vectors=observable_vecs,
       cell_results=acif_results,
       scan_aggregates=acif_aggregates,
   )
   canonical_scan.validation_summary = validation

# 5. Add API endpoint
   @router.get("/scan/{scan_id}/validation")
   async def get_scan_validation(scan_id: str):
       scan = await store.get_canonical_scan(scan_id)
       if not scan.validation_summary:
           return {"status": "not_validated"}
       return scan.validation_summary.dict()
```

### Day 2: Diagnostics & Spectral Index Fix

```bash
# 1. Run diagnostic query
   SELECT COUNT(*) FROM scan_cells 
   WHERE s2_b4 IS NULL OR s2_b8 IS NULL OR s2_b11 IS NULL OR s2_b12 IS NULL;
   
   # If result > 0: bands are present ✓
   # If result = total_cells: bands are MISSING — raise alert

# 2. Find spectral index computation
   grep -r "clay_index\|ferric_ratio" aurora_vnext/app/
   
   # If not found: need to implement

# 3. Implement spectral indices (in normalisation.py or GEE pipeline)
   def compute_spectral_indices(b4, b8, b11, b12):
       clay = (b11 + b4) / (b11 - b4 + 1e-8)
       ferric = b4 / b8 if b8 > 0 else 0
       ndvi = (b8 - b4) / (b8 + b4 + 1e-8)
       return {'clay': clay, 'ferric': ferric, 'ndvi': ndvi}

# 4. Test with one scan
   python3 gee_sensor_pipeline.py test_payload.json
   # Verify: output includes clay_index, ferric_ratio
```

---

## 4. SUCCESS METRICS

### Week 1 (Validation Framework Live)
- [ ] Validation summary appears on all new scans
- [ ] Users see trustworthiness badge (VALID_FOR_RANKING, PARTIAL_MODALITY_SUPPORT, etc.)
- [ ] Alert messages flag suspicious scans (broadcasting, missing spectral data)
- [ ] Zero regression: ACIF scores unchanged (validation is observational only)

### Week 2 (Spectral Indices Working)
- [ ] Clay/ferric observables no longer zero across all cells
- [ ] Observable distribution report shows > 0% coverage for x_spec_*
- [ ] Vector uniqueness > 80% (before was likely < 20% due to uniform zeros)
- [ ] Scans with spectral data show improved evidence scores

### Week 3 (Calibrated Thresholds)
- [ ] Ground truth database seeded with 50+ real deposits per commodity
- [ ] Gold (WAF) calibrated profile deployed (t1=0.68, t2=0.42, t3=0.18)
- [ ] New scans use calibrated thresholds, not hard-coded defaults
- [ ] Before/after comparison shows 15–25% change in tier distribution for test AOIs

---

## 5. DELIVERABLES

**Code (Created Today):**
- ✅ `aurora_vnext/app/models/scan_validation_model.py` (8.2 KB)
- ✅ `aurora_vnext/app/services/scan_validator.py` (20.6 KB)
- ✅ `VALIDATION_CALIBRATION_ARCHITECTURE.md` (20.2 KB)
- ✅ `PHASE_AU_ROOT_CAUSE_AND_ROADMAP.md` (This file)

**Next (To Implement):**
- [ ] `aurora_vnext/app/services/threshold_calibrator.py` — ~3 KB
- [ ] `aurora_vnext/app/models/calibration_lineage_model.py` — ~2 KB
- [ ] Extended ground truth schema + calibration version tracking
- [ ] scan_pipeline.py integration (20 lines)
- [ ] API endpoint (15 lines)
- [ ] Frontend validation badge + alerts (50 lines React)

---

## 6. KNOWN RISKS & MITIGATION

| Risk | Mitigation |
|------|-----------|
| Spectral indices not implemented anywhere | Grep all source + check GEE worker output |
| Raw S2 bands are null in ScanCell | Query DB to verify; if null, fix GEE worker |
| Validation adds latency to freeze | ~200ms — acceptable for one-time compute |
| Ground truth DB is empty or synthetic | Check `ground_truth.py`; seed manually if needed |
| Reprocessing old scans breaks API | Use parent_scan_id versioning; old scans remain immutable |

---

## 7. LONG-TERM VISION

**After Phase AU:**
- Scans are **validated** — users trust tier assignments
- Thresholds are **dynamic** — calibrated per commodity + basin
- Lineage is **tracked** — full reproducibility + audit trail
- Observable computation is **correct** — no more uniform zeros

Aurora becomes a **scientifically defensible** mineral exploration system.

---