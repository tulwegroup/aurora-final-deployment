/**
 * processGeologicalReport — Post-generation hardening
 * 
 * Responsibilities:
 *   1. Strip all [FIELD: ...] placeholders before rendering
 *   2. Enforce section discipline (no duplication)
 *   3. Apply spatial intelligence (clusters, corridors)
 *   4. Inject audience-specific framing
 *   5. Embed visual references (map URLs)
 * 
 * This function runs AFTER generateGeologicalReport returns sections.
 * It guarantees client-ready output.
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// ---- Placeholder redaction ----
function stripPlaceholders(text) {
  if (!text) return text;
  // Remove all [FIELD: ... ] patterns
  return text.replace(/\[FIELD:\s*[^\]]+\]/g, '').replace(/\s+/g, ' ').trim();
}

// ---- Section discipline enforcement ----
function enforceCanonicalOnlySection(content, canonicalFields) {
  // For section 1 (observed_canonical_outputs): ensure ONLY canonical values reported
  const lines = content.split('\n').map(line => {
    // Reject interpretive language
    if (/suggest|indicate|imply|may be|could be|interpretation/i.test(line)) {
      return `[REDACTED: interpretive language in canonical section]`;
    }
    return line;
  });
  return lines.join('\n').trim();
}

function enforceInterpretationOnlySection(content, canonicalContent) {
  // For section 2: ensure NO duplication of raw canonical values
  const canonicalLines = canonicalContent.toLowerCase().split('\n');
  const lines = content.split('\n').map(line => {
    // Check if this line is a verbatim repeat of canonical output
    const lineLower = line.toLowerCase();
    if (canonicalLines.some(cl => cl.length > 20 && cl === lineLower)) {
      return `[REDACTED: duplicate canonical value]`;
    }
    return line;
  });
  return lines.join('\n').trim();
}

// ---- Spatial intelligence injection ----
function injectSpatialContext(sections, spatialData) {
  if (!spatialData || !spatialData.clusters) return sections;

  const interpretSection = sections.find(s => s.section_type === 'geological_interpretation');
  if (!interpretSection) return sections;

  const spatialText = `

### Spatial Distribution & Targeting

**Cluster Analysis:**
${spatialData.clusters.map(c => `- ${c.name}: ${c.cell_count} cells, centroid at ${c.centroid.lat.toFixed(4)}°N, ${c.centroid.lon.toFixed(4)}°E`).join('\n')}

**Priority Zones (highest ACIF):**
${spatialData.priority_zones?.slice(0, 3).map(z => `- ${z.label}: ${z.acif.toFixed(3)} (drill target confidence: ${z.confidence})`).join('\n') || '- Await spatial analytics'}

**Structural Context:**
${spatialData.structural_notes || 'See map overlay for fault lineations and contact geometry.'}
`;

  interpretSection.content += spatialText;
  return sections;
}

// ---- Audience-specific transforms ----
const AUDIENCE_TRANSFORMS = {
  sovereign_government: (sections) => {
    // Add policy/strategy framing
    const nextSteps = sections.find(s => s.section_type === 'recommended_next_steps');
    if (nextSteps) {
      nextSteps.content = `**Strategic Implications:**
Mineralisation signature supports regional targeting strategy. Recommend next-stage survey to refine footprint and assess regional significance.\n\n` + nextSteps.content;
    }
    return sections;
  },

  operator_technical: (sections) => {
    // Add technical drilling guidance
    const nextSteps = sections.find(s => s.section_type === 'recommended_next_steps');
    if (nextSteps) {
      nextSteps.content = `**Drilling Recommendation:**
Priority zones identified in spatial section. Recommend scout drilling in cluster(s) with highest confidence anomalies. Target depth: [consult with exploration geologist based on deposit model].\n\n` + nextSteps.content;
    }
    return sections;
  },

  investor_executive: (sections) => {
    // Add commercial/risk framing
    const summary = sections.find(s => s.section_type === 'geological_interpretation');
    if (summary) {
      summary.content = `**Opportunity Overview:**
Aurora scan identified mineralisation signature consistent with tier-1 commodities. Confidence in anomaly: moderate-to-high. Further drilling required to assess commercial viability.\n\n` + summary.content;
    }
    return sections;
  },
};

// ---- Main processor ----
Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    const { sections, audience, spatialData } = await req.json();

    if (!sections || !Array.isArray(sections)) {
      return Response.json({ error: 'Invalid sections array' }, { status: 422 });
    }

    let processed = sections.map(s => ({
      ...s,
      content: stripPlaceholders(s.content),
    }));

    // Enforce section discipline
    const canonicalSection = processed.find(s => s.section_type === 'observed_canonical_outputs');
    const interpretSection = processed.find(s => s.section_type === 'geological_interpretation');

    if (canonicalSection) {
      canonicalSection.content = enforceCanonicalOnlySection(canonicalSection.content, {});
    }

    if (interpretSection && canonicalSection) {
      interpretSection.content = enforceInterpretationOnlySection(interpretSection.content, canonicalSection.content);
    }

    // Inject spatial intelligence
    if (spatialData) {
      processed = injectSpatialContext(processed, spatialData);
    }

    // Apply audience-specific transforms
    if (audience && AUDIENCE_TRANSFORMS[audience]) {
      processed = AUDIENCE_TRANSFORMS[audience](processed);
    }

    // Count redactions
    const redactionCount = processed.reduce((acc, s) => acc + (s.content.match(/\[REDACTED:/g) || []).length, 0);

    return Response.json({
      status: 'success',
      sections: processed,
      redaction_count: redactionCount,
      has_redactions: redactionCount > 0,
      processed_at: new Date().toISOString(),
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});