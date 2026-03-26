"""
Aurora OSI vNext — Portfolio Ranking
Phase AD §AD.3

Ranks and snapshots a set of PortfolioEntry records.

CONSTITUTIONAL RULES:
  Rule 1: Ranking is based on portfolio_score only — which is itself
          an aggregation of stored canonical metrics (ACIF mean, tier1 density,
          veto rate). No ACIF is recomputed during ranking.
  Rule 2: Risk-adjusted ranking applies a penalty only from stored risk_tier
          (derived from stored veto_rate and coverage). No scientific re-evaluation.
  Rule 3: PortfolioSnapshot is immutable after assembly.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from typing import Optional

from app.models.portfolio_model import (
    PortfolioEntry, PortfolioScore, PortfolioSnapshot, RiskTier,
    TerritoryType,
)


# Risk-adjusted penalty applied to portfolio_score for ranking only (display only)
_RISK_PENALTY = {
    RiskTier.LOW:    0.0,
    RiskTier.MEDIUM: 0.05,
    RiskTier.HIGH:   0.15,
}


def _risk_adjusted_score(entry: PortfolioEntry) -> float:
    """
    Apply risk penalty to portfolio_score for ranking purposes.

    risk_adjusted = portfolio_score - penalty[risk_tier]

    PROOF: penalty is applied to the display composite (portfolio_score).
    It does not alter acif_mean, tier counts, or any stored canonical field.
    """
    penalty = _RISK_PENALTY.get(entry.risk.risk_tier, 0.0)
    return max(0.0, entry.score.portfolio_score - penalty)


def rank_entries(
    entries: list[PortfolioEntry],
    risk_adjusted: bool = True,
) -> list[PortfolioEntry]:
    """
    Sort and assign portfolio_rank to entries.

    Args:
      entries:       List of PortfolioEntry to rank.
      risk_adjusted: If True, applies risk penalty before sorting.

    Returns:
      New list of PortfolioEntry (frozen) with portfolio_rank set.
      Original entries are NOT modified.

    PROOF: ranking is a read operation on stored portfolio scores.
    No canonical scan record is touched.
    """
    if not entries:
        return []

    key_fn = _risk_adjusted_score if risk_adjusted else (lambda e: e.score.portfolio_score)
    sorted_entries = sorted(entries, key=key_fn, reverse=True)

    # Assign rank — creates new PortfolioScore with portfolio_rank set
    ranked: list[PortfolioEntry] = []
    for rank, entry in enumerate(sorted_entries, start=1):
        new_score = PortfolioScore(
            raw_acif_mean   = entry.score.raw_acif_mean,
            tier1_density   = entry.score.tier1_density,
            veto_rate       = entry.score.veto_rate,
            portfolio_score = entry.score.portfolio_score,
            portfolio_rank  = rank,
            weights_used    = entry.score.weights_used,
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
    """SHA-256 of sorted entry IDs — stable for identical entry sets."""
    payload = json.dumps(sorted(entry_ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def build_snapshot(
    entries:        list[PortfolioEntry],
    commodity:      Optional[str] = None,
    territory_type: Optional[TerritoryType] = None,
    risk_adjusted:  bool = True,
) -> PortfolioSnapshot:
    """
    Build a PortfolioSnapshot from a list of PortfolioEntry records.
    Entries are ranked and frozen into the snapshot.
    """
    ranked = rank_entries(entries, risk_adjusted=risk_adjusted)

    risk_summary = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for e in ranked:
        risk_summary[e.risk.risk_tier.value.upper()] = (
            risk_summary.get(e.risk.risk_tier.value.upper(), 0) + 1
        )

    return PortfolioSnapshot(
        snapshot_id    = _snapshot_id([e.entry_id for e in ranked]),
        commodity      = commodity,
        territory_type = territory_type,
        entries        = tuple(ranked),
        generated_at   = datetime.utcnow().isoformat(),
        total_entries  = len(ranked),
        risk_summary   = risk_summary,
    )