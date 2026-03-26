# Phase AC Completion Proof
## Aurora OSI vNext — Real-World Calibration Mathematics & Provenance Weighting

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/calibration_math_model.py` | Model | `ProvenanceWeight`, `BayesianPriorUpdate`, `ResidualQuantileThreshold`, `UncertaintyRecalibration`, `CalibrationRunResult` |
| `app/services/calibration_math.py` | Service | All calibration update formulas: geometric mean, Bayesian prior, residual quantile, k_u, λ update |
| `app/services/calibration_executor.py` | Service | End-to-end calibration run: fetch → weight → update → new version → hard guard |
| `app/models/report_model.py` | Updated | Added `msl_id` to `ReportAuditTrail` (MSL traceable per Phase AB constraint) |
| `tests/unit/test_calibration_math_phase_ac.py` | Tests | 20 tests: formulas, bounds, synthetic exclusion, lineage, no-ACIF guard |
| `docs/phase_ac_completion_proof.md` | Proof | This document |

---

## 2. Calibration Parameter Update Logic

### What calibration may update

| Parameter | Field | Formula |
|---|---|---|
| Province prior | `CalibrationParameters.province_prior_updates` | Bayesian Beta-Binomial update |
| Evidence weight | `CalibrationParameters.lambda_1_updates` | Provenance-weighted signal ratio nudge |
| Causal weight | `CalibrationParameters.lambda_2_updates` | Same as λ₁ |
| Physics veto threshold | `CalibrationParameters.tau_physics_updates` | Q₀.₉₅ of confirmed positive residuals |
| Gravity veto threshold | `CalibrationParameters.tau_gravity_updates` | Q₀.₉₅ of confirmed positive residuals |
| Uncertainty factor | `CalibrationParameters.uncertainty_ku_per_commodity` | k_u from overconfidence gap |

### What calibration must NEVER update

| Forbidden | Reason |
|---|---|
| ACIF scores | Would bypass canonical freeze |
| Tier assignments | Tier is stored at scan time — immutable |
| Gate pass/fail | Gate is a scan-time evaluation |
| Historical scan records | Past is immutable |

---

## 3. Provenance Weighting Schema

### Composite weight formula

```
w_gt = (w_s · w_a · w_t · w_g)^(1/4)
```

| Symbol | Field | Meaning |
|---|---|---|
| w_s | `source_confidence` | How reliable is the data source (USGS, national survey, operator)? |
| w_a | `spatial_accuracy` | How precisely located is the ground truth point? |
| w_t | `temporal_relevance` | How recent and applicable is the ground truth? |
| w_g | `geological_context_strength` | How geologically comparable is the GT site to the AOI? |
| w_gt | `composite` | Geometric mean — one weak dimension cannot be masked |

**Geometric mean enforcement:** If any single dimension is 0 (e.g., unknown spatial accuracy), the composite weight is 0.0. The record contributes nothing to calibration. This is the correct behaviour — one-dimensional uncertainty should not be hidden by averaging.

### Bayesian province prior update

```
Π_post(c, r) = (α₀ + Σw_gt⁺) / (α₀ + β₀ + Σw_gt)
```

**Proof of bounds:** α₀ > 0 and β₀ > 0 ensure the denominator is always > numerator, so Π_post ∈ (0, 1). Degenerate results (0 or 1) are impossible given non-zero pseudocounts.

**Example (gold, Yilgarn Craton):**
```
α₀ = 2.0,  β₀ = 2.0
3 confirmed positive GT records:  Σw_gt⁺ = 2.41  (geometric means summed)
5 total GT records:               Σw_gt   = 3.87

Π_post = (2.0 + 2.41) / (2.0 + 2.0 + 3.87) = 4.41 / 7.87 = 0.5603

Interpretation: prior probability of gold occurrence in Yilgarn updated
from prior neutral (0.5) to 0.5603, weighted by GT confidence.
```

---

## 4. Version Lineage

```
CalibrationVersion v1 (ACTIVE)
  ├── version_id:         "cal-v1-abc123"
  ├── parent_version_id:  None  (genesis)
  ├── status:             ACTIVE
  └── applies_to_scans_after: "2026-01-01T00:00:00"

CalibrationExecutor.run() → triggers:

CalibrationVersion v2 (DRAFT → ACTIVE)
  ├── version_id:         "cal-v2-def456"
  ├── parent_version_id:  "cal-v1-abc123"  ← immutable lineage link
  ├── status:             DRAFT (until activated)
  ├── ground_truth_record_ids: ["r1", "r3", "r5", ...]
  ├── calibration_effect_flags: ["province_priors", "veto_thresholds", "lambda_weights"]
  └── rationale: "Provenance-weighted calibration from 5 approved GT records."

On activation:
  ├── v2.applies_to_scans_after = utcnow()  ← future scans only
  ├── v1 → status = SUPERSEDED (never deleted)
  └── Historical scans retain v1 reference via CalibrationScanTrace

CalibrationRunResult:
  ├── new_version_id:    "cal-v2-def456"
  ├── parent_version_id: "cal-v1-abc123"  ← explicit lineage in result
  └── ...
