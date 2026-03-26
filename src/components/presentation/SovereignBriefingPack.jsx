/**
 * SovereignBriefingPack — Phase AL
 *
 * Audience: Governments, Geological Surveys, Regulators
 *
 * CONSTITUTIONAL RULES:
 *   - No resource claims without confirmed drilling
 *   - ACIF framed as non-physical scoring function
 *   - Aurora explicitly positioned as screening tool, not replacement for field validation
 *   - Audit trail and governance emphasis
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, AlertTriangle, ChevronRight, Globe, Lock } from "lucide-react";

const POSITIONING_STATEMENT = "Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.";

const SLIDES = [
  {
    num: "01",
    title: "What Aurora OSI Delivers",
    type: "Overview",
    content: [
      "Aurora OSI is a multi-source geophysical assessment platform designed for systematic mineral exploration screening across national territories and state blocks.",
      "It integrates satellite gravity, airborne magnetic, spectral imaging, and seismic data to generate rapid, auditable geophysical assessments.",
      "Core output: ACIF (Aurora Composite Inference Framework) scoring — a dimensionless geophysical anomaly index per cell.",
      "Secondary outputs: tier classification (Tier 1/2/3 = high/medium/low geophysical alignment), digital twin visualisation, and risk-adjusted portfolio ranking.",
    ],
    callout: {
      label: "Positioning",
      text: POSITIONING_STATEMENT,
      highlight: true,
    },
  },
  {
    num: "02",
    title: "The Aurora Workflow",
    type: "Process",
    workflow: [
      { step: "AOI Definition",     desc: "Government defines target block or concession. Geometry locked and cryptographically hashed for audit trail." },
      { step: "Data Integration",   desc: "Multi-source geophysical data harmonised: gravity, magnetics, spectral, seismic (where available). Data provenance recorded." },
      { step: "ACIF Scoring",       desc: "Per-cell geophysical anomaly score computed using calibrated commodity-specific kernel weights. Uncertainty quantified." },
      { step: "Tier Assignment",    desc: "Cells classified into tiers using calibration-version-locked thresholds. Physics residual veto applied. Immutable record created." },
      { step: "Canonical Record",   desc: "Scored cells stored in tamper-evident canonical format. Version history maintained. Audit trail locked." },
      { step: "Portfolio Delivery",  desc: "Executive report, digital twin, and secure data-room package generated. Time-limited watermarked delivery." },
    ],
  },
  {
    num: "03",
    title: "Understanding ACIF Scores",
    type: "Output Explanation",
    content: [
      "ACIF is a dimensionless geophysical anomaly scoring function. It is not a geological quality metric, resource probability, or economic proxy.",
      "ACIF = Σ [ w_i(commodity) × φ_i(observable) ] where w_i are calibrated kernel weights and φ_i are normalised observables (gravity, magnetic, spectral, seismic).",
      "Higher ACIF indicates stronger geophysical alignment with the target commodity's analogue signature in the calibration library. It does not indicate deposit presence, grade, or size.",
      "All ACIF scores carry explicit uncertainty intervals (±σ, 95% CI). Scores below uncertainty threshold are flagged as 'low confidence'.",
      "Tier 1 cells (ACIF ≥ threshold) are anomaly indicators suitable for exploration prioritisation. They do not confirm mineralisation without drilling.",
    ],
    callout: {
      label: "Not a Resource Metric",
      text: "ACIF is a geophysical screening index. It cannot be used to estimate resources, reserves, or economic parameters without independent field validation and drilling confirmation.",
    },
  },
  {
    num: "04",
    title: "Pilot Case Summaries",
    type: "Evidence",
    pilots: [
      {
        name: "Ghana — Gold (Ashanti Belt)",
        territory: "12,400 km² · Birimian Supergroup",
        tier1_pct: "18%",
        acif_mean: "0.52",
        veto_rate: "6.1%",
        system_status: "PASS_CONFIRMED",
        msl_alignment: "Birimian orogenic gold signature present. TMI and gravity gradient concordance with analogue library.",
        finding: "Tier 1 clustering in northern sector consistent with historical gold production zones.",
        caveat: "No drilling confirmation in AOI. Geophysical anomaly identification only. No resource estimate possible.",
      },
      {
        name: "Zambia — Copper (Copperbelt)",
        territory: "8,700 km² · Roan Group stratigraphy",
        tier1_pct: "24%",
        acif_mean: "0.61",
        veto_rate: "3.2%",
        system_status: "PASS_CONFIRMED",
        msl_alignment: "Roan Group metallogenic signature. Low veto rate indicates strong physics-model concordance.",
        finding: "High Tier 1 density in central block. Spectral anomaly pattern consistent with oxide/sulphide surface expression.",
        caveat: "No drilling confirmation in AOI. Exploratory geophysical characterisation. Uncertainty ±0.12 ACIF units (95% CI).",
      },
      {
        name: "Senegal — Petroleum (Offshore Basin)",
        territory: "22,000 km² · Taoudeni Basin",
        tier1_pct: "11%",
        acif_mean: "0.38",
        veto_rate: "12.4%",
        system_status: "PASS_CONFIRMED",
        msl_alignment: "Seismic structural lead detected. Anticline trap geometry consistent with basin depositional models.",
        finding: "Gravity low in central block suggests sedimentary depocenter. Structural lead defined for follow-up seismic interpretation.",
        caveat: "Offshore setting increases data uncertainty. Structural lead only — not a prospect. No drilling confirmation. High uncertainty (±0.18 ACIF units).",
      },
    ],
  },
  {
    num: "05",
    title: "Governance, Provenance & Audit",
    type: "Compliance",
    content: [
      "All Aurora outputs are deterministic, versioned, and auditable. Every scan record includes: scan_id, calibration_version, geometry_hash, and immutable timestamp.",
      "Calibration versions are locked — no retroactive changes. Ground-truth data ingestion follows two-step governance: submission → admin approval → archived or active status.",
      "Data provenance is recorded for all source observables: satellite imagery (vintage, provider, processing), airborne surveys (date, QA metrics), and seismic data (processing version).",
      "Tier assignment rules and ACIF kernel weights are versioned and cited in every output. Weight changes produce new calibration versions with clear audit trail.",
      "Export materials include geometry_hash (SHA-256 of AOI boundary) and calibration_version for field validation and reproducibility audits.",
    ],
    callout: {
      label: "Audit Trail",
      text: "Every scan is fully auditable. Download audit certificate from data-room package for independent verification of scoring logic and calibration version.",
    },
  },
  {
    num: "06",
    title: "What Aurora Does Not Claim",
    type: "Limitations",
    limitations: [
      "Aurora does not estimate resources, reserves, or economically mineable tonnages. ACIF and tier classifications are geophysical anomaly indicators only.",
      "Aurora outputs cannot be used as supporting data for JORC Code or National Instrument 43-101 resource/reserve statements without independent geological and drilling validation.",
      "Tier 1 cells do not confirm mineralisation. They indicate geophysical alignment with target commodity analogues in the calibration library.",
      "Digital twin visualisations are screening aids, not resource models. Voxel values are propagated from ACIF scores, not physical density estimates.",
      "No pilot finding has been independently drill-confirmed within the cited AOI boundaries. All pilot results are exploratory.",
      "Uncertainty bounds are stated for all outputs. Aurora results in novel geological settings may have accuracy degradation where analogue coverage is sparse.",
      "Aurora is a systematic screening tool for exploration portfolio prioritisation. It requires follow-up fieldwork, drilling, and geological validation before resource or economic claims.",
    ],
  },
];

const TYPE_COLORS = {
  Overview:             "bg-slate-50 text-slate-700 border-slate-200",
  Process:              "bg-violet-50 text-violet-700 border-violet-200",
  "Output Explanation": "bg-amber-50 text-amber-700 border-amber-200",
  Evidence:             "bg-emerald-50 text-emerald-700 border-emerald-200",
  Compliance:           "bg-blue-50 text-blue-700 border-blue-200",
  Limitations:          "bg-red-50 text-red-700 border-red-200",
};

export default function SovereignBriefingPack() {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3 p-4 border-2 border-blue-200 bg-blue-50 rounded-xl">
        <Shield className="w-6 h-6 text-blue-700 mt-0.5 shrink-0" />
        <div>
          <div className="font-bold text-blue-900">Sovereign Briefing Pack</div>
          <div className="text-sm text-blue-700 mt-0.5">Governments · Geological Surveys · Regulators</div>
          <div className="text-xs text-blue-600 mt-1">6-slide structured briefing · Audit trail emphasis · No resource claims</div>
        </div>
      </div>

      {SLIDES.map((slide) => (
        <Card key={slide.num} className="border-l-4 border-l-blue-400">
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

            {slide.callout && (
              <div className={`flex items-start gap-2 text-xs rounded px-3 py-2 ${
                slide.callout.highlight
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : "bg-amber-50 text-amber-800 border border-amber-200"
              }`}>
                {slide.callout.highlight ? (
                  <Lock className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                )}
                <span><strong>{slide.callout.label}:</strong> {slide.callout.text}</span>
              </div>
            )}

            {slide.workflow && (
              <div className="space-y-2">
                {slide.workflow.map((w, i) => (
                  <div key={i} className="flex gap-3 border rounded p-3 bg-muted/20">
                    <div className="text-xs font-bold text-muted-foreground w-6 pt-0.5">{i + 1}.</div>
                    <div>
                      <div className="text-sm font-semibold">{w.step}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{w.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {slide.pilots && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {slide.pilots.map((p) => (
                  <div key={p.name} className="border rounded-lg p-3 space-y-2">
                    <div className="font-semibold text-sm">{p.name}</div>
                    <div className="text-xs text-muted-foreground">{p.territory}</div>
                    <div className="grid grid-cols-2 gap-1 text-xs font-mono">
                      <div className="bg-muted/30 rounded px-1.5 py-1"><span className="text-muted-foreground text-[10px]">Tier 1</span><div>{p.tier1_pct}</div></div>
                      <div className="bg-muted/30 rounded px-1.5 py-1"><span className="text-muted-foreground text-[10px]">ACIF mean</span><div>{p.acif_mean}</div></div>
                      <div className="bg-muted/30 rounded px-1.5 py-1"><span className="text-muted-foreground text-[10px]">Veto rate</span><div>{p.veto_rate}</div></div>
                      <div className="bg-muted/30 rounded px-1.5 py-1"><span className="text-muted-foreground text-[10px]">Status</span><div className="text-[10px]">✓</div></div>
                    </div>
                    <div className="text-xs">{p.finding}</div>
                    <div className="flex items-start gap-1.5 text-[10px] text-amber-800 bg-amber-50 rounded px-2 py-1">
                      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{p.caveat}
                    </div>
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