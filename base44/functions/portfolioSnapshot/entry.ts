/**
 * portfolioSnapshot — Portfolio territory aggregation
 * Phase AD §AD.5
 *
 * Aggregates stored canonical scan outputs into territory-level
 * exploration priority rankings. Returns snapshot with entries,
 * risk summary, weight config, and methodology note.
 *
 * In production this queries the Aurora RDS database via the API.
 * Currently returns a structured stub response so the frontend renders correctly.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json().catch(() => ({}));
    const { commodity, territory_type, risk_adjusted } = body;

    // Stub response — production: query Aurora API /api/v1/portfolio/snapshot
    // The portfolio aggregation router will be mounted in Phase AD when the API
    // routers are uncommented in aurora_vnext/app/main.py
    const entries = [
      {
        entry_id: "ent-001",
        territory_name: "Ghana Ashanti Belt",
        territory_type: "basin",
        commodity: "gold",
        exploration_priority_index: 0.812,
        acif_mean: 0.741,
        tier_1_density: 0.04,
        veto_compliance: 1.0,
        risk_level: "LOW",
        scan_count: 3,
        last_scan_date: "2026-03-15",
        notes: "Strong orogenic gold signatures across multiple scan epochs."
      },
      {
        entry_id: "ent-002",
        territory_name: "Zambia Copperbelt",
        territory_type: "basin",
        commodity: "copper",
        exploration_priority_index: 0.764,
        acif_mean: 0.693,
        tier_1_density: 0.031,
        veto_compliance: 0.95,
        risk_level: "LOW",
        scan_count: 2,
        last_scan_date: "2026-03-10",
        notes: "Classic IOCG signatures confirmed across 2 scan epochs."
      },
      {
        entry_id: "ent-003",
        territory_name: "Senegal Petroleum Block",
        territory_type: "block",
        commodity: "oil",
        exploration_priority_index: 0.631,
        acif_mean: 0.587,
        tier_1_density: 0.018,
        veto_compliance: 0.88,
        risk_level: "MEDIUM",
        scan_count: 1,
        last_scan_date: "2026-02-28",
        notes: "Offshore gravity anomalies consistent with basin inversion."
      },
    ];

    // Apply filters
    let filtered = entries;
    if (commodity) filtered = filtered.filter(e => e.commodity === commodity);
    if (territory_type) filtered = filtered.filter(e => e.territory_type === territory_type);

    // Risk-adjusted sort
    const sorted = filtered.sort((a, b) =>
      risk_adjusted
        ? (b.exploration_priority_index * (b.veto_compliance || 1)) - (a.exploration_priority_index * (a.veto_compliance || 1))
        : b.exploration_priority_index - a.exploration_priority_index
    );

    const riskSummary = {
      LOW:    sorted.filter(e => e.risk_level === "LOW").length,
      MEDIUM: sorted.filter(e => e.risk_level === "MEDIUM").length,
      HIGH:   sorted.filter(e => e.risk_level === "HIGH").length,
    };

    return Response.json({
      entries: sorted,
      total: sorted.length,
      risk_summary: riskSummary,
      weight_config: {
        version_id: "wc-v1.0",
        w_acif_mean: 0.5,
        w_tier1_density: 0.3,
        w_veto_compliance: 0.2,
      },
      methodology_note:
        "Exploration Priority Index = 0.5 × ACIF_mean + 0.3 × Tier1_density_normalised + 0.2 × veto_compliance. " +
        "This is a non-physical aggregation metric. It is not a geological score or resource estimate.",
      generated_at: new Date().toISOString(),
      data_source: "stub — Aurora API portfolio router not yet mounted",
    });

  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});