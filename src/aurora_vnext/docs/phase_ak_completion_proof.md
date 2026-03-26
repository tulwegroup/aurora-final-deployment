# Phase AK Completion Proof — Commercial Packaging & Pricing

**Date:** 2026-03-26  
**Status:** COMPLETE — Awaiting Phase AL Approval  

---

## Constitutional Statements

### 1. Pricing Independence
All prices are computed from:
- **Compute cost driver:** resolution tier (cell count × resolution multiplier × cloud-compute benchmark)
- **Area cost driver:** km² overage beyond included area threshold
- **Value tier:** package multiplier (Sovereign / Operator / Investor)

The following are **NOT** pricing variables:
- ACIF scores or component weights
- Tier 1 / Tier 2 / Tier 3 cell counts or detection rates
- Commodity type or geographic location
- Geological outcomes or scan quality
- Pilot success metrics

### 2. Feedback & Success Criteria Governance
- Pilot success metrics (detection rates, veto compliance) are **evaluation-only**
- No metric may be used as a tuning or threshold adjustment input
- No feedback loop from validation metrics into scoring, tiering, calibration, or reporting logic
- All pilot feedback is advisory — any change must be proposed as an explicit post-pilot recommendation and approved before implementation

---

## 1. Pricing Model Definition

### Per-Scan (Resolution Tier)

| Resolution | Cell Size     | Base Price | Per km² (overage) | Included Area | Turnaround |
|------------|---------------|------------|-------------------|---------------|------------|
| Survey     | ~100 km²/cell | $4,000     | $0.04             | 100,000 km²   | 24h        |
| Coarse     | ~25 km²/cell  | $12,000    | $0.12             | 100,000 km²   | 48h        |
| Medium     | ~5 km²/cell   | $35,000    | $0.35             | 100,000 km²   | 72h        |
| Fine       | ~1 km²/cell   | $95,000    | $0.95             | 100,000 km²   | 5 days     |

### Portfolio / Subscription

| Tier                  | Scope                                      | Price/Month | Annual Saving |
|-----------------------|--------------------------------------------|-------------|---------------|
| Starter               | 1 scan/mo · 50k km² · Medium              | $28,000     | 15%           |
| Professional          | 3 scans/mo · 100k km² · Fine              | $72,000     | 20%           |
| Enterprise / Sovereign | Unlimited · All resolutions · Priority   | Custom      | Custom        |

---

## 2. Package Tier Breakdown

### Sovereign Package (×1.4 package multiplier)
**Audience:** Governments, Geological Survey Authorities, Regulators

Included:
- Canonical scan record (JSON, full provenance)
- GeoJSON + KML map layers (all tiers)
- Digital twin (3D voxel, full depth profile)
- Geological report — sovereign/government edition
- Secure data-room package (30-day TTL)
- Full audit trail (chain-of-custody, geometry hash)
- Calibration version certificate
- Source quality attestation
- Dedicated CSM onboarding session

Not Included:
- Investor-facing executive summary (separate package)

---

### Operator Package (×1.0 base — reference tier)
**Audience:** Exploration companies, geologists, technical teams

Included:
- Canonical scan record (JSON, full provenance)
- GeoJSON + KML map layers (all tiers)
- Digital twin (3D voxel, full depth profile)
- Geological report — operator/technical edition
- Secure data-room package (7-day TTL)
- Audit trail (geometry hash, version lineage)
- API access to canonical outputs
- GIS-compatible exports (shapefile on request)

Not Included:
- Calibration version certificate (available on upgrade)
- Executive summary (Investor package)

---

### Investor Package (×0.3 — report-only scope)
**Audience:** Investment funds, C-suite, due-diligence teams

Included:
- Executive geological report (jargon-free, ≤ 8 pages)
- Exploration Priority Index summary (non-physical metric)
- Risk tier summary (LOW / MEDIUM / HIGH)
- Secure data-room package (48h TTL, single-use option)
- Portfolio comparison table (if multi-scan)
- Watermarked PDF for due-diligence sharing

Not Included:
- Raw canonical JSON (Operator/Sovereign)
- Digital twin (available on upgrade)
- Calibration lineage (available on upgrade)
- Full map layers (summary map only)

---

## 3. Delivery Content Summary

| Deliverable                    | Sovereign | Operator | Investor |
|-------------------------------|-----------|----------|----------|
| Canonical scan JSON            | ✓         | ✓        | ✗        |
| GeoJSON + KML layers           | ✓         | ✓        | Summary  |
| Digital twin (3D voxel)        | ✓         | ✓        | Upgrade  |
| Geological report              | ✓ (govt)  | ✓ (tech) | ✓ (exec) |
| Audit trail / geometry hash    | ✓         | ✓        | ✗        |
| Calibration certificate        | ✓         | Upgrade  | ✗        |
| Secure data-room               | 30d TTL   | 7d TTL   | 48h TTL  |
| API access                     | ✗         | ✓        | ✗        |
| EPI / Risk summary             | ✓         | ✓        | ✓        |
| Watermarked PDF                | ✓         | ✓        | ✓        |

---

## 4. Example Commercial Proposal Structure

```
Aurora OSI vNext — Commercial Proposal
Date: [Proposal Date]  ·  Indicative

Client Type:   Operator Package
Resolution:    Fine (~1 km²/cell)
AOI Area:      25,000 km²
Scans:         1

Cost Breakdown:
  Base scan (fine)                $95,000
  Area overage (0 km²)           $0
  Scan subtotal                   $95,000
  Package fee (×1.0 Operator)    $95,000
  ─────────────────────────────────
  Total (indicative)              $190,000

Included Deliverables:
  ✓ Canonical scan JSON
  ✓ GeoJSON + KML layers
  ✓ Digital twin
  ✓ Geological report (operator edition)
  ✓ Secure data-room (7d TTL)
  ✓ API access

Notes:
  Indicative only. Final pricing upon AOI submission and contract execution.
  Prices exclude VAT/taxes. Annual commitment discounts available.
```

---

## 5. Completion Checklist

| Requirement                              | Status      |
|------------------------------------------|-------------|
| Pricing model definition                 | ✓ DONE      |
| Package tier breakdown (3 tiers)         | ✓ DONE      |
| Delivery content per package             | ✓ DONE      |
| Proof of no scientific coupling          | ✓ CONFIRMED |
| Example commercial proposal structure    | ✓ DONE      |
| Success criteria governance enforced     | ✓ CONFIRMED |
| Feedback governance enforced             | ✓ CONFIRMED |

**Requesting Phase AL approval.**