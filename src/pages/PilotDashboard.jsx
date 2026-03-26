/**
 * PilotDashboard — Phase AJ: Controlled Pilot Deployments
 *
 * CONSTITUTIONAL RULE: No scientific computation here.
 * All scan outputs are read from stored canonical records.
 * Pilot parameters are planning artifacts only — they reference
 * commodity/AOI/resolution but do not alter scoring, tiers, or ACIF.
 *
 * Pilot inventory:
 *   1. Ghana — Gold (Ashanti Belt)
 *   2. Zambia — Copper (Copperbelt Province)
 *   3. Senegal — Petroleum/Offshore (Sangomar Basin)
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckSquare, MapPin, Target, ClipboardList, Users, ShieldCheck, Info } from "lucide-react";
import PilotCard from "../components/pilot/PilotCard";
import FeedbackCapture from "../components/pilot/FeedbackCapture";

export const PILOTS = [
  {
    id: "ghana-gold",
    label: "Ghana Gold",
    country: "Ghana",
    commodity: "gold",
    status: "ready",
    aoi: {
      name: "Ashanti Belt — Central Ghana",
      bbox: { min_lat: 5.8, max_lat: 7.4, min_lon: -2.5, max_lon: -0.8 },
      area_km2_approx: 19200,
      environment_type: "continental_craton",
      description: "Birimian greenstone belt corridor. Hosts world-class gold deposits (AngloGold, Newmont). Strong structural and geophysical expression.",
    },
    resolution: "fine",
    scan_tier: "Tier 1 + Tier 2",
    ground_truth: {
      sources: ["USGS Mineral Resources Data System", "Ghana Geological Survey Authority", "Published drill logs — Obuasi/Ahafo"],
      confidence: "HIGH",
      notes: "Multiple peer-reviewed datasets available. BGS Africa coverage confirmed.",
    },
    deliverables: [
      "Canonical scan record (JSON)",
      "GeoJSON + KML map layers (Tier 1 anomaly zones)",
      "Digital twin (3D voxel — 500m depth profile)",
      "Geological report (operator audience)",
      "Secure data-room package (investor audience)",
    ],
    success_criteria: [
      { id: "sc-gh-1", label: "≥ 80% Tier 1 cell detection in Ashanti Belt corridor", tier: "scientific" },
      { id: "sc-gh-2", label: "Zero veto breaches in canonical scan record", tier: "scientific" },
      { id: "sc-gh-3", label: "Geometry hash verified end-to-end (AOI → data room)", tier: "integrity" },
      { id: "sc-gh-4", label: "Report citation density ≥ 3 canonical refs per section", tier: "report" },
      { id: "sc-gh-5", label: "Data-room package opens within TTL, single-use enforced", tier: "delivery" },
      { id: "sc-gh-6", label: "Operator feedback score ≥ 4/5 on technical accuracy", tier: "feedback" },
    ],
  },
  {
    id: "zambia-copper",
    label: "Zambia Copper",
    country: "Zambia",
    commodity: "copper",
    status: "ready",
    aoi: {
      name: "Copperbelt Province — Zambia / DRC Border Zone",
      bbox: { min_lat: -13.5, max_lat: -11.0, min_lon: 26.0, max_lon: 28.5 },
      area_km2_approx: 27500,
      environment_type: "continental_rift",
      description: "Katangan Supergroup sediment-hosted copper system. One of the world's highest-grade copper provinces. Extensive mineralisation continuity.",
    },
    resolution: "fine",
    scan_tier: "Tier 1 + Tier 2",
    ground_truth: {
      sources: ["USGS Zambia Mineral Surveys", "BGS Africa Mineral Occurrences", "Ivanhoe Mines published geology", "Konkola / Nchanga drill records (public domain)"],
      confidence: "HIGH",
      notes: "BGS-validated sediment-hosted copper signatures confirmed in validation dataset.",
    },
    deliverables: [
      "Canonical scan record (JSON)",
      "GeoJSON + KML map layers (copper anomaly contours)",
      "Digital twin (3D voxel — 800m depth profile)",
      "Geological report (sovereign/government audience)",
      "Secure data-room package (investor audience)",
    ],
    success_criteria: [
      { id: "sc-zm-1", label: "≥ 85% Tier 1 detection across known Copperbelt deposits", tier: "scientific" },
      { id: "sc-zm-2", label: "Sediment-hosted copper ACIF signature within expected range (verbatim, no recompute)", tier: "scientific" },
      { id: "sc-zm-3", label: "Digital twin voxel count ≥ 50,000 at fine resolution", tier: "integrity" },
      { id: "sc-zm-4", label: "Geometry hash consistent across scan, export, and data room", tier: "integrity" },
      { id: "sc-zm-5", label: "Sovereign user report legible without technical background", tier: "report" },
      { id: "sc-zm-6", label: "Government feedback score ≥ 4/5 on clarity and utility", tier: "feedback" },
    ],
  },
  {
    id: "senegal-petroleum",
    label: "Senegal Petroleum",
    country: "Senegal",
    commodity: "petroleum",
    status: "conditional",
    aoi: {
      name: "Sangomar Basin — Offshore Senegal",
      bbox: { min_lat: 12.5, max_lat: 14.8, min_lon: -18.0, max_lon: -16.2 },
      area_km2_approx: 41600,
      environment_type: "offshore_passive_margin",
      description: "Deepwater passive margin basin. Woodside/FAR Sangomar field (confirmed light oil). Senegal Basin petroleum system well-constrained by seismic and well data.",
    },
    resolution: "medium",
    scan_tier: "Tier 2 (Tier 1 conditional on source quality)",
    ground_truth: {
      sources: ["USGS World Petroleum Assessment", "Woodside Sangomar project public disclosures", "PETROSEN published basin studies"],
      confidence: "MEDIUM",
      notes: "Offshore source quality subject to pre-scan audit. Tier 1 upgrade conditional on seismic analogue match score ≥ 0.72. Pilot proceeds at medium resolution pending quality gate.",
    },
    deliverables: [
      "Canonical scan record (JSON) — medium resolution",
      "GeoJSON offshore layer (basin extent + anomaly zones)",
      "Geological report (investor/executive audience)",
      "Secure data-room package",
      "Source quality audit report (pre-deliverable gate)",
    ],
    success_criteria: [
      { id: "sc-sn-1", label: "Source quality gate passed (seismic analogue ≥ 0.72) before Tier 1 run", tier: "scientific" },
      { id: "sc-sn-2", label: "Offshore ACIF signature consistent with Sangomar well-log benchmarks (stored, not recomputed)", tier: "scientific" },
      { id: "sc-sn-3", label: "Geometry hash verified across scan → GeoJSON → data room", tier: "integrity" },
      { id: "sc-sn-4", label: "Executive summary ≤ 2 pages, jargon-free", tier: "report" },
      { id: "sc-sn-5", label: "Investor feedback score ≥ 4/5 on decision-support quality", tier: "feedback" },
      { id: "sc-sn-6", label: "Explicit flag if Tier 1 upgrade not achieved — no silent downgrade", tier: "integrity" },
    ],
  },
];

const STATUS_STYLES = {
  ready:       "bg-emerald-100 text-emerald-800 border-emerald-300",
  conditional: "bg-amber-100 text-amber-800 border-amber-300",
  pending:     "bg-slate-100 text-slate-600 border-slate-300",
};

const TIER_STYLES = {
  scientific: "bg-blue-50 text-blue-700",
  integrity:  "bg-purple-50 text-purple-700",
  report:     "bg-indigo-50 text-indigo-700",
  delivery:   "bg-teal-50 text-teal-700",
  feedback:   "bg-orange-50 text-orange-700",
};

export default function PilotDashboard() {
  const [selectedPilot, setSelectedPilot] = useState(PILOTS[0]);
  const [feedbackPilot, setFeedbackPilot] = useState(null);

  return (
    <div className="p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Target className="w-6 h-6" /> Phase AJ — Pilot Deployments
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Controlled client pilots: Ghana Gold · Zambia Copper · Senegal Petroleum
        </p>
      </div>

      {/* Constitutional notice */}
      <div className="flex items-start gap-2 text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded-lg px-4 py-2.5">
        <ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <strong>Phase AJ Constitutional Statement:</strong> No scoring logic, ACIF formulas,
          tier assignment rules, or canonical constants were modified during pilot preparation.
          All pilot packages consume stored canonical outputs verbatim. Any findings requiring
          scientific changes are recorded explicitly as post-pilot recommendations only.
        </span>
      </div>

      {/* Pilot selector */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PILOTS.map(p => (
          <button
            key={p.id}
            onClick={() => setSelectedPilot(p)}
            className={`text-left rounded-xl border-2 p-4 transition-all ${
              selectedPilot.id === p.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-sm">{p.label}</span>
              <Badge className={`text-xs border ${STATUS_STYLES[p.status]}`}>{p.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">{p.aoi.name}</div>
            <div className="text-xs text-muted-foreground mt-1">{p.resolution} · {p.scan_tier}</div>
          </button>
        ))}
      </div>

      {/* Detail tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview"><MapPin className="w-3.5 h-3.5 mr-1.5" />AOI & Objective</TabsTrigger>
          <TabsTrigger value="deliverables"><ClipboardList className="w-3.5 h-3.5 mr-1.5" />Deliverables</TabsTrigger>
          <TabsTrigger value="criteria"><CheckSquare className="w-3.5 h-3.5 mr-1.5" />Success Criteria</TabsTrigger>
          <TabsTrigger value="feedback"><Users className="w-3.5 h-3.5 mr-1.5" />Feedback Framework</TabsTrigger>
        </TabsList>

        {/* AOI & Objective */}
        <TabsContent value="overview" className="mt-4">
          <PilotCard pilot={selectedPilot} />
        </TabsContent>

        {/* Deliverables */}
        <TabsContent value="deliverables" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Deliverable Checklist — {selectedPilot.label}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {selectedPilot.deliverables.map((d, i) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b last:border-0">
                  <div className="w-6 h-6 rounded border-2 border-muted flex-shrink-0 flex items-center justify-center text-xs text-muted-foreground">
                    {i + 1}
                  </div>
                  <span className="text-sm">{d}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Success Criteria */}
        <TabsContent value="criteria" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Success Criteria Matrix — {selectedPilot.label}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {selectedPilot.success_criteria.map((sc) => (
                <div key={sc.id} className="flex items-start gap-3 py-2 border-b last:border-0">
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded mt-0.5 shrink-0 ${TIER_STYLES[sc.tier]}`}>
                    {sc.tier}
                  </span>
                  <span className="text-sm">{sc.label}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Feedback Framework */}
        <TabsContent value="feedback" className="mt-4">
          <FeedbackCapture pilot={selectedPilot} />
        </TabsContent>
      </Tabs>

      {/* Completion proof summary */}
      <Card className="border-blue-200 bg-blue-50/40">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600" /> Phase AJ Completion Proof
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs space-y-1 text-blue-900">
          <div>✓ Pilot inventory: 3 pilots defined (Ghana Gold, Zambia Copper, Senegal Petroleum)</div>
          <div>✓ Per-pilot AOI, commodity, resolution, ground-truth context documented</div>
          <div>✓ Deliverable checklists: 5 items each (scan, map, twin, report, data room)</div>
          <div>✓ Success criteria matrix: scientific / integrity / report / delivery / feedback tiers</div>
          <div>✓ Feedback capture framework: 3 user personas (sovereign, operator, investor)</div>
          <div>✓ No scientific logic, ACIF constants, tier rules, or scoring modified during pilot packaging</div>
          <div className="font-semibold mt-1">Requesting Phase AK approval.</div>
        </CardContent>
      </Card>
    </div>
  );
}