/**
 * UICoverage — Master UI Coverage Matrix
 * Admin-only internal audit page documenting Aurora phase compliance.
 * Route: /coverage
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, AlertTriangle, XCircle, MinusCircle } from "lucide-react";

const STATUS = {
  IMPLEMENTED:           { label: "Implemented",           color: "bg-emerald-100 text-emerald-800", Icon: CheckCircle },
  PARTIALLY_IMPLEMENTED: { label: "Partial",               color: "bg-blue-100 text-blue-800",       Icon: AlertTriangle },
  BLOCKED:               { label: "Blocked (backend)",      color: "bg-red-100 text-red-800",         Icon: XCircle },
  NOT_APPLICABLE:        { label: "N/A",                    color: "bg-slate-100 text-slate-600",     Icon: MinusCircle },
};

const MATRIX = [
  // ─── Authentication / Session ────────────────────────────────────
  {
    id: "AUTH-01", phase: "P", feature: "Login / session management",
    persona: "All", route: "/login (platform)", component: "Base44 AuthProvider",
    endpoint: "Platform-managed", fields: "token, role, email",
    status: "NOT_APPLICABLE",
    gap: "Handled by Base44 platform — no custom login page needed.",
    action: "None",
  },
  {
    id: "AUTH-02", phase: "P §P.7", feature: "Role-aware sidebar (admin/operator/viewer)",
    persona: "All", route: "/layout", component: "Layout.jsx",
    endpoint: "/auth/me", fields: "role",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "AUTH-03", phase: "P §P.7", feature: "Non-admin redirect on protected pages",
    persona: "Admin", route: "/admin", component: "AdminPanel.jsx",
    endpoint: "/auth/me", fields: "role",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "AUTH-04", phase: "P §P.7", feature: "Logout clears token, redirects to /",
    persona: "All", route: "Layout sidebar", component: "Layout.jsx",
    endpoint: "/auth/logout", fields: "token",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Dashboard ───────────────────────────────────────────────────
  {
    id: "DASH-01", phase: "P", feature: "Active scan queue display",
    persona: "All", route: "/", component: "Dashboard.jsx",
    endpoint: "GET /api/v1/scan/active", fields: "active_scans, total",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "DASH-02", phase: "P", feature: "Quick actions grid (6 tiles)",
    persona: "All", route: "/", component: "Dashboard.jsx",
    endpoint: "None (nav links)", fields: "",
    status: "IMPLEMENTED", gap: "Was defined but not rendered — now rendered.", action: "Fixed",
  },
  {
    id: "DASH-03", phase: "AI", feature: "Ghana Gold demo banner + launch",
    persona: "All", route: "/?demo=ghana-gold → /workflow?demo=ghana-gold", component: "Dashboard.jsx",
    endpoint: "None (demo mode)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Workflow / AOI ──────────────────────────────────────────────
  {
    id: "WF-01", phase: "AI §AI.2", feature: "Step 1 AOI — bounding box / KML / GeoJSON / map draw",
    persona: "Operator, Admin", route: "/workflow", component: "AOIStep → MapDrawTool",
    endpoint: "POST /api/v1/aoi/validate", fields: "geometry, valid, area_km2, errors",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-02", phase: "AI §AI.2", feature: "AOI save + geometry hash",
    persona: "Operator, Admin", route: "/workflow", component: "AOIStep",
    endpoint: "POST /api/v1/aoi/save", fields: "aoi_id, geometry_hash, area_km2",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-03", phase: "AI §AI.3", feature: "Step 2 — full mineral commodity selector (21 minerals, grouped)",
    persona: "Operator, Admin", route: "/workflow", component: "ScanParamsStep",
    endpoint: "None (UI selection)", fields: "commodity",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-04", phase: "AI §AI.3", feature: "Step 2 — resolution tiers (3 options) + cost estimate",
    persona: "Operator, Admin", route: "/workflow", component: "ScanParamsStep",
    endpoint: "POST /api/v1/scan/cost-estimate", fields: "estimated_cells, cost_per_km2_usd, cost_tier",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-05", phase: "AI §AI.3", feature: "Scan submission → scan_id returned",
    persona: "Operator, Admin", route: "/workflow", component: "ScanParamsStep",
    endpoint: "POST /api/v1/scan/submit", fields: "scan_id, aoi_id, commodity, resolution",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-06", phase: "AI §AI.4", feature: "Step 3 — real-time scan status polling (4s)",
    persona: "Operator, Admin", route: "/workflow", component: "ScanResultsView",
    endpoint: "GET /api/v1/scan/{scan_id}/status", fields: "status, system_status, acif_mean, tier_counts",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-07", phase: "AI §AI.4", feature: "Step 3 — completed summary (tier counts, veto counts, total cells)",
    persona: "Operator, Admin", route: "/workflow", component: "ScanResultsView",
    endpoint: "GET /api/v1/scan/{scan_id}/status", fields: "tier_counts, veto_count, total_cells",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-08", phase: "AI §AI.4", feature: "Step 3 — links to Dataset, Map Export, Digital Twin, Report",
    persona: "Operator, Admin", route: "/workflow", component: "ScanResultsView (Tabs)",
    endpoint: "Nav links", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "WF-09", phase: "AH", feature: "Step 4 — Data Room export package creation",
    persona: "Operator, Admin", route: "/workflow", component: "ExportStep",
    endpoint: "buildDataRoom, revokeDeliveryLink backend functions", fields: "package_id, access_url, package_hash",
    status: "BLOCKED",
    gap: "ExportStep now renders explicit red banner explaining backend dependency. Demo mode (Ghana Gold) works fully. Live mode shows unavailable state. No dead-end button.",
    action: "Deploy buildDataRoom and revokeDeliveryLink backend functions",
  },
  {
    id: "WF-10", phase: "AI", feature: "Demo mode — Ghana Gold end-to-end (no backend)",
    persona: "All", route: "/workflow?demo=ghana-gold", component: "ClientWorkflow (demoMode prop)",
    endpoint: "None (pre-baked demoData.js)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Map Draw / AOI ──────────────────────────────────────────────
  {
    id: "MAP-01", phase: "AA §AA.10", feature: "Leaflet map — rectangle draw by drag",
    persona: "Operator, Admin", route: "/workflow, /map-builder", component: "MapDrawTool",
    endpoint: "None (client-side)", fields: "GeoJSON polygon geometry",
    status: "IMPLEMENTED", gap: "Replaced broken Google Maps dependency with Leaflet (OpenStreetMap).", action: "Done",
  },
  {
    id: "MAP-02", phase: "AA §AA.10", feature: "KML/GeoJSON file upload",
    persona: "Operator, Admin", route: "/workflow, /map-builder", component: "MapDrawTool",
    endpoint: "None (client-side parse)", fields: "GeoJSON polygon geometry",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "MAP-03", phase: "AA §AA.10", feature: "Bounding box coordinate entry",
    persona: "Operator, Admin", route: "/workflow, /map-builder", component: "MapDrawTool",
    endpoint: "None (client-side)", fields: "minLat, maxLat, minLon, maxLon",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "MAP-04", phase: "AA §AA.9", feature: "Map Builder full workflow (validate, save, preview, submit)",
    persona: "Operator, Admin", route: "/map-builder", component: "MapScanBuilder",
    endpoint: "aoiValidate, aoiSave, aoiEstimate, aoiSubmitScan backend functions", fields: "aoi_id, geometry_hash",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Map Export ──────────────────────────────────────────────────
  {
    id: "EXP-01", phase: "AA", feature: "Export KML/KMZ/GeoJSON from scan layers",
    persona: "All", route: "/map-export/:scanId", component: "MapExport",
    endpoint: "mapExport backend function", fields: "format, layers, geometry_hash",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Scan History ────────────────────────────────────────────────
  {
    id: "HIST-01", phase: "P §P.3", feature: "Paginated scan history list",
    persona: "All", route: "/history", component: "ScanHistory",
    endpoint: "GET /api/v1/history", fields: "scans, total, total_pages, display_acif_score, system_status",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "HIST-02", phase: "P §P.3", feature: "Commodity filter / search",
    persona: "All", route: "/history", component: "ScanHistory",
    endpoint: "GET /api/v1/history?commodity=", fields: "commodity",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "HIST-03", phase: "P §P.4", feature: "Scan detail — full canonical record view",
    persona: "All", route: "/history/:scanId", component: "ScanDetail",
    endpoint: "GET /api/v1/history/{id}", fields: "All CanonicalScan fields",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "HIST-04", phase: "P §P.4", feature: "Scan detail — reprocess lineage (parent_scan_id)",
    persona: "All", route: "/history/:scanId", component: "ScanDetail",
    endpoint: "GET /api/v1/history/{id}", fields: "parent_scan_id, reprocess_reason",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "HIST-05", phase: "P §P.4", feature: "Scan detail — calibration_version_id, pipeline_version provenance",
    persona: "All", route: "/history/:scanId", component: "ScanDetail",
    endpoint: "GET /api/v1/history/{id}", fields: "calibration_version_id, pipeline_version, model_commit_sha",
    status: "IMPLEMENTED", gap: "Was missing provenance card — now added.", action: "Fixed",
  },
  {
    id: "HIST-06", phase: "P §P.4", feature: "Admin reprocess trigger with mandatory reason",
    persona: "Admin", route: "/history/:scanId", component: "ScanDetail",
    endpoint: "reprocessScan backend function", fields: "scan_id, reason",
    status: "IMPLEMENTED", gap: "Added admin reprocess modal.", action: "Done",
  },

  // ─── Dataset View ────────────────────────────────────────────────
  {
    id: "DS-01", phase: "P §P.5", feature: "Dataset summary (ACIF mean/max/weighted, tier distribution, veto counts)",
    persona: "All", route: "/datasets/:scanId", component: "DatasetView",
    endpoint: "GET /api/v1/datasets/summary/{id}", fields: "display_acif_score, tier_counts, veto_counts",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "DS-02", phase: "P §P.5", feature: "Per-cell paginated table (cell_id, lat, lon, ACIF, tier, all component scores)",
    persona: "All", route: "/datasets/:scanId", component: "DatasetView",
    endpoint: "GET /api/v1/history/{id}/cells", fields: "cell_id, lat_center, lon_center, acif_score, tier, evidence_score, causal_score, physics_score, temporal_score, uncertainty",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Digital Twin ────────────────────────────────────────────────
  {
    id: "TWIN-01", phase: "N", feature: "3D voxel renderer (Three.js)",
    persona: "All", route: "/twin/:scanId", component: "TwinView + VoxelRenderer",
    endpoint: "GET /api/v1/twin/{id}", fields: "voxel data batches",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "TWIN-02", phase: "N", feature: "Version selection + snapshot export",
    persona: "All", route: "/twin/:scanId", component: "TwinView",
    endpoint: "GET /api/v1/twin/{id}/versions", fields: "version_id, committed_at",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "TWIN-03", phase: "N", feature: "Decimation controls + memory management",
    persona: "All", route: "/twin/:scanId", component: "TwinView + VoxelControls",
    endpoint: "None (client-side)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Reports ─────────────────────────────────────────────────────
  {
    id: "REP-01", phase: "AB §AB.10", feature: "Audience selector (sovereign / operator / investor)",
    persona: "All", route: "/reports/:scanId", component: "ReportViewer",
    endpoint: "generateGeologicalReport backend function", fields: "audience",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "REP-02", phase: "AB §AB.10", feature: "10-mineral commodity selector with MSL stubs",
    persona: "All", route: "/reports/:scanId", component: "ReportViewer",
    endpoint: "generateGeologicalReport backend function", fields: "commodity, mineral_system_logic",
    status: "IMPLEMENTED", gap: "Expanded from 2 to 10 MSL stubs (gold, silver, copper, nickel, lithium, cobalt, iron, uranium, diamonds, pgm).", action: "Done",
  },
  {
    id: "REP-03", phase: "AB §AB.10", feature: "Report sections (4 types) with citations",
    persona: "All", route: "/reports/:scanId", component: "ReportViewer + ReportSection",
    endpoint: "generateGeologicalReport backend function", fields: "sections[].section_type, citations",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "REP-04", phase: "AB §AB.10", feature: "Audit trail (report_id, prompt_version, grounding_snapshot_hash, generated_at)",
    persona: "All", route: "/reports/:scanId", component: "ReportViewer",
    endpoint: "generateGeologicalReport backend function", fields: "audit.*",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "REP-05", phase: "AB §AB.10", feature: "Print / export report",
    persona: "All", route: "/reports/:scanId", component: "ReportViewer",
    endpoint: "None (window.print)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "REP-06", phase: "AB", feature: "Redaction indicator (has_redactions)",
    persona: "Sovereign", route: "/reports/:scanId", component: "ReportViewer",
    endpoint: "generateGeologicalReport", fields: "has_redactions",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Ground Truth Admin ──────────────────────────────────────────
  {
    id: "GT-01", phase: "Z §Z.4", feature: "Ground truth record list (pending / approved / rejected tabs)",
    persona: "Admin, Operator", route: "/ground-truth", component: "GroundTruthAdmin",
    endpoint: "GET /api/v1/ground-truth/records", fields: "record_id, status, commodity, source_type",
    status: "BLOCKED",
    gap: "Aurora API Phase Z ground-truth routers not mounted in main.py. UI renders APIOffline banner + empty tabs. No silent failure.",
    action: "Mount ground_truth_admin.py router in Aurora main.py and redeploy API",
  },
  {
    id: "GT-02", phase: "Z §Z.4", feature: "Approve / reject with mandatory reason",
    persona: "Admin", route: "/ground-truth", component: "GroundTruthAdmin",
    endpoint: "POST /api/v1/ground-truth/approve, /reject", fields: "record_id, reason",
    status: "BLOCKED",
    gap: "Action buttons replaced with explicit 'Actions Unavailable' card explaining required backend action. No dead-end alert().",
    action: "Same as GT-01",
  },
  {
    id: "GT-03", phase: "Z §Z.4", feature: "Calibration version lineage view",
    persona: "Admin", route: "/ground-truth", component: "GroundTruthAdmin",
    endpoint: "GET /api/v1/ground-truth/versions", fields: "version_id, parent_version_id, calibration_effect_flags",
    status: "BLOCKED", gap: "Tab renders empty state. APIOffline banner shown at page top.", action: "Same as GT-01",
  },
  {
    id: "GT-04", phase: "Z §Z.4", feature: "Provenance detail panel",
    persona: "Admin, Operator", route: "/ground-truth", component: "ProvenancePanel",
    endpoint: "GET /api/v1/ground-truth/records/{id}", fields: "source_doc_ref, confidence, methodology",
    status: "BLOCKED", gap: "Panel shows 'Select a record' placeholder until records load.", action: "Same as GT-01",
  },
  {
    id: "GT-05", phase: "Z §Z.4", feature: "Ground truth audit log",
    persona: "Admin", route: "/ground-truth", component: "GroundTruthAdmin",
    endpoint: "GET /api/v1/ground-truth/audit", fields: "actor_id, action, occurred_at, from_status, to_status, reason",
    status: "BLOCKED", gap: "Audit tab renders empty table with 'No audit entries yet' message. No silent failure.", action: "Same as GT-01",
  },

  // ─── Portfolio ───────────────────────────────────────────────────
  {
    id: "PORT-01", phase: "AD", feature: "Portfolio snapshot (territories, EPI, risk tier)",
    persona: "All", route: "/portfolio", component: "PortfolioView",
    endpoint: "portfolioSnapshot backend function", fields: "territories, epi, risk_tier",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "PORT-02", phase: "AD", feature: "Commodity / territory / risk filters",
    persona: "All", route: "/portfolio", component: "PortfolioView",
    endpoint: "portfolioSnapshot backend function", fields: "commodity, territory, risk_adjustment",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "PORT-03", phase: "AD", feature: "Territory ranking table + territory cards",
    persona: "All", route: "/portfolio", component: "PortfolioRankingTable + TerritoryCard",
    endpoint: "portfolioSnapshot backend function", fields: "territories[].territory_id, epi, risk_tier",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Data Room ───────────────────────────────────────────────────
  {
    id: "DR-01", phase: "AH §AH.6", feature: "Package list (active / expired / revoked) with hashes",
    persona: "All", route: "/data-room", component: "DataRoom",
    endpoint: "dataRoomList backend function", fields: "packages[], package_hash, status, expires_at",
    status: "BLOCKED",
    gap: "UI shows explicit red 'Backend unavailable' banner at top + APIOffline component on list load failure. No silent failure.",
    action: "Deploy dataRoomList backend function wired to Aurora /api/v1/data-room/packages GET",
  },
  {
    id: "DR-02", phase: "AH §AH.6", feature: "Package creation (scan_id, audience, TTL, single-use, watermark)",
    persona: "Operator, Admin", route: "/data-room", component: "DataRoom → CreatePackageForm",
    endpoint: "dataRoomCreate backend function", fields: "scan_id, audience, ttl_seconds, single_use, watermarked",
    status: "BLOCKED",
    gap: "Create form renders but submission fails with APIOffline component. Red banner explains dependency. No silent failure.",
    action: "Deploy dataRoomCreate backend function",
  },
  {
    id: "DR-03", phase: "AH §AH.6", feature: "Copy access link / open package",
    persona: "Operator, Admin", route: "/data-room", component: "DataRoom → PackageRow",
    endpoint: "None (UI action on access_url)", fields: "access_url",
    status: "BLOCKED", gap: "Copy/Open buttons only render when access_url is present in API response — which requires DR-02.", action: "Deploy dataRoomCreate",
  },
  {
    id: "DR-04", phase: "AH §AH.6", feature: "Revoke package",
    persona: "Operator, Admin", route: "/data-room", component: "DataRoom",
    endpoint: "dataRoomRevoke backend function", fields: "package_id",
    status: "BLOCKED",
    gap: "Revoke button conditionally rendered only for active packages. Failure caught with alert(). Red banner explains dependency.",
    action: "Deploy dataRoomRevoke backend function",
  },
  {
    id: "DR-05", phase: "AH §AH.6", feature: "Single-use + watermark flag display",
    persona: "All", route: "/data-room", component: "PackageRow",
    endpoint: "dataRoomList", fields: "single_use, watermarked",
    status: "BLOCKED", gap: "Badges only render when package data is returned by API. Depends on DR-01.", action: "Deploy dataRoomList",
  },

  // ─── Admin ───────────────────────────────────────────────────────
  {
    id: "ADM-01", phase: "P §P.7", feature: "User list with roles",
    persona: "Admin", route: "/admin", component: "AdminPanel",
    endpoint: "GET /api/v1/admin/users", fields: "users[], user_id, email, full_name, role",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "ADM-02", phase: "P §P.7", feature: "Role change with mandatory audit reason",
    persona: "Admin", route: "/admin", component: "AdminPanel",
    endpoint: "PUT /api/v1/admin/users/{id}/role", fields: "new_role, reason",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "ADM-03", phase: "P §P.7", feature: "Audit log — append-only, paginated",
    persona: "Admin", route: "/admin", component: "AdminPanel",
    endpoint: "GET /api/v1/admin/audit", fields: "events[], event_type, actor_email, actor_role, scan_id, timestamp",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Sovereign / Investor Presentation ──────────────────────────
  {
    id: "PRES-01", phase: "Presentation", feature: "Investor pitch deck, technical annex, sovereign briefing",
    persona: "Investor, Sovereign", route: "/presentation", component: "PresentationLayer",
    endpoint: "None (static presentation)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Commercial / Pilots ─────────────────────────────────────────
  {
    id: "COM-01", phase: "Commercial", feature: "Package tiers, pricing table, proposal builder",
    persona: "Admin", route: "/commercial", component: "CommercialPackaging",
    endpoint: "None (static + proposal builder)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },
  {
    id: "PIL-01", phase: "Pilot", feature: "Pilot dashboard — feedback capture, pilot cards",
    persona: "Admin", route: "/pilots", component: "PilotDashboard",
    endpoint: "None (static pilot management)", fields: "",
    status: "IMPLEMENTED", gap: "", action: "",
  },

  // ─── Constitutional Compliance ───────────────────────────────────
  {
    id: "CONST-01", phase: "ALL", feature: "Zero scientific recomputation in frontend",
    persona: "N/A", route: "All", component: "All pages",
    endpoint: "N/A", fields: "N/A",
    status: "IMPLEMENTED",
    gap: "Verified: no ACIF formula, no tier arithmetic, no threshold comparison in any page or component. All values sourced verbatim from API fields.",
    action: "Ongoing compliance",
  },
];

const STATUS_FILTER_OPTIONS = ["ALL", "IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "BLOCKED", "NOT_APPLICABLE"];

const BLOCKED_ITEMS = MATRIX.filter(m => m.status === "BLOCKED");
const IMPLEMENTED_ITEMS = MATRIX.filter(m => m.status === "IMPLEMENTED");
const PARTIAL_ITEMS = MATRIX.filter(m => m.status === "PARTIALLY_IMPLEMENTED");

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.NOT_APPLICABLE;
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-medium ${s.color}`}>
      <s.Icon className="w-3 h-3" />
      {s.label}
    </span>
  );
}

export default function UICoverage() {
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");

  const filtered = MATRIX.filter(m => {
    if (filter !== "ALL" && m.status !== filter) return false;
    if (search && !`${m.feature} ${m.id} ${m.phase}`.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">UI Coverage Matrix</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Master compliance audit against all approved Aurora OSI phases.
          {" "}{IMPLEMENTED_ITEMS.length} implemented · {PARTIAL_ITEMS.length} partial · {BLOCKED_ITEMS.length} backend-blocked.
        </p>
        <div className="inline-flex items-center gap-2 mt-2 px-3 py-1.5 rounded border border-amber-300 bg-amber-50 text-amber-900 text-xs font-medium">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
          UI STATUS: <strong>COMPLETE EXCEPT BACKEND-BLOCKED ITEMS</strong>
          {" — "}{BLOCKED_ITEMS.length} features have production-safe unavailable states but require backend deployment to activate.
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Implemented", count: IMPLEMENTED_ITEMS.length, color: "text-emerald-700 bg-emerald-50 border-emerald-200" },
          { label: "Partial", count: PARTIAL_ITEMS.length, color: "text-blue-700 bg-blue-50 border-blue-200" },
          { label: "Backend-Blocked", count: BLOCKED_ITEMS.length, color: "text-red-700 bg-red-50 border-red-200" },
          { label: "Total Features", count: MATRIX.length, color: "text-slate-700 bg-slate-50 border-slate-200" },
        ].map(({ label, count, color }) => (
          <Card key={label} className={`border ${color.split(" ")[2]}`}>
            <CardContent className={`py-3 px-4 ${color}`}>
              <div className="text-2xl font-bold tabular-nums">{count}</div>
              <div className="text-xs mt-0.5">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="matrix">
        <TabsList>
          <TabsTrigger value="matrix">Full Matrix ({MATRIX.length})</TabsTrigger>
          <TabsTrigger value="blocked">Blocked ({BLOCKED_ITEMS.length})</TabsTrigger>
          <TabsTrigger value="routes">Routes</TabsTrigger>
          <TabsTrigger value="blocked">Blocked ({BLOCKED_ITEMS.length})</TabsTrigger>
        <TabsTrigger value="routes">Routes</TabsTrigger>
        <TabsTrigger value="constitutional">Constitutional Proof</TabsTrigger>
        </TabsList>

        {/* Full matrix */}
        <TabsContent value="matrix" className="mt-4 space-y-3">
          <div className="flex gap-3 flex-wrap items-center">
            <input
              type="text"
              placeholder="Search features…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm w-56"
            />
            <div className="flex gap-1 flex-wrap">
              {STATUS_FILTER_OPTIONS.map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`px-2.5 py-1 rounded border text-xs transition-colors ${
                    filter === f ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"
                  }`}>
                  {f === "ALL" ? "All" : STATUS[f]?.label || f}
                </button>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">{filtered.length} rows</span>
          </div>

          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      {["ID", "Phase", "Feature", "Route / Component", "Endpoint", "Status", "Gap / Action"].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(m => (
                      <tr key={m.id} className="border-b hover:bg-muted/20 align-top">
                        <td className="px-3 py-2 font-mono font-medium text-primary whitespace-nowrap">{m.id}</td>
                        <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">{m.phase}</td>
                        <td className="px-3 py-2 font-medium max-w-[180px]">{m.feature}</td>
                        <td className="px-3 py-2 text-muted-foreground max-w-[200px]">
                          <div className="font-mono text-[10px]">{m.route}</div>
                          <div className="text-[10px] text-muted-foreground/70">{m.component}</div>
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground max-w-[160px]">{m.endpoint}</td>
                        <td className="px-3 py-2 whitespace-nowrap"><StatusBadge status={m.status} /></td>
                        <td className="px-3 py-2 max-w-[200px]">
                          {m.gap && <div className="text-muted-foreground">{m.gap}</div>}
                          {m.action && m.action !== "None" && m.action !== "" && (
                            <div className="text-primary font-medium mt-0.5">→ {m.action}</div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Blocked items */}
        <TabsContent value="blocked" className="mt-4 space-y-3">
          <div className="text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded px-4 py-2">
            The following {BLOCKED_ITEMS.length} features cannot be implemented until their backend dependencies are resolved.
          </div>
          {BLOCKED_ITEMS.map(m => (
            <Card key={m.id} className="border-red-200">
              <CardContent className="py-3 px-4 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs text-muted-foreground">{m.id}</span>
                    {" · "}
                    <span className="font-medium text-sm">{m.feature}</span>
                  </div>
                  <StatusBadge status={m.status} />
                </div>
                <div className="text-xs text-muted-foreground">Phase: {m.phase}</div>
                <div className="text-xs text-red-700">{m.gap}</div>
                <div className="text-xs font-medium text-red-900">Required action: {m.action}</div>
                <div className="text-[10px] font-mono text-muted-foreground">Endpoint: {m.endpoint}</div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        {/* Route inventory */}
        <TabsContent value="routes" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    {["Route", "Page Component", "Role Access", "States", "Backend"].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left font-semibold text-muted-foreground text-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { route: "/",                  page: "Dashboard",         roles: "All",            states: "Loading, Error (APIOffline), Empty, Active scans",              backend: "GET /scan/active" },
                    { route: "/workflow",           page: "ClientWorkflow",    roles: "Admin, Operator", states: "4-step wizard, demo mode, loading, error",                   backend: "aoi/*, scan/submit, scan/status, dataRoomCreate" },
                    { route: "/history",            page: "ScanHistory",       roles: "All",            states: "Loading, Error, Empty, Paginated list, Search filter",         backend: "GET /history" },
                    { route: "/history/:scanId",    page: "ScanDetail",        roles: "All",            states: "Loading, Error, Full canonical record, Reprocess modal (admin)",backend: "GET /history/{id}" },
                    { route: "/datasets/:scanId",   page: "DatasetView",       roles: "All",            states: "Loading, Error, Summary cards, Paginated cell table",           backend: "GET /datasets/summary/{id}, /cells" },
                    { route: "/twin/:scanId",       page: "TwinView",          roles: "All",            states: "Loading, Error, 3D viewer, version history, snapshot export",  backend: "GET /twin/{id}" },
                    { route: "/reports/:scanId",    page: "ReportViewer",      roles: "All",            states: "Config panel, Loading (LLM), Error, Report sections, Audit",   backend: "generateGeologicalReport function" },
                    { route: "/reports",            page: "ReportViewer",      roles: "All",            states: "Same as above (demo scan ID used)",                             backend: "generateGeologicalReport function" },
                    { route: "/portfolio",          page: "PortfolioView",     roles: "All",            states: "Loading, Error, Filters, Summary, Territory ranking/cards",    backend: "portfolioSnapshot function" },
                    { route: "/data-room",          page: "DataRoom",          roles: "All",            states: "Loading, Error (APIOffline), Packages list, Create form",       backend: "dataRoomList, dataRoomCreate, dataRoomRevoke (BLOCKED)" },
                    { route: "/map-builder",        page: "MapScanBuilder",    roles: "Admin, Operator", states: "4-step: Draw → Validate → Preview → Submit",                 backend: "aoiValidate, aoiSave, aoiEstimate, aoiSubmitScan" },
                    { route: "/map-export/:scanId", page: "MapExport",         roles: "All",            states: "Layer select, Format select, Export, Hash verification",       backend: "mapExport function" },
                    { route: "/map-export",         page: "MapExport",         roles: "All",            states: "Same (no pre-selected scan)",                                   backend: "mapExport function" },
                    { route: "/ground-truth",       page: "GroundTruthAdmin",  roles: "Admin, Operator", states: "Loading, Error (APIOffline), Tabs, Provenance panel, Modals",backend: "BLOCKED: Phase Z router not mounted" },
                    { route: "/admin",              page: "AdminPanel",        roles: "Admin only",     states: "Loading, Error, User list, Role change modal, Audit log",      backend: "GET /admin/users, /audit" },
                    { route: "/pilots",             page: "PilotDashboard",    roles: "Admin",          states: "Pilot cards, feedback capture",                                 backend: "None (static)" },
                    { route: "/commercial",         page: "CommercialPackaging",roles: "Admin",         states: "Pricing tiers, proposal builder",                               backend: "None (static)" },
                    { route: "/deploy",             page: "DeploymentPanel",   roles: "Admin",          states: "CloudFormation deployment form, status",                        backend: "deployToAWS function" },
                    { route: "/ops",                page: "ProductionDashboard",roles: "Admin",         states: "Multi-stage deployment orchestration",                          backend: "Various AWS functions" },
                    { route: "/go-live",            page: "GoLiveChecklist",   roles: "Admin",          states: "Checklist items with status",                                   backend: "executeGoLive function" },
                    { route: "/api-console",        page: "APITestConsole",    roles: "Admin",          states: "Endpoint testing, health checks",                               backend: "All Aurora API endpoints" },
                    { route: "/coverage",           page: "UICoverage (this)", roles: "Admin",          states: "Matrix, Blocked, Routes, Constitutional proof",                backend: "None" },
                  ].map(row => (
                    <tr key={row.route} className="border-b hover:bg-muted/20">
                      <td className="px-4 py-2 font-mono text-xs">{row.route}</td>
                      <td className="px-4 py-2 text-xs font-medium">{row.page}</td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">{row.roles}</td>
                      <td className="px-4 py-2 text-xs text-muted-foreground max-w-[250px]">{row.states}</td>
                      <td className="px-4 py-2 text-[10px] font-mono text-muted-foreground max-w-[200px]">{row.backend}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Constitutional proof */}
        <TabsContent value="constitutional" className="mt-4 space-y-4">
          <Card className="border-emerald-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-emerald-800">Zero Scientific Logic in Frontend — Proof</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {[
                { rule: "No ACIF formula", proof: "ACIF scores rendered verbatim from API fields (display_acif_score, acif_mean). The only math in the UI is (v × 100).toFixed(1) which is display formatting only — identical to multiplying by 100 for percentage display, applied universally to all 0-1 fraction fields." },
                { rule: "No tier derivation", proof: "Tier labels sourced from API response fields (cell.tier, scan.tier_counts). No comparison against thresholds. TierBadge renders the tier string verbatim from the API." },
                { rule: "No threshold arithmetic", proof: "tier_thresholds_used displayed verbatim when present in the canonical record. No threshold-based comparison used to assign colours or categories in the UI." },
                { rule: "No anomaly recomputation", proof: "Evidence, causal, physics, temporal scores shown as read from cell records. No combination, weighting, or aggregation performed client-side." },
                { rule: "No calibration logic", proof: "calibration_version_id displayed as a string. No calibration coefficients loaded or applied in the frontend." },
                { rule: "No MSL application", proof: "Mineral System Logic stubs are injected as prompt context into the generateGeologicalReport backend function — they do not drive any UI scoring, tier assignment, or filtering." },
                { rule: "MissingValue discipline", proof: "All null/undefined canonical fields render MissingValue component — no fallback numbers, estimated values, or default thresholds substituted." },
              ].map(({ rule, proof }) => (
                <div key={rule} className="border-l-4 border-emerald-400 pl-3 py-1">
                  <div className="font-semibold text-emerald-800">{rule}</div>
                  <div className="text-muted-foreground text-xs mt-0.5">{proof}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">End-to-End Flow Confirmation</CardTitle>
            </CardHeader>
            <CardContent className="text-xs space-y-2">
              {[
                ["Login", "Base44 AuthProvider → /auth/me → role set in Layout context → role-filtered nav rendered"],
                ["AOI Draw/Upload", "MapDrawTool (Leaflet/BBox/Upload) → geometry → AOIStep → aoiValidate → aoiSave → aoi_id + geometry_hash"],
                ["Scan Submission", "ScanParamsStep → commodity + resolution → submitScan → scan_id returned"],
                ["Results Viewing", "ScanResultsView polls getScanStatus every 4s → status/tier_counts/acif_mean rendered verbatim"],
                ["Report Viewing", "ReportViewer → audience + commodity → generateGeologicalReport (LLM backend) → sections + audit trail"],
                ["Digital Twin", "TwinView → GET /twin/{id} → VoxelRenderer (Three.js) → version selection → snapshot export"],
                ["Data Room Package", "DataRoom → CreatePackageForm → dataRoomCreate → package_id + access_url (BLOCKED pending backend)"],
                ["Portfolio", "PortfolioView → portfolioSnapshot → territories + EPI + risk tier displayed verbatim"],
                ["Admin Flow", "AdminPanel (admin role only) → listUsers → promptRoleChange → mandatory reason modal → updateRole → audit log"],
              ].map(([flow, desc]) => (
                <div key={flow} className="border-b py-1.5 last:border-0">
                  <span className="font-semibold">{flow}:</span>{" "}
                  <span className="text-muted-foreground">{desc}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}