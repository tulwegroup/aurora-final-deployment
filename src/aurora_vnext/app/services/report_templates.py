"""
Aurora OSI vNext — Report Templates
Phase AB §AB.4

Audience-specific prompt templates for geological report generation.

Three audiences:
  SOVEREIGN_GOVERNMENT — strategic mineral significance, regional targeting,
                          next-stage survey recommendations
  OPERATOR_TECHNICAL   — evidence breakdown, structural context, vetoes,
                          calibration context, follow-up work program
  INVESTOR_EXECUTIVE   — opportunity summary, risk drivers, confidence limits,
                          commercial implications, next-step milestones

CONSTITUTIONAL RULES:
  Rule 1: Every template instructs the model to cite canonical field values
          using the notation [FIELD: field.path = "value"].
  Rule 2: Every template explicitly instructs the model NOT to:
          invent scores, reclassify tiers, derive thresholds, claim deposit
          certainty, or make resource statements.
  Rule 3: Templates are versioned. report_audit.prompt_version records which
          template version was used.
  Rule 4: The grounding bundle fields are injected verbatim — no computation.
"""

from __future__ import annotations

from app.models.report_model import ReportAudience, SectionType

TEMPLATE_VERSION = "1.0.0"


_GROUNDING_INJECTION = """
=== CANONICAL SCAN DATA (READ ONLY — DO NOT MODIFY OR RECOMPUTE) ===
Scan ID:           {scan_id}
Commodity target:  {commodity}
Scan date:         {scan_date}
Pipeline version:  {pipeline_version}
Calibration:       {calibration_version_id}

ACIF score (stored):     {acif_score}
System status (stored):  {system_status}
Total cells:             {total_cells}
Cells above Tier 1:      {cells_above_tier1}

Tier counts (stored — do not reclassify):
{tier_counts_formatted}

Component scores (stored verbatim):
{component_scores_formatted}

Veto explanations (stored verbatim):
{veto_summary_formatted}

Tier thresholds (stored — do not alter):
{tier_thresholds_formatted}

=== APPROVED MINERAL SYSTEM LOGIC (READ ONLY) ===
Commodity:    {msl_commodity}
Version:      {msl_version}
Deposit models: {msl_deposit_models}
Expected drivers: {msl_expected_drivers}
Structural context: {msl_structural_context}
Key observables (canonical): {msl_key_observables}
Geophysical signature: {msl_geophysical_signature}
Uncertainty note: {msl_uncertainty_note}
Known false positives: {msl_known_false_positives}

{ground_truth_block}
"""

_STRICT_PROHIBITION = """
=== STRICT PROHIBITIONS — VIOLATION WILL CAUSE REDACTION ===
You MUST NOT:
- Invent any score, probability, or numeric value not listed above.
- Reclassify any cell's tier (tier values are stored and final).
- Derive new thresholds or cutoffs.
- State that a deposit is confirmed, proven, or probable.
- Make any mineral resource quantity statement (no tonnes, no grade).
- Inflate probability beyond what is stored in commodity_probs.
Every interpretive claim MUST be followed by [FIELD: field.path = "stored_value"]
citing the canonical field that grounds it.
"""

_SECTION_INSTRUCTIONS = {
    SectionType.OBSERVED_CANONICAL_OUTPUTS: """
Write Section 1: OBSERVED CANONICAL OUTPUTS.
Report verbatim what the canonical scan produced. Include:
- ACIF score [FIELD: scan.display_acif_score = "{acif_score}"]
- System status [FIELD: scan.system_status = "{system_status}"]
- Tier distribution (verbatim counts) [FIELD: scan.tier_counts = ...]
- Active veto count and explanations [FIELD: cell.veto_explanation = ...]
- Component score breakdown [FIELD: scan.component_scores = ...]
Do NOT interpret. Only report what is stored.
""",
    SectionType.GEOLOGICAL_INTERPRETATION: """
Write Section 2: GEOLOGICAL INTERPRETATION.
Interpret the canonical outputs using ONLY the approved mineral system logic above.
For each interpretive statement, cite the exact canonical field that grounds it.
Example: "The elevated SWIR spectral response [FIELD: x_spec_7 = "0.8213"] is
consistent with argillic alteration, which is a recognised driver for {commodity}
mineralisation per the {deposit_model} model."
Reference false positives where relevant.
""",
    SectionType.UNCERTAINTY_AND_LIMITATIONS: """
Write Section 3: UNCERTAINTY AND LIMITATIONS.
Report uncertainty using only stored component scores and the approved uncertainty note.
Include:
- Sensor coverage gaps (where components were missing)
- Veto-driven uncertainty
- Known false positive risks from the mineral system logic
- The approved uncertainty note verbatim
Do NOT quantify uncertainty beyond what is in stored component_scores.
""",
    SectionType.RECOMMENDED_NEXT_STEPS: """
Write Section 4: RECOMMENDED NEXT STEPS.
Based on the canonical outputs and approved mineral system logic, recommend follow-up.
Do NOT guarantee that follow-up will confirm mineralisation.
Do NOT state resource quantities.
Base all recommendations on the tier distribution and evidence pattern.
""",
}

