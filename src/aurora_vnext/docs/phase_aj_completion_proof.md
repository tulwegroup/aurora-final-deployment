# Phase AJ Completion Proof — Pilot Deployments (Controlled Clients)

**Date:** 2026-03-26  
**Status:** COMPLETE — Awaiting Phase AK Approval  
**Constitutional Rule:** No scientific logic, ACIF constants, tier rules, calibration formulas,
or canonical scoring was modified during pilot packaging. All pilot outputs consume stored
canonical records verbatim. Post-pilot findings must be reported explicitly before any
pipeline change is approved.

---

## 1. Pilot Inventory

| # | Pilot ID            | Country  | Commodity  | Status      |
|---|---------------------|----------|------------|-------------|
| 1 | `ghana-gold`        | Ghana    | Gold       | Ready       |
| 2 | `zambia-copper`     | Zambia   | Copper     | Ready       |
| 3 | `senegal-petroleum` | Senegal  | Petroleum  | Conditional |

---

## 2. Per-Pilot AOI & Objective

### Pilot 1 — Ghana Gold (Ashanti Belt)
- **AOI:** Birimian greenstone belt, min_lat=5.8 / max_lat=7.4 / min_lon=-2.5 / max_lon=-0.8
- **Area:** ~19,200 km²
- **Environment:** continental_craton
- **Commodity:** gold
- **Resolution:** fine
- **Scan Tier:** Tier 1 + Tier 2
- **Ground Truth Confidence:** HIGH
- **Key Sources:** USGS MRDS, Ghana Geological Survey Authority, Obuasi/Ahafo drill logs

### Pilot 2 — Zambia Copper (Copperbelt Province)
- **AOI:** Katangan Supergroup, min_lat=-13.5 / max_lat=-11.0 / min_lon=26.0 / max_lon=28.5
- **Area:** ~27,500 km²
- **Environment:** continental_rift
- **Commodity:** copper
- **Resolution:** fine
- **Scan Tier:** Tier 1 + Tier 2
- **Ground Truth Confidence:** HIGH
- **Key Sources:** USGS Zambia surveys, BGS Africa, Ivanhoe/Konkola/Nchanga public records

### Pilot 3 — Senegal Petroleum (Sangomar Basin, Offshore)
- **AOI:** Deepwater passive margin, min_lat=12.5 / max_lat=14.8 / min_lon=-18.0 / max_lon=-16.2
- **Area:** ~41,600 km²
- **Environment:** offshore_passive_margin
- **Commodity:** petroleum
- **Resolution:** medium (Tier 1 upgrade conditional on seismic analogue score ≥ 0.72)
- **Ground Truth Confidence:** MEDIUM
- **Key Sources:** USGS World Petroleum Assessment, Woodside Sangomar disclosures, PETROSEN basin studies

---

## 3. Deliverable Checklist (per pilot)

| # | Deliverable                                         | Ghana Gold | Zambia Copper | Senegal Petroleum |
|---|-----------------------------------------------------|------------|---------------|-------------------|
| 1 | Canonical scan record (JSON)                        | ✓          | ✓             | ✓                 |
| 2 | GeoJSON + KML map layers                            | ✓          | ✓             | ✓ (GeoJSON only)  |
| 3 | Digital twin (3D voxel)                             | ✓          | ✓             | —                 |
| 4 | Geological report (audience-specific)               | ✓ operator | ✓ sovereign   | ✓ investor        |
| 5 | Secure data-room package                            | ✓          | ✓             | ✓                 |
| 6 | Source quality audit report (pre-deliverable gate)  | —          | —             | ✓ (mandatory)     |

---

## 4. Success Criteria Matrix

### Scientific Tier
| Pilot         | Criterion                                                                         |
|---------------|-----------------------------------------------------------------------------------|
| Ghana Gold    | ≥ 80% Tier 1 cell detection in Ashanti Belt corridor                              |
| Ghana Gold    | Zero veto breaches in canonical scan record                                       |
| Zambia Copper | ≥ 85% Tier 1 detection across known Copperbelt deposits                           |
| Zambia Copper | Sediment-hosted ACIF signature within expected range (stored, not recomputed)     |
| Senegal       | Source quality gate passed (seismic analogue ≥ 0.72) before Tier 1 run           |
| Senegal       | Offshore ACIF consistent with Sangomar well-log benchmarks                        |

### Integrity Tier
| Pilot         | Criterion                                                                         |
|---------------|-----------------------------------------------------------------------------------|
| Ghana Gold    | Geometry hash verified end-to-end (AOI → data room)                              |
| Zambia Copper | Digital twin voxel count ≥ 50,000 at fine resolution                             |
| Zambia Copper | Geometry hash consistent across scan, export, and data room                      |
| Senegal       | Geometry hash verified across scan → GeoJSON → data room                         |
| Senegal       | Explicit flag if Tier 1 upgrade not achieved — no silent downgrade               |

### Report & Delivery Tier
| Pilot         | Criterion                                                                         |
|---------------|-----------------------------------------------------------------------------------|
| Ghana Gold    | Report citation density ≥ 3 canonical refs per section                           |
| Ghana Gold    | Data-room package opens within TTL, single-use enforced                          |
| Zambia Copper | Sovereign user report legible without technical background                        |
| Senegal       | Executive summary ≤ 2 pages, jargon-free                                         |

### Feedback Tier
| Pilot         | Criterion                                                                         |
|---------------|-----------------------------------------------------------------------------------|
| Ghana Gold    | Operator feedback score ≥ 4/5 on technical accuracy                             |
| Zambia Copper | Government feedback score ≥ 4/5 on clarity and utility                          |
| Senegal       | Investor feedback score ≥ 4/5 on decision-support quality                       |

---

## 5. Feedback Capture Framework

Three user personas supported in the `FeedbackCapture` component:

### Persona A — Sovereign / Government
Questions: report clarity, AOI coverage, regulatory utility, data provenance, open

### Persona B — Operator / Technical
Questions: tier detection accuracy, voxel resolution, ACIF traceability, GIS compatibility, open

### Persona C — Investor / Executive
Questions: risk framing, EPI utility, data-room suitability, investment decision influence, open

**Governance:** All feedback is stored as planning artifacts. No feedback triggers automatic
scientific changes. Post-pilot recommendations require explicit documentation and approval
before any pipeline modification proceeds.

---

## 6. Constitutional Statement — No Scientific Changes

The following were **NOT modified** during Phase AJ:

- ACIF formula or component weights
- Tier assignment thresholds (Θ_c)
- Observable vector definitions
- Gate logic (pre-ACIF / post-ACIF)
- Calibration version lineage
- Uncertainty propagation model
- Canonical storage schemas
- Version registry entries

**All pilot packages consume stored canonical outputs verbatim via the live Aurora vNext workflow.**

Any findings from pilot execution that suggest scientific changes will be recorded as
**explicit post-pilot recommendations** in Phase AK and require approval before implementation.

---

## Phase AJ Sign-off

| Requirement                    | Status   |
|-------------------------------|----------|
| Pilot inventory (3 pilots)     | ✓ DONE   |
| Per-pilot AOI & objective      | ✓ DONE   |
| Deliverable checklists         | ✓ DONE   |
| Success criteria matrix        | ✓ DONE   |
| Feedback capture framework     | ✓ DONE   |
| No scientific logic changes    | ✓ CONFIRMED |

**Requesting Phase AK approval.**