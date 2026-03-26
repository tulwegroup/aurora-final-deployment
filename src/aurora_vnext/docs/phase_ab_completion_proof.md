# Phase AB Completion Proof
## Aurora OSI vNext — Intelligent Geological Interpretation & Report Generation

---

## 1. Deliverable Inventory

| File | Category | Purpose |
|---|---|---|
| `app/models/report_model.py` | Model | `GeologicalReport`, `ReportSection`, `CitationRef`, `ReportAuditTrail`, forbidden claim types |
| `app/services/mineral_system_logic.py` | Service | Approved MSL registry: gold, copper, lithium, nickel — deposit models, expected drivers, key observables, uncertainty notes |
| `app/services/report_grounding.py` | Service | `GroundingBundle` assembly, `grounding_snapshot_hash` (SHA-256), `check_for_forbidden_claims()` |
| `app/services/report_templates.py` | Service | Audience-specific prompt templates: sovereign/government, operator/technical, investor/executive |
| `app/services/report_engine.py` | Service | Orchestrator: fetch → ground → LLM × 4 sections → check → assemble → audit |
| `app/api/reports.py` | API | 4 endpoints: generate, list, get, audit trail |
| `functions/generateGeologicalReport.js` | Backend | Calls InvokeLLM with grounded prompt; computes grounding hash client-side |
| `pages/ReportViewer.jsx` | UI | Audience selector, 4-section display with citations, audit trail tab |
| `components/ReportSection.jsx` | UI | Section renderer with citation badges and redaction notices |
| `components/CitationBadge.jsx` | UI | Hoverable canonical field citation with stored_value verbatim |
| `tests/unit/test_report_phase_ab.py` | Tests | 20 tests: model, audit, forbidden claims, grounding hash, MSL registry, no-scoring |
| `docs/phase_ab_completion_proof.md` | Proof | This document |

---

## 2. Report Model Inventory

```
GeologicalReport (frozen)
  ├── report_id
  ├── scan_id                         → binds to exactly one CanonicalScan
  ├── commodity
  ├── audience                        → sovereign_government | operator_technical | investor_executive
  ├── status                          → draft | final | redacted
  ├── summary                         → ≤ 3 sentences for UI card
  ├── sections: ReportSection[4]      → always exactly 4, in mandatory order
  │     ├── observed_canonical_outputs
  │     ├── geological_interpretation
  │     ├── uncertainty_and_limitations
  │     └── recommended_next_steps
  │     Each section carries:
  │       content (str)               → LLM-generated, post-grounding-check
  │       citations: CitationRef[]    → [field_path, stored_value, relevance]
  │       redaction_notes (Optional)  → set if forbidden claims were found and removed
  └── audit: ReportAuditTrail
        ├── report_version            → "1.0.0"
        ├── prompt_version            → "1.0.0"
        ├── grounding_snapshot_hash   → SHA-256 of full grounding bundle
        ├── calibration_version_id    → from CalibrationScanTrace
        ├── mineral_system_logic_version → from MSL registry
        ├── generated_at              → ISO 8601 UTC
        ├── generated_by              → user or service ID
        └── llm_model_hint            → "aurora-interpretation-v1"
```

---

## 3. Report Engine Architecture

```
caller → ReportEngine.generate(scan_id, audience)
         │
         ├─── 1. fetch CanonicalScan from storage (read-only)
         │         NO write to CanonicalScan
         ├─── 2. fetch CalibrationScanTrace
         ├─── 3. fetch approved GT context (optional)
         ├─── 4. look up MineralSystemEntry from registry
         │
         ├─── 5. assemble_grounding_bundle(...)
         │         → GroundingBundle (all values verbatim from storage)
         │         → grounding_snapshot_hash = SHA-256(sorted JSON)
         │
         ├─── 6. For each of 4 mandatory sections:
         │     ├─── build_section_prompt(section_type, audience, bundle_vars)
         │     │         → injects canonical values + MSL + STRICT_PROHIBITION
         │     ├─── LLMCaller.call(prompt, audience)
         │     ├─── check_for_forbidden_claims(raw_output)
         │     │         → redact if violations found
         │     └─── extract_citations(clean_text, bundle)
         │               → [FIELD: path = value] patterns + auto-cite canonical fields
         │
         ├─── 7. build summary (verbatim from bundle.tier_counts + bundle.system_status)
         ├─── 8. assemble GeologicalReport (frozen)
         ├─── 9. assert_audit_complete()   ← HARD GUARD
         └─── 10. save_report(report)
```

---

## 4. Prompt Grounding Rules

### Permitted in prompt
| Category | Examples |
|---|---|
| Canonical scores (verbatim) | `acif_score: 0.7412`, `component_scores: {evidence: 0.7812, ...}` |
| Stored tier counts | `TIER_1: 12, TIER_2: 47, TIER_3: 88` |
| Stored tier thresholds | `TIER_1: 0.75, TIER_2: 0.55` |
| Veto explanations | Verbatim stored strings |
| Approved MSL | Deposit models, expected drivers, key observables, uncertainty note |
| Approved GT context | Provenance summary of approved records only |

### Forbidden in prompt (never injected)
| Category | Reason |
|---|---|
| Raw feature tensor values | `x_spec_7`, `x_grav_1` raw numbers — not interpretable without context |
| Model weights / lambdas | Calibration math internals |
| Instructions to produce new scores | Would create alternate scoring path |
| Instructions to classify deposit type as proven/probable | Unsupported resource claim |

