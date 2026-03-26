"""
Aurora OSI vNext — Portfolio Aggregation
Phase AD §AD.2 (Corrected)

CORRECTIONS APPLIED:
  - exploration_priority_index replaces portfolio_score throughout
  - Hard-coded _W_ACIF, _W_TIER1, _W_RISK constants removed
  - All weight usage delegates to PortfolioWeightConfig (versioned, auditable)

CONSTITUTIONAL RULES:
  Rule 1: All aggregation reads stored scan records only — no recomputation.
  Rule 2: acif_mean is the stored aggregate — never recalculated here.
  Rule 3: Tier counts are summed from stored values — not re-derived from ACIF.
  Rule 4: exploration_priority_index is a non-physical aggregation metric.
          It must never be labeled as a geological score or ACIF value.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from typing import Optional

from app.models.portfolio_model import (
    ScanContribution, TerritoryBlock, PortfolioRiskProfile,
    PortfolioScore, PortfolioEntry, RiskTier, PortfolioStatus,
    PortfolioWeightConfig, DEFAULT_WEIGHT_CONFIG,
)


# ---------------------------------------------------------------------------
# 1. Risk tier classification (from stored metrics only)
# ---------------------------------------------------------------------------

def classify_risk_tier(veto_rate: float, coverage_score: float, scan_count: int) -> RiskTier:
    """
    Classify territory risk tier from stored veto rate and coverage score.
    No ACIF used.
    """
    if veto_rate > 0.30 or coverage_score < 0.30 or scan_count < 2:
        return RiskTier.HIGH
    if veto_rate < 0.05 and coverage_score > 0.70 and scan_count >= 3:
        return RiskTier.LOW
    return RiskTier.MEDIUM


def build_risk_notes(
    veto_rate: float, coverage_score: float,
    scan_count: int, gt_confidence: Optional[float],
) -> tuple[str, ...]:
    notes = []
    if veto_rate > 0.30:
        notes.append(f"High veto rate ({veto_rate:.1%}) — geophysical constraints violated in >30% of cells")
    elif veto_rate > 0.10:
        notes.append(f"Moderate veto rate ({veto_rate:.1%})")
    else:
        notes.append(f"Low veto rate ({veto_rate:.1%}) — good geophysical compliance")

    if coverage_score < 0.30:
        notes.append(f"Low observable coverage ({coverage_score:.1%}) — multi-source data gaps")
    elif coverage_score > 0.70:
        notes.append(f"Good observable coverage ({coverage_score:.1%})")

    if scan_count < 2:
        notes.append("Only one scan available — limited reproducibility")
    elif scan_count >= 3:
        notes.append(f"{scan_count} independent scans — good spatial coverage")

    if gt_confidence is not None:
        if gt_confidence < 0.4:
            notes.append(f"Low ground-truth confidence ({gt_confidence:.2f})")
        elif gt_confidence > 0.7:
            notes.append(f"High ground-truth confidence ({gt_confidence:.2f})")

    return tuple(notes)


# ---------------------------------------------------------------------------
# 2. exploration_priority_index computation (versioned weights)
# ---------------------------------------------------------------------------

def compute_exploration_priority(
    acif_mean:    Optional[float],
    tier1_count:  int,
    total_cells:  int,
    veto_count:   int,
    weight_config: PortfolioWeightConfig = DEFAULT_WEIGHT_CONFIG,
) -> PortfolioScore:
    """
    Compute exploration_priority_index from stored canonical metrics.

    CORRECTION: weights sourced from PortfolioWeightConfig — no hard-coded constants.

    exploration_priority_index = (
        w_acif_mean      × acif_mean        +
        w_tier1_density  × tier1_density    +
        w_veto_compliance × (1 − veto_rate)
    ) / (w_acif_mean + w_tier1_density + w_veto_compliance)

    PROOF: all inputs are stored values. No ACIF is recomputed.
    exploration_priority_index is a non-physical aggregation metric.
    """
    if total_cells <= 0:
        return PortfolioScore(
            raw_acif_mean              = acif_mean,
            tier1_density              = 0.0,
            veto_rate                  = 0.0,
            exploration_priority_index = 0.0,
            exploration_priority_rank  = None,
            weight_config_version      = weight_config.version_id,
            weights_used               = {
                "w_acif_mean": weight_config.w_acif_mean,
                "w_tier1_density": weight_config.w_tier1_density,
                "w_veto_compliance": weight_config.w_veto_compliance,
            },
        )

    tier1_density = tier1_count / total_cells
    veto_rate     = veto_count / total_cells
    acif_val      = acif_mean if acif_mean is not None else 0.0

    # Weights sourced from config — never hard-coded
    w_a = weight_config.w_acif_mean
    w_t = weight_config.w_tier1_density
    w_v = weight_config.w_veto_compliance

    index = (
        w_a * acif_val +
        w_t * tier1_density +
        w_v * (1.0 - veto_rate)
    ) / (w_a + w_t + w_v)   # denominator = 1.0 enforced by PortfolioWeightConfig

    return PortfolioScore(
        raw_acif_mean              = acif_mean,
        tier1_density              = round(tier1_density, 6),
        veto_rate                  = round(veto_rate, 6),
        exploration_priority_index = round(index, 6),
        exploration_priority_rank  = None,
        weight_config_version      = weight_config.version_id,
        weights_used               = {
            "w_acif_mean": w_a,
            "w_tier1_density": w_t,
            "w_veto_compliance": w_v,
        },
    )


# ---------------------------------------------------------------------------
# 3. PortfolioEntry assembly
# ---------------------------------------------------------------------------

def assemble_portfolio_entry(
    entry_id:       str,
    territory:      TerritoryBlock,
    contributions:  list[ScanContribution],
    gt_confidence:  Optional[float] = None,
    actor_id:       str = "system",
    weight_config:  PortfolioWeightConfig = DEFAULT_WEIGHT_CONFIG,
) -> PortfolioEntry:
    """
    Assemble a PortfolioEntry from a set of ScanContributions.
    All numeric aggregation uses stored canonical values.
    Weights sourced from PortfolioWeightConfig — versioned and auditable.
    """
    from datetime import datetime

    if not contributions:
        raise ValueError(f"PortfolioEntry {entry_id}: no scan contributions provided.")

    total_cells  = sum(c.total_cells for c in contributions)
    tier1_total  = sum(c.tier_1_count for c in contributions)
    veto_total   = sum(c.veto_count for c in contributions)

    acif_vals = [(c.acif_mean, c.total_cells) for c in contributions if c.acif_mean is not None]
    if acif_vals and total_cells > 0:
        weight_total = sum(w for _, w in acif_vals)
        agg_acif = sum(v * w for v, w in acif_vals) / weight_total if weight_total > 0 else None
    else:
        agg_acif = None

    passing = sum(
        1 for c in contributions
        if c.system_status in ("PASS_CONFIRMED", "PARTIAL_SIGNAL")
    )
    coverage_score = passing / len(contributions) if contributions else 0.0
    veto_rate      = veto_total / total_cells if total_cells > 0 else 0.0

    risk_tier  = classify_risk_tier(veto_rate, coverage_score, len(contributions))
    risk_notes = build_risk_notes(veto_rate, coverage_score, len(contributions), gt_confidence)

    risk = PortfolioRiskProfile(
        veto_rate      = round(veto_rate, 6),
        coverage_score = round(coverage_score, 6),
        gt_confidence  = gt_confidence,
        scan_diversity = len(contributions),
        risk_tier      = risk_tier,
        risk_notes     = risk_notes,
    )

    score = compute_exploration_priority(
        acif_mean    = agg_acif,
        tier1_count  = tier1_total,
        total_cells  = total_cells,
        veto_count   = veto_total,
        weight_config = weight_config,
    )

    return PortfolioEntry(
        entry_id      = entry_id,
        territory     = territory,
        contributions = tuple(contributions),
        risk          = risk,
        score         = score,
        status        = PortfolioStatus.ACTIVE,
        assembled_at  = datetime.utcnow().isoformat(),
        assembled_by  = actor_id,
    )