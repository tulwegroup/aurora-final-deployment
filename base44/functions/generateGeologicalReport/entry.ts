/**
 * generateGeologicalReport — Backend function
 * Phase AB §AB.7
 *
 * Calls InvokeLLM with a grounded prompt assembled from canonical scan data.
 * Returns structured report sections for each of the 4 mandatory section types.
 *
 * CONSTITUTIONAL RULES:
 *   Rule 1: This function reads canonical field values from the request payload.
 *            It never calls any scoring or tiering function.
 *   Rule 2: The grounding bundle (acif_score, tier_counts, component_scores,
 *            veto_explanations, mineral_system_logic) is assembled here verbatim
 *            from the caller-provided payload.
 *   Rule 3: Forbidden claims are listed in the prompt prohibitions.
 *   Rule 4: grounding_snapshot_hash is computed here (SHA-256 of sorted bundle JSON).
 *   Rule 5: User must be authenticated before any report generation.
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const REPORT_ENGINE_VERSION = "1.0.0";
const TEMPLATE_VERSION      = "1.0.0";

const AUDIENCE_FOCUS = {
  sovereign_government: `
AUDIENCE: Sovereign / Government strategic planning.
Focus on strategic mineral significance, regional targeting, uncertainty, and next-stage survey recommendations.
Language: formal, policy-appropriate.`,

  operator_technical: `
AUDIENCE: Operator / Technical team.
Focus on full evidence breakdown, structural context, active vetoes, calibration context, follow-up work program.
Language: technical, reference canonical observable keys.`,

  investor_executive: `
AUDIENCE: Investor / Executive.
Focus on opportunity summary, risk drivers, confidence limits, commercial implications, next-step milestones.
Language: accessible. NEVER use: reserve, resource, JORC, NI 43-101, proven, probable.`,
};

const SECTION_INSTRUCTIONS = [
  {
    type:  "observed_canonical_outputs",
    title: "1. Observed Canonical Outputs",
    instr: "Report verbatim what the canonical scan produced. Include ACIF score, system status, tier distribution, active vetoes, and component score breakdown. Do NOT interpret — only report stored values with [FIELD: path = value] citations.",
  },
  {
    type:  "geological_interpretation",
    title: "2. Geological Interpretation",
    instr: "Interpret canonical outputs using ONLY the approved mineral system logic. Each interpretive statement must be followed by [FIELD: path = value] citing the canonical field. Reference known false positives where appropriate.",
  },
  {
    type:  "uncertainty_and_limitations",
    title: "3. Uncertainty and Limitations",
    instr: "Report uncertainty using stored component scores and the approved uncertainty note. Include sensor coverage gaps, veto-driven uncertainty, and known false positive risks. Do NOT quantify beyond stored component_scores.",
  },
  {
    type:  "recommended_next_steps",
    title: "4. Recommended Next Steps",
    instr: "Based on canonical outputs and approved mineral system logic only, recommend follow-up actions. Do NOT guarantee mineralisation confirmation. Do NOT state resource quantities.",
  },
];

const STRICT_PROHIBITION = `
STRICT PROHIBITIONS — any violation will be redacted:
- Do NOT invent any score, probability, or numeric value not provided above.
- Do NOT reclassify any tier (tier values are stored and final).
- Do NOT derive new thresholds or cutoffs.
- Do NOT state a deposit is confirmed, proven, or probable.
- Do NOT make mineral resource quantity statements (no tonnes, no grade).
- Every interpretive claim MUST include [FIELD: field.path = "stored_value"].
`;

async function computeHash(obj) {
  const sorted = JSON.stringify(obj, Object.keys(obj).sort());
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(sorted),
  );
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user   = await base44.auth.me();
  if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const payload = await req.json();
  const {
    scan_id, audience, commodity,
    acif_score, tier_counts, tier_thresholds, system_status,
    veto_explanations = [], component_scores = {},
    calibration_version_id = "unknown",
    scan_date = "unknown", pipeline_version = "unknown",
    total_cells = 0, cells_above_tier1 = 0,
    mineral_system_logic,     // full MSL entry from client
    ground_truth_context = null,
  } = payload;

  if (!scan_id || !audience || !commodity || !mineral_system_logic) {
    return Response.json({ error: "Missing required fields: scan_id, audience, commodity, mineral_system_logic" }, { status: 422 });
  }

  const audienceFocus = AUDIENCE_FOCUS[audience];
  if (!audienceFocus) {
    return Response.json({ error: `Unknown audience: ${audience}` }, { status: 422 });
  }

  // Assemble grounding bundle for hashing
  const groundingBundle = {
    scan_id, commodity, acif_score, tier_counts, tier_thresholds,
    system_status, veto_explanations, component_scores,
    calibration_version_id, scan_date, pipeline_version,
    total_cells, cells_above_tier1, mineral_system_logic,
    ground_truth_context,
  };

  const groundingHash = await computeHash(groundingBundle);

  const groundingText = `
=== CANONICAL SCAN DATA (READ ONLY — DO NOT MODIFY OR RECOMPUTE) ===
Scan ID:          ${scan_id}
Commodity:        ${commodity}
Scan date:        ${scan_date}
Pipeline version: ${pipeline_version}
Calibration:      ${calibration_version_id}
ACIF score:       ${acif_score ?? "—"}
System status:    ${system_status}
Total cells:      ${total_cells}
Cells Tier 1:     ${cells_above_tier1}
Tier counts:      ${JSON.stringify(tier_counts)}
Component scores: ${JSON.stringify(component_scores)}
Tier thresholds:  ${JSON.stringify(tier_thresholds)}
Vetoes:           ${veto_explanations.join("; ") || "none"}

=== APPROVED MINERAL SYSTEM LOGIC ===
Commodity:     ${mineral_system_logic.commodity} (v${mineral_system_logic.version})
Deposit models: ${mineral_system_logic.deposit_models?.join(", ")}
Expected drivers: ${mineral_system_logic.expected_drivers?.join("; ")}
Structural context: ${mineral_system_logic.structural_context}
Key observables: ${mineral_system_logic.key_observables?.join(", ")}
Geophysical signature: ${mineral_system_logic.geophysical_signature}
Uncertainty note: ${mineral_system_logic.uncertainty_note}
Known false positives: ${mineral_system_logic.known_false_positives?.join("; ")}
${ground_truth_context ? `\n=== APPROVED GROUND TRUTH CONTEXT ===\n${JSON.stringify(ground_truth_context, null, 2)}` : ""}
`;

  // Generate all 4 sections
  const sections = [];
  for (const section of SECTION_INSTRUCTIONS) {
    const prompt = `You are a geological interpretation assistant for Aurora OSI.\n${audienceFocus}\n${groundingText}\n${STRICT_PROHIBITION}\n\n${section.instr}`;
    const result = await base44.integrations.Core.InvokeLLM({ prompt });
    sections.push({
      section_type:    section.type,
      title:           section.title,
      content:         typeof result === "string" ? result : result?.result || String(result),
      redaction_notes: null,
    });
  }

  const summary = `Aurora scan for ${commodity} (${scan_id.slice(0,8)}…) — status: ${system_status}. ACIF: ${acif_score ?? "—"}. ${cells_above_tier1} Tier 1 cells of ${total_cells} total.`;

  return Response.json({
    report_id:  `rpt-${crypto.randomUUID()}`,
    scan_id,
    commodity,
    audience,
    status:     "final",
    summary,
    sections,
    audit: {
      report_version:               REPORT_ENGINE_VERSION,
      prompt_version:               TEMPLATE_VERSION,
      grounding_snapshot_hash:      groundingHash,
      calibration_version_id,
      mineral_system_logic_version: mineral_system_logic.version,
      generated_at:                 new Date().toISOString(),
      generated_by:                 user.email,
      llm_model_hint:               "aurora-interpretation-v1",
    },
  });
});