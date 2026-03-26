# Phase AD Completion Proof
## Aurora OSI vNext — Portfolio & Territory Intelligence

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/portfolio_model.py` | Model | `PortfolioEntry`, `TerritoryBlock`, `ScanContribution`, `PortfolioScore`, `PortfolioRiskProfile`, `PortfolioSnapshot` |
| `app/services/portfolio_aggregation.py` | Service | Aggregation from stored canonical outputs + risk tier classification + portfolio score |
| `app/services/portfolio_ranking.py` | Service | Risk-adjusted ranking, `build_snapshot()`, snapshot hash |
| `app/services/calibration_diversity.py` | Service | GT diversity validator (AC additional constraint): source, spatial, geological |
| `app/api/portfolio.py` | API | 5 endpoints: list, snapshot, risk-summary, get, assemble |
| `pages/PortfolioView.jsx` | UI | Ranked table + territory cards + risk summary + constitutional notice |
| `components/TerritoryCard.jsx` | UI | Territory detail card with score bar + risk notes + contributions |
| `components/PortfolioRankingTable.jsx` | UI | Ranked table with all stored metrics verbatim |
| `tests/unit/test_portfolio_phase_ad.py` | Tests | 20 tests: scoring, risk, ranking, diversity, immutability, no-imports |
| `docs/phase_ad_completion_proof.md` | Proof | This document |

---

## 2. Portfolio Scoring Methodology

### Inputs — all sourced from stored canonical records

| Input | Source field | Role in score |
|---|---|---|
| `acif_mean` | `CanonicalScan.acif_mean` (stored aggregate) | Quality signal |
| `tier1_density` | `tier_1_count / total_cells` (stored counts) | Prospectivity concentration |
| `veto_rate` | `veto_count / total_cells` (stored counts) | Geophysical compliance |

### Formula

```
portfolio_score = (w_acif × acif_mean + w_tier1 × tier1_density + w_risk × (1 − veto_rate))
                / (w_acif + w_tier1 + w_risk)

Where:
  w_acif  = 0.5   (display weight — not part of calibration system)
  w_tier1 = 0.3
  w_risk  = 0.2
  Weights sum to 1.0.
```

**Proof that this is not ACIF recomputation:**
- `acif_mean` is read from the stored `CanonicalScan.acif_mean` field — already aggregated at scan time.
- `tier1_density` is computed from stored `tier_1_count` and `total_cells` — integer arithmetic on stored counts.
- `veto_rate` is computed from stored `veto_count` and `total_cells` — same.
- The formula produces a display composite ∈ [0, 1] — labeled as `portfolio_score` in all outputs.
- No function from `app.core.*` is called.

---

## 3. Aggregation Logic

### Cross-scan aggregation (within territory/commodity)

```
total_cells  = Σ(c.total_cells for c in contributions)
tier1_total  = Σ(c.tier_1_count for c in contributions)
veto_total   = Σ(c.veto_count for c in contributions)

# ACIF mean: weighted by cell count — verbatim stored values, no recomputation
agg_acif = Σ(c.acif_mean × c.total_cells) / Σ(c.total_cells)
           (for contributions with non-null acif_mean)
```

**PROOF: `acif_mean` values are read from stored `CanonicalScan` records only.**
The aggregation is a weighted average of stored values — no scoring function is called.

### Multi-scan coverage proxy

```
coverage_score = count(scans with system_status ∈ {"PASS_CONFIRMED", "PARTIAL_SIGNAL"})
               / total_scan_count
```

This uses the stored `system_status` field — no recomputation.

---

## 4. Risk-Adjusted Ranking Framework

### Risk tier classification

| Tier | Condition (stored metrics only) |
|---|---|
| LOW | veto_rate < 0.05 AND coverage_score > 0.70 AND scan_count ≥ 3 |
| HIGH | veto_rate > 0.30 OR coverage_score < 0.30 OR scan_count < 2 |
| MEDIUM | All other cases |

**PROOF:** All three conditions use stored `veto_count`, `total_cells`, `system_status`, and scan count. No ACIF is evaluated.

### Ranking penalty

```
risk_adjusted_score = portfolio_score - penalty[risk_tier]

penalty = {LOW: 0.00, MEDIUM: 0.05, HIGH: 0.15}
```

Ranking is by `risk_adjusted_score` descending. Original `portfolio_score` is preserved in output — the adjusted score is used for ordering only.

---

## 5. No Scientific Recomputation Proof

```
CLAIM: Phase AD performs no ACIF computation, tier assignment, gate evaluation,
       or canonical scan modification.

EVIDENCE:

