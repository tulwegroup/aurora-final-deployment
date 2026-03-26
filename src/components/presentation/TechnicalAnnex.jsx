/**
 * TechnicalAnnex — Phase AL
 *
 * Audience: Geologists, Exploration Engineers, Geophysicists, Data Scientists
 * POSITIONING: Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.
 *
 * CONSTITUTIONAL RULES:
 *   - ACIF formula described accurately (no simplification)
 *   - Uncertainty bounds stated for every output type
 *   - No scientific misrepresentation
 *   - Calibration version lineage documented
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlaskConical, AlertTriangle, ChevronRight, Lock } from "lucide-react";

const POSITIONING_STATEMENT = "Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.";

const SECTIONS = [
  {
    num: "A1",
    title: "ACIF — Aurora Composite Inference Framework",
    content: [
      "ACIF integrates N geophysical observables into a per-cell composite score. Observable components include: gravity anomaly (Bouguer), magnetic intensity (TMI), seismic coherence, spectral band ratios, and temporal stability index.",
      "Each observable is normalised to [0,1] using province-prior-informed bounds. Normalised values are weighted by commodity-specific kernel weights derived from calibrated analogue libraries.",
      "The composite score S(c) for cell c is: S(c) = Σ_i [ w_i(commodity) × φ_i(obs_i) ] / Σ_i w_i — where φ_i is the normalised observable and w_i the kernel weight for the target commodity.",
      "Uncertainty on S(c) is propagated from: (a) input observable uncertainty, (b) calibration kernel uncertainty (Monte Carlo over 1,000 weight perturbations), and (c) province-prior confidence.",
      "Physics residual r(c) = |observed_gravity − forward_model_gravity| / σ_prior. Cells with r(c) > threshold_veto are flagged and may be excluded from tier assignment.",
    ],
    uncertainty: "ACIF scores carry a ±σ uncertainty interval. The 95% CI is stored in the canonical record per cell. Scores should not be used without consulting uncertainty fields.",
  },
  {
    num: "A2",
    title: "Tier Assignment Logic",
    content: [
      "Tier 1, 2, and 3 are classification labels assigned based on ACIF score thresholds defined in the active calibration version's ThresholdPolicy.",
      "Threshold values are commodity-specific and calibration-version-locked. Example (illustrative, not universal): Tier 1 = ACIF ≥ 0.72, Tier 2 = 0.50–0.72, Tier 3 = 0.30–0.50.",
      "Veto rules (physics residual, uncertainty cap, temporal anomaly) can override tier assignment even for high-ACIF cells. Veto logic is applied before tier finalisation.",
      "Tier counts in a canonical scan record are immutable. No downstream process may re-assign tiers without initiating a reprocess (which creates a new canonical record and preserves the original).",
    ],
    uncertainty: "Tier boundaries are calibration-version-dependent. A cell classified Tier 1 under calibration v2 may be Tier 2 under v3. Always check calibration_version field in output.",
  },
  {
    num: "A3",
    title: "Digital Twin — Voxel Architecture",
    content: [
      "The digital twin is a 3D voxel representation of ACIF-scored subsurface volumes. Each voxel is defined by: depth_m, lat_center, lon_center, commodity_probs, kernel_weight, expected_density, temporal_score, physics_residual, uncertainty.",
      "Voxel depth is derived from seismic velocity models where available, or from province-prior depth-of-exploration heuristics. Depth values carry higher uncertainty than surface observables.",
      "commodity_probs per voxel is the softmax-normalised posterior probability distribution over the candidate commodity list for the scan. It is not a geological resource probability.",
      "Visualisation uses decimation for GPU memory management. Displayed voxel count may be less than total; all stored values are verbatim from the canonical record regardless of display stride.",
    ],
    uncertainty: "Depth estimates are the highest-uncertainty dimension of the twin. Sub-surface extrapolation beyond seismic coverage uses province priors and carries uncertainty > ±20% in depth.",
  },
  {
    num: "A4",
    title: "Aurora Workflow — Technical Detail",
    steps: [
      { label: "AOI Ingestion",       detail: "Geometry validated (valid polygon, WGS84, area limits). SHA-256 hash computed and locked. AOI ID assigned. No modification after lock." },
      { label: "Data Ingestion",      detail: "Multi-source geophysical data retrieved: satellite-derived gravity, TMI, spectral (Sentinel-2/Landsat), seismic (where available). Harmonised to common grid resolution." },
      { label: "Cell Decomposition",  detail: "AOI tiled into scan cells at specified resolution. Each cell tagged with province prior, calibration version, and commodity kernel weights." },
      { label: "ACIF Scoring",        detail: "Per-cell ACIF computed: observable normalisation → kernel weighting → composite score → uncertainty propagation → veto gate → tier assignment." },
      { label: "Canonical Write",     detail: "Scored cells written to immutable canonical record. CanonicalScan record created. Digital twin built. Version registry updated." },
      { label: "Output Packaging",    detail: "GeoJSON/KML layers generated. Geological report grounded to canonical values. Data-room package assembled with geometry hash, calibration certificate, and audit trail." },
    ],
    uncertainty: null,
  },
  {
    num: "A5",
    title: "Pilot Case — Technical Detail",
    pilots: [
      {
        name: "Ghana — Gold (Ashanti Belt)",
        resolution: "Medium (~5 km²/cell)",
        cells: "~2,480 cells",
        acif_range: "0.18 – 0.84",
        tier1_pct: "18%",
        veto_rate: "6.1%",
        physics_residual_mean: "0.041",
        calibration: "gold_v2.1.3",
        uncertainty_95: "±0.08 ACIF units",
        notes: "Birimian Supergroup host rock geophysical signature dominant in northern sector. Elevated TMI and gravity gradient concordance with Tier 1 cells.",
        limitation: "No drill intercepts available within AOI. Findings represent geophysical anomaly characterisation only.",
      },
      {
        name: "Zambia — Copper (Copperbelt)",
        resolution: "Fine (~1 km²/cell)",
        cells: "~8,700 cells",
        acif_range: "0.22 – 0.91",
        tier1_pct: "24%",
        veto_rate: "3.2%",
        physics_residual_mean: "0.029",
        calibration: "copper_v3.0.1",
        uncertainty_95: "±0.12 ACIF units",
        notes: "Roan Group stratigraphy-aligned ACIF clustering. Low veto rate indicates strong physics-model concordance. Spectral anomaly pattern consistent with oxide/sulphide surface expression analogues.",
        limitation: "High-resolution scan increases cell count and anomaly definition, but also uncertainty in borderline tier assignments. Review ±σ fields before drill targeting.",
      },
      {
        name: "Senegal — Petroleum (Offshore)",
        resolution: "Coarse (~25 km²/cell)",
        cells: "~880 cells",
        acif_range: "0.11 – 0.61",
        tier1_pct: "11%",
        veto_rate: "12.4%",
        physics_residual_mean: "0.068",
        calibration: "petroleum_structural_v1.0.0",
        uncertainty_95: "±0.18 ACIF units",
        notes: "Seismic coherence patterns in northern sub-basin consistent with anticline trap geometry. Gravity low in central block suggests sedimentary depocenter. Temporal score elevated where water-column coupling is stronger.",
        limitation: "Offshore setting: gravity and seismic data quality lower than onshore equivalent. High veto rate (12.4%) indicates observable quality constraints. Coarse resolution limits prospect-scale inference.",
      },
    ],
  },
  {
    num: "A6",
    title: "Calibration, Provenance & Data Quality",
    content: [
      "Calibration versions are immutable once promoted to active status. Each version defines: kernel weights per commodity, threshold policies, veto rules, and province-prior references.",
      "Ground-truth data ingestion follows a two-step governance process: submission → admin approval. Rejected records are archived. Only approved records may influence future calibration versions.",
      "Calibration diversity safeguards prevent over-concentration of training analogues in any single geological province (Herfindahl index monitored).",
      "All source datasets are recorded in the real_sources_registry. Quality metrics (resolution, coverage, vintage) are tracked per observable per province.",
      "Observable quality scores below province-specific thresholds trigger automatic veto flags. These are propagated verbatim into the canonical cell record.",
    ],
    uncertainty: "Calibration accuracy degrades in geological settings with fewer analogue records. Province-prior confidence intervals are wider for under-sampled terrains. Check province_prior_confidence field in canonical output.",
  },
];

export default function TechnicalAnnex() {
  return (
    <div className="space-y-5">
      {/* Positioning Banner */}
      <div className="flex items-start gap-2.5 p-4 border border-emerald-300 bg-emerald-100 rounded-lg">
        <Lock className="w-5 h-5 text-emerald-700 mt-0.5 shrink-0" />
        <span className="text-sm font-semibold text-emerald-900">{POSITIONING_STATEMENT}</span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-3 p-4 border-2 border-violet-200 bg-violet-50 rounded-xl">
        <FlaskConical className="w-6 h-6 text-violet-700 mt-0.5 shrink-0" />
        <div>
          <div className="font-bold text-violet-900">Technical Annex</div>
          <div className="text-sm text-violet-700 mt-0.5">Geologists · Exploration Engineers · Geophysicists · Data Scientists</div>
          <div className="text-xs text-violet-600 mt-1">6-section technical reference · ACIF formula · Uncertainty framing · Pilot detail</div>
        </div>
      </div>

      {SECTIONS.map((sec) => (
        <Card key={sec.num} className="border-l-4 border-l-violet-400">
          <CardHeader className="pb-2 flex-row items-start gap-3">
            <span className="text-3xl font-black text-muted-foreground/30 leading-none font-mono">{sec.num}</span>
            <CardTitle className="text-base flex-1">{sec.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {sec.content && (
              <ul className="space-y-2">
                {sec.content.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm font-mono text-xs leading-relaxed">
                    <ChevronRight className="w-3.5 h-3.5 mt-0.5 text-muted-foreground shrink-0" />{c}
                  </li>
                ))}
              </ul>
            )}

            {sec.steps && (
              <div className="space-y-2">
                {sec.steps.map((s, i) => (
                  <div key={i} className="flex gap-3 border rounded p-3">
                    <div className="text-xs font-bold text-muted-foreground w-5 pt-0.5">{i + 1}.</div>
                    <div>
                      <div className="text-sm font-semibold">{s.label}</div>
                      <div className="text-xs text-muted-foreground font-mono mt-0.5">{s.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {sec.pilots && (
              <div className="space-y-4">
                {sec.pilots.map((p) => (
                  <div key={p.name} className="border rounded-lg p-4 space-y-3">
                    <div className="font-semibold text-sm">{p.name}</div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
                      {[
                        ["Resolution", p.resolution],
                        ["Cell count", p.cells],
                        ["ACIF range", p.acif_range],
                        ["Tier 1 %", p.tier1_pct],
                        ["Veto rate", p.veto_rate],
                        ["Physics residual (mean)", p.physics_residual_mean],
                        ["Calibration", p.calibration],
                        ["Uncertainty (95% CI)", p.uncertainty_95],
                      ].map(([k, v]) => (
                        <div key={k} className="bg-muted/30 rounded px-2 py-1.5">
                          <div className="text-muted-foreground text-[10px]">{k}</div>
                          <div className="font-medium">{v}</div>
                        </div>
                      ))}
                    </div>
                    <div className="text-xs">{p.notes}</div>
                    <div className="flex items-start gap-2 text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{p.limitation}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {sec.uncertainty && (
              <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span><strong>Uncertainty note:</strong> {sec.uncertainty}</span>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}