```

**Historical scans are never rescored:** `applies_to_scans_after` is set to `utcnow()` at activation. Scans processed before activation retain their original `CalibrationScanTrace.calibration_version_id`. They are not reprocessed, re-scored, or modified in any way.

---

## 5. No ACIF / Tier Computation Proof

### Formal proof

```
CLAIM: Phase AC performs no ACIF computation, tier assignment, gate evaluation,
       or canonical scan modification.

EVIDENCE:

1. File import analysis:
   - app/models/calibration_math_model.py: zero imports from app.core.*
   - app/services/calibration_math.py:     zero imports from app.core.*
   - app/services/calibration_executor.py: zero imports from app.core.*
   Verified by test_calibration_math_phase_ac.py::TestNoScientificImports

2. CalibrationRunResult.assert_no_acif_fields():
   Checks all field names against {"acif", "tier", "gate", "score", "probability"}.
   Any field containing these terms raises ValueError.
   Called unconditionally in CalibrationExecutor.run() before persisting.

3. Output type analysis:
   - BayesianPriorUpdate.posterior_prior: probability ∈ (0,1) — not ACIF
   - ResidualQuantileThreshold.computed_threshold: a τ value (float) — not ACIF
   - UncertaintyRecalibration.k_u: a scalar factor ≥ 1.0 — not ACIF
   - lambda_updates: {"lambda_1": float, "lambda_2": float} — configuration

4. Storage writes:
   - CalibrationExecutor writes to CalibrationVersion store only
   - No write to: scan store, cell store, twin store, or canonical store

5. Historical scan protection:
   - applies_to_scans_after enforced at version activation
   - CalibrationScanTrace is written at scan freeze time (not at calibration time)
   - Past CalibrationScanTraces are immutable

CONCLUSION: Phase AC is configuration-only.
No ACIF is computed. No tier is assigned. No scan is touched.
```

### Formula summary

| Formula | Result type | Feeds into |
|---|---|---|
| `w_gt = (w_s·w_a·w_t·w_g)^(1/4)` | ProvenanceWeight (float) | All update formulas |
| `Π_post = (α₀+Σw⁺)/(α₀+β₀+Σw)` | Probability ∈ (0,1) | `CalibrationParameters.province_prior_updates` → `core/priors.py` at next scan |
| `τ(c) = Q₀.₉₅(R | confirmed positives)` | Float threshold | `CalibrationParameters.tau_physics_updates` → `core/physics.py` at next scan |
| `U' = 1-(1-U)^k_u` | Modified uncertainty | `CalibrationParameters.uncertainty_ku_per_commodity` → `core/uncertainty.py` at next scan |
| `λ_new = clamp(λ + lr·(ratio-0.5), 0.1, 2.0)` | Float weight | `CalibrationParameters.lambda_1_updates` → `core/scoring.py` at next scan |

**None of these formulas evaluate ACIF. All outputs are configuration scalars fed into existing calibrated parameters for future scans only.**

---

## 6. MSL Traceable in Report Audit Trail (Phase AB Constraint)

Per the Phase AB constraint added at Phase AC approval:

```python
# In ReportAuditTrail (app/models/report_model.py):
msl_id:                      str    # NEW — unique identifier for the MSL entry
mineral_system_logic_version: str   # existing — version string

# In ReportEngine (app/services/report_engine.py):
audit = ReportAuditTrail(
    ...
    msl_id                       = f"msl-{msl.commodity}-{msl.version}",
    mineral_system_logic_version = registry_version(),
    ...
)
```

**MSL immutability guarantee:**
- Each MSL entry carries a `version` string (e.g., "1.0.0").
- Reports store `msl_id` and `mineral_system_logic_version` in `ReportAuditTrail`.
- When the MSL registry is updated, new entries get a new version string.
- Prior reports retain their `msl_id` reference — they are not regenerated.
- A report generated against MSL v1.0.0 cannot be retroactively altered by MSL v1.1.0.

---

## 7. Real-World Ground Truth Source Compliance

| Source type | Permitted | Notes |
|---|---|---|
| USGS MRDS, MAS/MILS | ✅ Yes | Public domain geological survey data |
| National geological surveys (GSA, BGS, GEUS) | ✅ Yes | Approved with provenance record |
| Validated operator records (historical production) | ✅ Yes | `source_type=production_history` |
| Public cadastre / concession records | ✅ Yes | Lawful jurisdiction-specific |
| Synthetic / AI-generated records | ❌ Never | Two-barrier exclusion enforced |
| Unverified crowdsourced data | ❌ Never | No approved pathway |

---

## Phase AC Complete

1. ✅ Calibration parameter update logic — 5 update pathways with explicit formulas
2. ✅ Provenance weighting schema — geometric mean, 4 dimensions, zero-collapse enforcement
3. ✅ Version lineage — `parent_version_id`, `applies_to_scans_after`, historical immutability
4. ✅ No ACIF/tier computation proof — import analysis + `assert_no_acif_fields()` + storage write audit
5. ✅ Synthetic exclusion — two barriers (storage + executor filter)
6. ✅ MSL traceable in ReportAuditTrail — `msl_id` + `mineral_system_logic_version`
7. ✅ 20 regression tests — formulas, bounds, lineage, synthetic exclusion, no-imports
8. ✅ Zero `core/*` imports across all Phase AC files

**Requesting Phase AD approval.**