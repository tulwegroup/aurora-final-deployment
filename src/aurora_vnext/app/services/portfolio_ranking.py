"""
Aurora OSI vNext — Portfolio Ranking
Phase AD §AD.3 (Corrected)

CORRECTIONS APPLIED:
  - exploration_priority_index replaces portfolio_score throughout
  - Weight config passed through to snapshot for full auditability

CONSTITUTIONAL RULES:
  Rule 1: Ranking based on exploration_priority_index — a non-physical aggregation metric.
  Rule 2: Risk-adjusted ranking applies penalty from stored risk_tier only.
  Rule 3: PortfolioSnapshot is immutable after assembly.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from app.models.portfolio_model import (
    PortfolioEntry, PortfolioScore, PortfolioSnapshot, RiskTier,
    TerritoryType, PortfolioWeightConfig, DEFAULT_WEIGHT_CONFIG,
)

_RISK_PENALTY = {
    RiskTier.LOW:    0.0,
    RiskTier.MEDIUM: 0.05,
    RiskTier.HIGH:   0.15,
}


def _risk_adjusted_index(entry: PortfolioEntry) -> float:
    """
    Apply risk penalty to exploration_priority_index for ranking purposes.
    Does not alter stored canonical fields.
    """
    penalty = _RISK_PENALTY.get(entry.risk.risk_tier, 0.0)
    return max(0.0, entry.score.exploration_priority_index - penalty)


def rank_entries(
    entries:       list[PortfolioEntry],
    risk_adjusted: bool = True,
) -> list[PortfolioEntry]:
    """
    Sort and assign exploration_priority_rank to entries.
    Creates new frozen PortfolioScore per entry with rank set.
    Original entries not modified.
    """
    if not entries:
        return []

    key_fn = _risk_adjusted_index if risk_adjusted else (
        lambda e: e.score.exploration_priority_index
    )
    sorted_entries = sorted(entries, key=key_fn, reverse=True)

    ranked: list[PortfolioEntry] = []
    for rank, entry in enumerate(sorted_entries, start=1):
        new_score = PortfolioScore(
            raw_acif_mean              = entry.score.raw_acif_mean,
            tier1_density              = entry.score.tier1_density,
            veto_rate                  = entry.score.veto_rate,
            exploration_priority_index = entry.score.exploration_priority_index,
            exploration_priority_rank  = rank,
            weight_config_version      = entry.score.weight_config_version,
            weights_used               = entry.score.weights_used,
        )
        ranked.append(PortfolioEntry(
            entry_id      = entry.entry_id,
            territory     = entry.territory,
            contributions = entry.contributions,
            risk          = entry.risk,
            score         = new_score,
            status        = entry.status,
            assembled_at  = entry.assembled_at,
            assembled_by  = entry.assembled_by,
        ))
    return ranked


def _snapshot_id(entry_ids: list[str]) -> str:
    payload = json.dumps(sorted(entry_ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def build_snapshot(
    entries:        list[PortfolioEntry],
    commodity:      Optional[str] = None,
    territory_type: Optional[TerritoryType] = None,
    risk_adjusted:  bool = True,
    weight_config:  PortfolioWeightConfig = DEFAULT_WEIGHT_CONFIG,
) -> PortfolioSnapshot:
    """Build a ranked, frozen PortfolioSnapshot."""
    ranked = rank_entries(entries, risk_adjusted=risk_adjusted)

    risk_summary = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for e in ranked:
        k = e.risk.risk_tier.value.upper()
        risk_summary[k] = risk_summary.get(k, 0) + 1

    return PortfolioSnapshot(
        snapshot_id    = _snapshot_id([e.entry_id for e in ranked]),
        commodity      = commodity,
        territory_type = territory_type,
        entries        = tuple(ranked),
        generated_at   = datetime.utcnow().isoformat(),
        total_entries  = len(ranked),
        risk_summary   = risk_summary,
        weight_config  = weight_config,
    )