1. Import analysis (verified by TestNoScientificImports):
   - app/models/portfolio_model.py:          zero app.core.* imports
   - app/services/portfolio_aggregation.py:  zero app.core.* imports
   - app/services/portfolio_ranking.py:      zero app.core.* imports
   - app/api/portfolio.py:                   zero app.core.* imports
   - app/services/calibration_diversity.py:  zero app.core.* imports

2. Input analysis:
   - ScanContribution.acif_mean — sourced from stored CanonicalScan.acif_mean
   - ScanContribution.tier_1_count — sourced from stored CanonicalScan.tier_counts
   - ScanContribution.veto_count — sourced from stored scan veto count
   - No ScanContribution field is computed at portfolio time

3. Output type analysis:
   - portfolio_score: weighted average of stored values — labeled as display composite
   - portfolio_rank: integer ordinal — not a scientific score
   - risk_tier: LOW/MEDIUM/HIGH — infrastructure classification from veto_rate
   - All outputs carry constitutional note in API response:
     "No ACIF was recomputed. All inputs sourced from stored canonical records."

4. Storage write analysis:
   - Portfolio entries are written to portfolio store only
   - No write to: scan store, cell store, twin store, canonical store, calibration store

CONCLUSION: Phase AD is a read-only aggregation and ranking surface.
No ACIF is computed. No tier is assigned. No scan is touched.
```

---

## 6. Calibration Diversity Constraints (AC Additional Constraint)

Per the Phase AC additional constraints applied at Phase AD approval:

### Three enforced constraints

| Constraint | Minimum | Enforcement |
|---|---|---|
| Unique sources | ≥ 2 distinct `source_name` values | `CalibrationDiversityError` |
| Spatial dispersion | ≥ 0.5° max great-circle spread | `CalibrationDiversityError` |
| Geological type variation | ≥ 2 distinct `geological_data_type` values | `CalibrationDiversityError` |

### Commodity scoping

All constraints are validated per-commodity. A commodity with insufficient diversity cannot proceed to calibration even if another commodity's GT set is diverse. Cross-commodity leakage is prevented:

```python
def assert_gt_diversity(commodity: str, records: list[dict]) -> DiversityReport:
    # Only records for the specific commodity are passed
    # constraints enforced per (commodity, province) scope
```

### Spatial dispersion formula

```
dispersion = max(haversine(p1, p2) for all pairs p1, p2 in records with lat/lon)
           ≈ max_distance_km / 111.0    (degrees approximation)
```

Haversine formula used — geometry only, no scientific computation.

### Lineage compliance

All three AC constraints (immutable, queryable, scan-traceable) remain satisfied:
- `CalibrationVersion` records carry `ground_truth_record_ids` — the exact GT records used
- `CalibrationScanTrace` written at scan freeze — scan-level traceability
- `CalibrationVersion.parent_version_id` — full DAG lineage, never overwritten

---

## 7. Audience Views

| Audience | Portfolio Surface |
|---|---|
| Sovereign / Government | Country-level `TerritoryType.COUNTRY` entries — strategic mineral prospectivity ranking |
| Operator / Technical | Block and concession entries — scan contribution details, veto analysis, calibration version |
| Investor / Executive | Ranked snapshot with risk-adjusted scores — comparative prospectivity only, no resource claims |

**Constitutional language enforcement:** Portfolio UI displays:
- `portfolio_score` as "Portfolio Score (display composite)" — never as "ACIF" or "deposit probability"
- Risk tier as "LOW/MEDIUM/HIGH risk" — not as deposit classification
- Constitutional notice on every portfolio view: "No ACIF was recomputed. This view does not constitute geological resource classification."

---

## Phase AD Complete

1. ✅ Portfolio scoring methodology — weighted composite of 3 stored metrics, formula in §2
2. ✅ Aggregation logic — cross-scan cell-count-weighted ACIF mean, stored tier sums, §3
3. ✅ Risk-adjusted ranking framework — penalty table, risk_tier from veto_rate, §4
4. ✅ No scientific recomputation proof — import audit + input analysis + output type analysis, §5
5. ✅ Calibration diversity constraints — 3 enforced (sources, spatial, geological), §6
6. ✅ Commodity scoping — diversity and calibration parameters indexed by commodity
7. ✅ Calibration lineage — immutable, queryable, scan-traceable (from Phase AC)
8. ✅ Portfolio snapshot — deterministic SHA-256 ID, ranked, frozen
9. ✅ Constitutional UI notices on all portfolio surfaces
10. ✅ 20 regression tests — scoring, risk, ranking, diversity, immutability, no-imports
11. ✅ Zero `core/*` imports across all Phase AD files

**Aurora OSI vNext — Phases Z through AD complete.**

**Roadmap status: Z ✅ AA ✅ AB ✅ AC ✅ AD ✅**