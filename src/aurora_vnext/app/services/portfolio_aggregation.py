"""
Aurora OSI vNext — Portfolio Aggregation
Phase AD §AD.2

Aggregates stored canonical scan records into TerritoryBlock summaries.

CONSTITUTIONAL RULES:
  Rule 1: All aggregation reads stored scan records only — no recomputation.
  Rule 2: acif_mean is the stored aggregate from CanonicalScan.acif_mean_area_weighted
          or CanonicalScan.acif_mean — never recalculated here.
  Rule 3: Tier counts are summed across scans — never re-derived from ACIF.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.portfolio_model import (
    ScanContribution, TerritoryBlock, PortfolioRiskProfile,
    PortfolioScore, PortfolioEntry, RiskTier, PortfolioStatus,
)


# Fixed display weights — not part of calibration system
_W_ACIF  = 0.5
_W_TIER1 = 0.3
_W_RISK  = 0.2


# ---------------------------------------------------------------------------
# 1. Risk tier classification (from stored metrics only)
# ---------------------------------------------------------------------------

def classify_risk_tier(veto_rate: float, coverage_score: float, scan_count: int) -> RiskTier:
    """
    Classify territory risk tier from stored veto rate and coverage score.

    Rules (no ACIF used):
      LOW:    veto_rate < 0.05 AND coverage_score > 0.7 AND scan_count >= 3
      HIGH:   veto_rate > 0.30 OR coverage_score < 0.3 OR scan_count < 2
      MEDIUM: everything else
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
        notes.append(f"High veto rate ({veto_rate:.1%}) — strong geophysical constraints violated in >30% of cells")
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
            notes.append(f"Low ground-truth confidence ({gt_confidence:.2f}) — calibration uncertain")
        elif gt_confidence > 0.7:
            notes.append(f"High ground-truth confidence ({gt_confidence:.2f})")

    return tuple(notes)


# ---------------------------------------------------------------------------
# 2. Portfolio score computation
# ---------------------------------------------------------------------------

def compute_portfolio_score(
    acif_mean:    Optional[float],
    tier1_count:  int,
    total_cells:  int,
    veto_count:   int,
) -> PortfolioScore:
    """
    Compute portfolio score from stored canonical metrics.

    portfolio_score = (w_acif × acif_mean + w_tier1 × tier1_density + w_risk × (1-veto_rate))
                    / (w_acif + w_tier1 + w_risk)

    PROOF: all inputs are stored values. No ACIF is recomputed.
    acif_mean is the stored scan aggregate — not a new calculation.
    tier1_density = stored tier1_count / stored total_cells.
    veto_rate = stored veto_count / stored total_cells.
    """
    if total_cells <= 0:
        return PortfolioScore(
            raw_acif_mean   = acif_mean,
            tier1_density   = 0.0,
            veto_rate       = 0.0,
            portfolio_score = 0.0,
            portfolio_rank  = None,
            weights_used    = {"w_acif": _W_ACIF, "w_tier1": _W_TIER1, "w_risk": _W_RISK},
        )

    tier1_density = tier1_count / total_cells
    veto_rate     = veto_count / total_cells
    acif_val      = acif_mean if acif_mean is not None else 0.0

    score = (
        _W_ACIF  * acif_val +
        _W_TIER1 * tier1_density +
        _W_RISK  * (1.0 - veto_rate)
    ) / (_W_ACIF + _W_TIER1 + _W_RISK)

    return PortfolioScore(
        raw_acif_mean   = acif_mean,
        tier1_density   = round(tier1_density, 6),
        veto_rate       = round(veto_rate, 6),
        portfolio_score = round(score, 6),
        portfolio_rank  = None,           # set during cohort ranking
        weights_used    = {"w_acif": _W_ACIF, "w_tier1": _W_TIER1, "w_risk": _W_RISK},
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
) -> PortfolioEntry:
    """
    Assemble a PortfolioEntry from a set of ScanContributions.
    All numeric aggregation uses stored canonical values.
    """
    from datetime import datetime

    if not contributions:
        raise ValueError(f"PortfolioEntry {entry_id}: no scan contributions provided.")

    # Aggregate stored values — no recomputation
    total_cells  = sum(c.total_cells for c in contributions)
    tier1_total  = sum(c.tier_1_count for c in contributions)
    veto_total   = sum(c.veto_count for c in contributions)

    # acif_mean: weighted average of stored acif_mean per scan by cell count
    acif_vals = [(c.acif_mean, c.total_cells) for c in contributions if c.acif_mean is not None]
    if acif_vals and total_cells > 0:
        weighted_sum = sum(v * w for v, w in acif_vals)
        weight_total = sum(w for _, w in acif_vals)
        agg_acif = weighted_sum / weight_total if weight_total > 0 else None
    else:
        agg_acif = None

    # Coverage score: proxy — fraction of scans with PASS_CONFIRMED or PARTIAL_SIGNAL
    passing = sum(
        1 for c in contributions
        if c.system_status in ("PASS_CONFIRMED", "PARTIAL_SIGNAL")
    )
    coverage_score = passing / len(contributions) if contributions else 0.0

    veto_rate = veto_total / total_cells if total_cells > 0 else 0.0

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

    score = compute_portfolio_score(agg_acif, tier1_total, total_cells, veto_total)

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