---

## 5. Canonical Field Citation Mechanism

Every interpretive claim in the LLM output is expected to carry a citation:

```
[FIELD: scan.display_acif_score = "0.7412"]
[FIELD: scan.system_status = "PASS_CONFIRMED"]
[FIELD: scan.tier_counts.TIER_1 = "12"]
[FIELD: cell.veto_explanation = "Physics residual exceeds τ_phys"]
```

The `extract_citations()` function parses these from the LLM output using regex pattern:
```
\[FIELD:\s*([^\]=]+?)\s*=\s*"?([^"\]]+)"?\]
```

Auto-citations are added for the top-level canonical fields (ACIF score, system status, all tier counts) regardless of what the LLM produced. This guarantees every report section has at least one citation tracing its content to the canonical record.

---

## 6. No-Rescoring Proof

```
CLAIM: Phase AB does not rescore any canonical scan.

PROOF:
1. ReportEngine.generate() calls:
   - storage.fetch_canonical_scan()  → READ ONLY
   - storage.fetch_calibration_trace() → READ ONLY
   - storage.save_report()  → WRITES to report store ONLY, never to scan store

2. No import from app.core.scoring, app.core.tiering, app.core.gates,
   app.core.uncertainty, app.core.evidence, app.core.causal, app.core.physics,
   app.core.temporal, or app.core.priors in any Phase AB file.
   (Verified by test_report_phase_ab.py::TestNoScientificImports)

3. The LLM is instructed via STRICT_PROHIBITION:
   "Do NOT invent any score, probability, or numeric value not provided above.
    Do NOT reclassify any tier (tier values are stored and final).
    Do NOT derive new thresholds or cutoffs."

4. LLM output passes through check_for_forbidden_claims() BEFORE section construction.
   Any violation is redacted and logged. The report carries redaction_notes.

5. assert_audit_complete() is a hard guard — reports with empty audit fields
   cannot be saved.

CONCLUSION: The report layer is a read-only interpretation surface.
No CanonicalScan, ScanCell, or CalibrationVersion is modified by report generation.
```

---

## 7. Example Grounded Report Output (Gold Scan)

Below is an abbreviated example of what Section 2 (Geological Interpretation) produces for a gold scan with ACIF = 0.7412, system_status = PASS_CONFIRMED, TIER_1 = 12 cells:

```
Section 2: GEOLOGICAL INTERPRETATION

The canonical ACIF score of 0.7412 [FIELD: scan.display_acif_score = "0.7412"]
places this scan in the PASS_CONFIRMED category [FIELD: scan.system_status = "PASS_CONFIRMED"],
consistent with a coherent multi-observable geoscientific signal for gold mineralisation.

The evidence component score of 0.7812 [FIELD: scan.component_scores.evidence = "0.781200"]
suggests moderate to strong spectral and structural signal coherence. This is consistent
with the expected hydrothermal alteration zones and structural corridors described in the
approved Orogenic Gold deposit model (USGS model 36a).

The 12 Tier 1 cells [FIELD: scan.tier_counts.TIER_1 = "12"] represent 4.0% of the 300
total cells processed. Per the approved mineral system logic, this spatial clustering
pattern is consistent with second- or third-order structural splay geometry — a
characteristic setting for orogenic gold mineralisation.

[GROUNDING NOTE: No deposit certainty is claimed. The interpretation above is based solely
on canonical field values and the approved mineral system logic. Known false positives
include laterite profiles producing similar SWIR signatures and barren granitoids.]
```

---

## 8. Forbidden Claim Detection Examples

| Input text | Detected type | Action |
|---|---|---|
| `"probability of finding gold is 0.85"` | `invented_score` | Sentence redacted → `[REDACTED: Invented score not present in canonical record]` |
| `"reclassify these cells as Tier 1"` | `tier_reassignment` | Sentence redacted |
| `"resource of 2.5 million ounces"` | `resource_statement` | Sentence redacted |
| `"proven deposit with strong support"` | `deposit_certainty` | Sentence redacted |
| `"threshold of 0.65 should be applied"` | `threshold_derivation` | Sentence redacted |

---

## Phase AB Complete

1. ✅ Report model inventory — `GeologicalReport`, 4 mandatory sections, `ReportAuditTrail`
2. ✅ Report engine architecture — fetch → ground → LLM × 4 → check → assemble → audit guard
3. ✅ Prompt grounding rules — permitted and forbidden fields documented and enforced
4. ✅ Canonical field citation mechanism — `[FIELD: path = value]` extraction + auto-citation
5. ✅ No-rescoring proof — no `core/*` imports, read-only storage access, hard audit guard
6. ✅ Example grounded report output — gold scan, Section 2, with field citations
7. ✅ 4 approved MSL entries (gold, copper, lithium, nickel) with observables + uncertainty notes
8. ✅ Forbidden claim detection — 7 pattern categories, redaction with notes
9. ✅ 3 audience templates (sovereign/government, operator/technical, investor/executive)
10. ✅ grounding_snapshot_hash — SHA-256 of sorted bundle, deterministic
11. ✅ 20 regression tests
12. ✅ Zero `core/*` imports across all Phase AB files

**Requesting Phase AC approval.**