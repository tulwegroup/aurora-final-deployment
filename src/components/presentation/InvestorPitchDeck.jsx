/**
 * InvestorPitchDeck — Phase AL
 *
 * Audience: Investment Funds, C-Suite, Due-Diligence Teams
 * POSITIONING: Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.
 *
 * CONSTITUTIONAL RULES:
 *   - No resource estimates without confirmed drilling
 *   - EPI framed as non-physical aggregation metric
 *   - Risk tiers are classification labels, not economic forecasts
 *   - Uncertainty framing on all output descriptions
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, AlertTriangle, ChevronRight, BarChart3, Globe, Lock } from "lucide-react";

const POSITIONING_STATEMENT = "Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.";

const SLIDES = [
  {
    num: "01",
    title: "The Exploration Intelligence Gap",
    type: "Problem",
    content: [
      "Traditional mineral exploration is slow, expensive, and geographically uneven. Drill-first approaches consume 70–90% of exploration budgets before a single probabilistic filter is applied.",
      "Most global greenfield acreage has never been systematically screened with modern multi-source geophysical integration.",
      "Aurora OSI addresses this by delivering rapid, systematic, multi-source geophysical assessments — enabling capital allocation decisions before committing to expensive fieldwork.",
    ],
    callout: null,
  },
  {
    num: "02",
    title: "What Aurora Delivers to Investors",
    type: "Value Proposition",
    positioning: true,
    content: [
      "Portfolio-level screening: assess dozens of blocks simultaneously and rank by Exploration Priority Index (EPI).",
      "Due-diligence acceleration: structured, auditable scan outputs with full provenance replace ad hoc geological assessments.",
      "Risk-adjusted prioritisation: territories classified as LOW, MEDIUM, or HIGH risk using canonical stored outputs.",
      "Secure data-room delivery: time-limited, watermarked packages for deal-room sharing with full access logging.",
    ],
    callout: {
      label: "Positioning",
      text: POSITIONING_STATEMENT,
    },
  },
  {
    num: "03",
    title: "Understanding the Exploration Priority Index (EPI)",
    type: "Output Explanation",
    content: [
      "EPI is a non-physical aggregation metric. It combines three stored canonical outputs using configurable weights: ACIF mean score, Tier 1 cell density, and veto compliance rate.",
      "EPI does not represent metal price, resource tonnage, NPV, or economic return. It is a relative prioritisation tool within a portfolio.",
      "Higher EPI indicates stronger relative geophysical alignment across the territory, adjusted for data quality and veto compliance.",
      "EPI is risk-adjustable: applying a risk multiplier reweights the index to reflect geopolitical, geological, or infrastructure factors.",
    ],
    callout: {
      label: "EPI Formula Note",
      text: "EPI = w_acif × acif_mean + w_tier1 × tier1_density + w_veto × veto_compliance. Weights are versioned (weight_config_version). Changing weights produces a new EPI — the underlying ACIF scores are unchanged.",
    },
  },
  {
    num: "04",
    title: "Pilot Results at a Glance",
    type: "Evidence",
    pilots: [
      { name: "Ghana (Gold)", territory: "Ashanti Belt · 12,400 km²", tier1_pct: "18%", risk: "LOW",    epi_note: "Strong ACIF alignment with Birimian analogues", caveat: "No drilling confirmation in AOI. Exploratory finding." },
      { name: "Zambia (Copper)", territory: "Copperbelt · 8,700 km²", tier1_pct: "24%", risk: "LOW",    epi_note: "High Tier 1 density, low veto rate. Strong spatial clustering.", caveat: "No drill data in AOI boundary. Uncertainty ±0.12 ACIF units (95% CI)." },
      { name: "Senegal (Petroleum)", territory: "Offshore Basin · 22,000 km²", tier1_pct: "11%", risk: "MEDIUM", epi_note: "Structural lead — seismic coherence consistent with anticline traps.", caveat: "Offshore setting increases uncertainty. Structural lead only, not a prospect." },
    ],
  },
  {
    num: "05",
    title: "From Scan to Deal Room",
    type: "Process",
    workflow: [
      { step: "AOI Submission",   desc: "Define target block. Geometry locked and hashed. Scan parameters configured." },
      { step: "Aurora Scan",      desc: "Multi-source geophysical assessment. ACIF scored. Tiers assigned. Digital twin built." },
      { step: "Investor Package", desc: "Executive report, EPI summary, risk tier, and portfolio comparison generated." },
      { step: "Data Room",        desc: "Watermarked, time-limited secure link. Revocable. Full access audit log." },
    ],
  },
  {
    num: "06",
    title: "What Aurora Does Not Claim",
    type: "Limitations",
    limitations: [
      "No resource or reserve estimates are made. Aurora outputs cannot be used as JORC/NI 43-101 supporting data without independent validation.",
      "EPI and Risk Tier are relative classification tools, not economic forecasts.",
      "Tier 1 cells are geophysical anomaly indicators. They do not confirm economically viable mineralisation.",
      "All pilot findings are exploratory. No Aurora pilot has been independently drill-confirmed within the cited AOI boundaries.",
      "Uncertainty bounds accompany all outputs. Results in novel geological settings may have lower analogue accuracy.",
      "Aurora is a screening and prioritisation tool. It does not substitute for geological fieldwork, drilling, or feasibility studies.",
    ],
  },
];

const RISK_STYLES = { LOW: "bg-emerald-100 text-emerald-800", MEDIUM: "bg-amber-100 text-amber-800", HIGH: "bg-red-100 text-red-800" };
const TYPE_COLORS = {
  Problem:             "bg-slate-50 text-slate-700 border-slate-200",
  "Value Proposition": "bg-blue-50 text-blue-700 border-blue-200",
  "Output Explanation":"bg-amber-50 text-amber-700 border-amber-200",
  Evidence:            "bg-emerald-50 text-emerald-700 border-emerald-200",
  Process:             "bg-violet-50 text-violet-700 border-violet-200",
  Limitations:         "bg-red-50 text-red-700 border-red-200",
};

export default function InvestorPitchDeck() {
  return (
    <div className="space-y-5">
      {/* Positioning Banner */}
      <div className="flex items-start gap-2.5 p-4 border border-emerald-300 bg-emerald-100 rounded-lg">
        <Lock className="w-5 h-5 text-emerald-700 mt-0.5 shrink-0" />
        <span className="text-sm font-semibold text-emerald-900">{POSITIONING_STATEMENT}</span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-3 p-4 border-2 border-emerald-200 bg-emerald-50 rounded-xl">
        <TrendingUp className="w-6 h-6 text-emerald-700 mt-0.5 shrink-0" />
        <div>
          <div className="font-bold text-emerald-900">Investor Pitch Deck</div>
          <div className="text-sm text-emerald-700 mt-0.5">Investment Funds · C-Suite · Due-Diligence Teams</div>
          <div className="text-xs text-emerald-600 mt-1">6-slide structured deck · EPI framed as non-physical metric · No resource claims</div>
        </div>
      </div>

      {SLIDES.map((slide) => (
        <Card key={slide.num} className="border-l-4 border-l-emerald-400">
          <CardHeader className="pb-2 flex-row items-start gap-3">
            <span className="text-3xl font-black text-muted-foreground/30 leading-none">{slide.num}</span>
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <CardTitle className="text-base">{slide.title}</CardTitle>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${TYPE_COLORS[slide.type] || ""}`}>{slide.type}</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {slide.content && (
              <ul className="space-y-2">
                {slide.content.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <ChevronRight className="w-3.5 h-3.5 mt-0.5 text-muted-foreground shrink-0" />{c}
                  </li>
                ))}
              </ul>
            )}

            {slide.positioning && !slide.callout && (
              <div className="flex items-start gap-2.5 p-3 border border-emerald-300 bg-emerald-50 rounded">
                <Lock className="w-4 h-4 text-emerald-700 mt-0.5 shrink-0" />
                <span className="text-sm text-emerald-900">{POSITIONING_STATEMENT}</span>
              </div>
            )}

            {slide.callout && (
              <div className="flex items-start gap-2 text-xs bg-amber-50 text-amber-800 border border-amber-200 rounded px-3 py-2">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span><strong>{slide.callout.label}:</strong> {slide.callout.text}</span>
              </div>
            )}

            {slide.pilots && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {slide.pilots.map((p) => (
                  <div key={p.name} className="border rounded-lg p-3 space-y-2">
                    <div className="font-semibold text-sm">{p.name}</div>
                    <div className="text-xs text-muted-foreground">{p.territory}</div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono">Tier 1: {p.tier1_pct}</span>
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${RISK_STYLES[p.risk]}`}>{p.risk} RISK</span>
                    </div>
                    <div className="text-xs">{p.epi_note}</div>
                    <div className="flex items-start gap-1.5 text-[10px] text-amber-800 bg-amber-50 rounded px-2 py-1">
                      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{p.caveat}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {slide.workflow && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                {slide.workflow.map((w, i) => (
                  <div key={i} className="bg-muted/30 rounded-lg p-3 border">
                    <div className="text-[10px] text-muted-foreground font-medium uppercase mb-0.5">Step {i + 1}</div>
                    <div className="text-sm font-semibold mb-1">{w.step}</div>
                    <div className="text-xs text-muted-foreground">{w.desc}</div>
                  </div>
                ))}
              </div>
            )}

            {slide.limitations && (
              <ul className="space-y-2">
                {slide.limitations.map((l, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-red-800">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-red-500" />{l}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}