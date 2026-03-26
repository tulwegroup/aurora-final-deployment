# Phase AL Completion Proof — Sovereign & Investor Presentation Layer

**Date:** 2026-03-26  
**Status:** COMPLETE — Awaiting Phase AM Approval  

---

## Phase AK Corrections Applied (Pre-AL)

### 1. Pricing Calculation — Double-Counting Removed
**Old (incorrect):** Total = base_scan + package_fee (two separate line items added)  
**New (correct):** Total = (base_price + overage) × numScans × package_multiplier  

No double-counting. Package multiplier is applied to scan subtotal, not added on top.

### 2. Pricing Model Versioning
- Centralised `lib/pricingModel.js` introduced. Version: `v1.0.0`
- All resolution base prices, per-km² rates, included-area thresholds, and package multipliers sourced from this file
- `PRICING_MODEL_VERSION` and `PRICING_MODEL_DATE` exposed for display in all UI components
- `PACKAGE_MULTIPLIERS.version` records the model version with each multiplier set
- No hard-coded pricing constants remain in UI components

### 3. Pricing Independence Confirmed
Pricing drivers (only):
- Compute cost: resolution → base price
- Area cost: km² overage × per_km2 rate
- Package tier: client type multiplier

Explicitly excluded from pricing:
- ACIF scores or component values
- Tier 1 / 2 / 3 detection counts
- Commodity type or geographic location
- Geological outcomes or scan quality

---

## Phase AL — Presentation Layer

### 1. Sovereign Briefing Pack
6-slide structured briefing for governments, geological surveys, and regulators.

| Slide | Title | Type |
|-------|-------|------|
| 01 | What Aurora OSI Delivers | Overview |
| 02 | The Aurora Workflow | Process |
| 03 | Understanding ACIF Scores | Output Explanation |
| 04 | Pilot Case Summaries | Evidence |
| 05 | Governance, Provenance & Audit | Compliance |
| 06 | What Aurora Does Not Claim | Limitations |

### 2. Investor Pitch Deck
6-slide deck for investment funds, C-suite, and due-diligence teams.

| Slide | Title | Type |
|-------|-------|------|
| 01 | The Exploration Intelligence Gap | Problem |
| 02 | What Aurora Delivers to Investors | Value Proposition |
| 03 | Understanding the Exploration Priority Index (EPI) | Output Explanation |
| 04 | Pilot Results at a Glance | Evidence |
| 05 | From Scan to Deal Room | Process |
| 06 | What Aurora Does Not Claim | Limitations |

### 3. Technical Annex
6-section technical reference for geologists, engineers, and scientists.

| Section | Title |
|---------|-------|
| A1 | ACIF — Aurora Composite Inference Framework |
| A2 | Tier Assignment Logic |
| A3 | Digital Twin — Voxel Architecture |
| A4 | Aurora Workflow — Technical Detail |
| A5 | Pilot Case — Technical Detail |
| A6 | Calibration, Provenance & Data Quality |

---

## Messaging Framework Per Audience

| Element | Sovereign | Investor | Technical |
|---------|-----------|----------|-----------|
| Primary output | ACIF score, Tier count | EPI rank, Risk tier | ACIF formula, uncertainty bounds |
| Workflow emphasis | Governance, audit trail | Speed, deal-room | Pipeline steps, calibration |
| Pilot presentation | Regulatory framing, compliance | EPI summary, risk | Cell counts, veto rates, CI |
| Uncertainty framing | "Probabilistic, not deterministic" | "Screening tool, not resource" | "±σ per cell, CI stated" |
| Resource claims | Prohibited | Prohibited | Prohibited |
| Key limitation | Drilling required before resource claim | No JORC/NI 43-101 basis | Calibration version governs tiers |

---

## Proof of No Scientific Misrepresentation

| Requirement | Status |
|-------------|--------|
| No resource estimates without drilling confirmation | ✓ ENFORCED — explicit disclaimer on all slides |
| ACIF described as dimensionless scoring function, not physical quantity | ✓ ENFORCED — A1, slide 03 sovereign, slide 03 investor |
| EPI described as non-physical aggregation metric | ✓ ENFORCED — investor slide 03, EPI formula note |
| Tier assignment described as calibration-version-locked classification | ✓ ENFORCED — A2, slide 03 sovereign |
| Uncertainty framing on all outputs | ✓ ENFORCED — per-slide limitation notes, A1–A6 uncertainty fields |
| Pilot findings described as exploratory | ✓ ENFORCED — caveat on every pilot card |
| No drill confirmation claimed in any AOI | ✓ ENFORCED — "No drilling confirmation in AOI" on all three pilots |
| Digital twin described as visualisation, not resource model | ✓ ENFORCED — A3 |
| Calibration version stated with all pilot data | ✓ ENFORCED — A5 (gold_v2.1.3, copper_v3.0.1, petroleum_structural_v1.0.0) |

---

## Completion Checklist

| Requirement | Status |
|-------------|--------|
| AK pricing correction (no double-counting) | ✓ DONE |
| AK pricing model versioning | ✓ DONE |
| Sovereign briefing pack (6 slides) | ✓ DONE |
| Investor pitch deck (6 slides) | ✓ DONE |
| Technical annex (6 sections) | ✓ DONE |
| Aurora workflow included in all packs | ✓ DONE |
| Pilot case summaries (Ghana, Zambia, Senegal) | ✓ DONE |
| Limitations and uncertainty framing | ✓ DONE |
| Messaging framework per audience | ✓ DONE |
| No scientific misrepresentation proof | ✓ CONFIRMED |

**Requesting Phase AM approval.**