_AUDIENCE_FOCUS = {
    ReportAudience.SOVEREIGN_GOVERNMENT: """
AUDIENCE: Sovereign / Government strategic planning.
Focus on:
- Strategic mineral significance at regional scale
- Regional targeting logic and prospectivity ranking
- Uncertainty and survey data quality
- Recommendations for next-stage national survey prioritisation
- Regulatory and licensing context (do not invent specifics)
Language: formal, policy-appropriate. Avoid technical jargon.
""",
    ReportAudience.OPERATOR_TECHNICAL: """
AUDIENCE: Operator / Technical team.
Focus on:
- Full evidence breakdown by observable type
- Structural and lithological context
- Active vetoes and their implications for follow-up
- Calibration version context (which GT data informed thresholds)
- Specific follow-up work program: recommended survey types, drill density,
  geochemical sampling strategy
Language: technical. Use canonical observable keys and component names.
""",
    ReportAudience.INVESTOR_EXECUTIVE: """
AUDIENCE: Investor / Executive summary.
Focus on:
- Opportunity summary (what the scan found, expressed as prospectivity level)
- Key risk drivers (vetoes, low-confidence components)
- Confidence limits (reference stored uncertainty, do NOT invent)
- Commercial implications (comparative prospectivity, NOT resource estimates)
- Next-step milestones and timeline context
Language: accessible, non-technical. Avoid ore reserve language entirely.
Do NOT use terms: "reserve", "resource", "JORC", "NI 43-101", "proven", "probable".
""",
}


def build_section_prompt(
    section_type:  SectionType,
    audience:      ReportAudience,
    bundle_vars:   dict,
) -> str:
    """
    Build the complete prompt for a single report section.
    bundle_vars: pre-formatted values from GroundingBundle.
    """
    grounding = _GROUNDING_INJECTION.format(**bundle_vars)
    audience_focus = _AUDIENCE_FOCUS[audience]
    section_instr  = _SECTION_INSTRUCTIONS[section_type].format(**bundle_vars)

    return (
        "You are a geological interpretation assistant for Aurora OSI.\n"
        "Your role is to interpret frozen canonical scan data for a specific audience.\n\n"
        + audience_focus + "\n"
        + grounding + "\n"
        + _STRICT_PROHIBITION + "\n"
        + section_instr
    )


def format_bundle_vars(bundle) -> dict:
    """
    Convert a GroundingBundle into the string variables needed by templates.
    All values are verbatim from stored canonical fields.
    """
    msl = bundle.mineral_system_logic

    def fmt_dict(d: dict) -> str:
        return "\n".join(f"  {k}: {v}" for k, v in d.items()) if d else "  (none)"

    def fmt_list(lst: list) -> str:
        return "\n".join(f"  - {i}" for i in lst) if lst else "  (none)"

    gt_block = ""
    if bundle.ground_truth_context:
        gt_lines = "\n".join(
            f"  [{r.get('record_id','?')[:8]}] {r.get('geological_data_type','?')} "
            f"source={r.get('source_name','?')} confidence={r.get('confidence_composite','?')}"
            for r in bundle.ground_truth_context
        )
        gt_block = f"=== APPROVED GROUND TRUTH CONTEXT ===\n{gt_lines}"

    return {
        "scan_id":                 bundle.scan_id,
        "commodity":               bundle.commodity,
        "scan_date":               bundle.scan_date,
        "pipeline_version":        bundle.pipeline_version,
        "calibration_version_id":  bundle.calibration_version_id,
        "acif_score":              bundle.acif_score or "—",
        "system_status":           bundle.system_status,
        "total_cells":             str(bundle.total_cells),
        "cells_above_tier1":       str(bundle.cells_above_tier1),
        "tier_counts_formatted":   fmt_dict(bundle.tier_counts),
        "component_scores_formatted": fmt_dict(bundle.component_scores),
        "veto_summary_formatted":  fmt_list(bundle.veto_summary),
        "tier_thresholds_formatted": fmt_dict(bundle.tier_thresholds),
        "msl_commodity":           msl.commodity,
        "msl_version":             msl.version,
        "msl_deposit_models":      ", ".join(msl.deposit_models),
        "msl_expected_drivers":    fmt_list(list(msl.expected_drivers)),
        "msl_structural_context":  msl.structural_context,
        "msl_key_observables":     ", ".join(msl.key_observables),
        "msl_geophysical_signature": msl.geophysical_signature,
        "msl_uncertainty_note":    msl.uncertainty_note,
        "msl_known_false_positives": fmt_list(list(msl.known_false_positives)),
        "ground_truth_block":      gt_block,
        "deposit_model":           msl.deposit_models[0] if msl.deposit_models else commodity,
    }