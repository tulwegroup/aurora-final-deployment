"""
Aurora OSI vNext — Portfolio & Territory Intelligence Model
Phase AD §AD.1

Defines all data structures for portfolio-level aggregation and ranking.

CONSTITUTIONAL RULES:
  Rule 1: Portfolio scores are AGGREGATIONS of stored canonical outputs only.
          No ACIF is recomputed. No tier is reassigned at portfolio time.
  Rule 2: All numeric inputs to portfolio scoring come from stored scan records
          (acif_mean, tier_counts, scan counts, veto rates).
  Rule 3: Portfolio rank is a relative ordering metric — not a scientific score.
          It must never be presented as a new ACIF or deposit certainty.
  Rule 4: TerritoryBlock and PortfolioEntry are frozen and immutable after assembly.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TerritoryType(str, Enum):
    COUNTRY    = "country"
    BASIN      = "basin"
    BLOCK      = "block"
    CONCESSION = "concession"
    PROVINCE   = "province"


class RiskTier(str, Enum):
    """
    Portfolio risk classification — derived from veto rate and coverage metrics only.
    NOT derived from ACIF scores.
    """
    LOW    = "low"       # low veto rate, high coverage, multiple confirmatory scans
    MEDIUM = "medium"    # moderate veto rate or limited scan count
    HIGH   = "high"      # high veto rate, low coverage, sparse GT grounding


class PortfolioStatus(str, Enum):
    ACTIVE   = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class ScanContribution:
    """
    Summary of one canonical scan's contribution to a territory portfolio entry.

    All values sourced verbatim from stored CanonicalScan records.
    No recomputation occurs here.
    """
    scan_id:             str
    commodity:           str
    acif_mean:           Optional[float]    # stored aggregate — NOT recomputed
    tier_1_count:        int                # stored tier count
    tier_2_count:        int
    tier_3_count:        int
    total_cells:         int
    veto_count:          int                # stored veto count
    system_status:       str                # stored verbatim
    completed_at:        str
    calibration_version: str
    aoi_id:              Optional[str]
    geometry_hash:       Optional[str]


@dataclass(frozen=True)
class TerritoryBlock:
    """
    A geographic territory unit for portfolio intelligence.

    Contains aggregated statistics assembled from stored scan records.
    geometry_wkt: well-known text of the territory boundary (for map display).
    """
    block_id:       str
    block_name:     str
    territory_type: TerritoryType
    country_code:   str        # ISO 3166-1 alpha-2
    commodity:      str
    geometry_wkt:   Optional[str]
    area_km2:       Optional[float]
    scan_count:     int
    scan_ids:       tuple[str, ...]


@dataclass(frozen=True)
class PortfolioRiskProfile:
    """
    Risk profile assembled from stored canonical outputs — not from scientific recomputation.

    veto_rate:       fraction of cells with any_veto_fired = True (aggregated, stored)
    coverage_score:  fraction of cells with full observable coverage (stored)
    gt_confidence:   aggregate confidence of associated GT records (from GT store)
    scan_diversity:  number of independent scans covering this territory
    risk_tier:       LOW | MEDIUM | HIGH — derived from veto_rate and coverage only
    """
    veto_rate:       float     # ∈ [0, 1]
    coverage_score:  float     # ∈ [0, 1]
    gt_confidence:   Optional[float]   # aggregate GT weight — may be None if no GT records
    scan_diversity:  int               # unique scan count
    risk_tier:       RiskTier
    risk_notes:      tuple[str, ...]   # human-readable risk observations


@dataclass(frozen=True)
class PortfolioScore:
    """
    Portfolio score for one territory.

    PROOF: this is a COMPOSITE of stored canonical metrics — not a new scientific score.

    formula:
      portfolio_score = (
          w_acif  × normalised_acif_mean     +
          w_tier1 × tier1_density            +
          w_risk  × (1 - veto_rate)
      ) / (w_acif + w_tier1 + w_risk)

    Where:
      normalised_acif_mean = acif_mean (already ∈ [0,1])
      tier1_density        = tier1_count / total_cells (∈ [0,1])
      veto_rate            = veto_cells / total_cells (∈ [0,1])
      w_acif = 0.5, w_tier1 = 0.3, w_risk = 0.2  (fixed weights — not calibrated)

    CONSTITUTIONAL NOTE: w_acif, w_tier1, w_risk are DISPLAY weights only.
    They combine stored metrics for ranking purposes.
    They do not affect any canonical scan record.
    They are not part of the calibration system.
    """
    raw_acif_mean:      Optional[float]    # stored aggregate verbatim
    tier1_density:      float              # tier1_count / total_cells
    veto_rate:          float              # veto_count / total_cells
    portfolio_score:    float              # composite ∈ [0, 1]
    portfolio_rank:     Optional[int]      # rank within cohort (set at cohort assembly time)
    weights_used:       dict               # {"w_acif": 0.5, "w_tier1": 0.3, "w_risk": 0.2}


@dataclass(frozen=True)
class PortfolioEntry:
    """
    Complete portfolio intelligence record for one territory/commodity pair.

    Assembles TerritoryBlock + ScanContributions + RiskProfile + PortfolioScore.
    All scientific values sourced verbatim from stored canonical records.
    """
    entry_id:       str
    territory:      TerritoryBlock
    contributions:  tuple[ScanContribution, ...]   # all contributing scans
    risk:           PortfolioRiskProfile
    score:          PortfolioScore
    status:         PortfolioStatus
    assembled_at:   str      # ISO 8601 UTC — when this entry was assembled
    assembled_by:   str

    @property
    def scan_count(self) -> int:
        return len(self.contributions)

    @property
    def latest_scan_date(self) -> Optional[str]:
        dates = [c.completed_at for c in self.contributions if c.completed_at]
        return max(dates) if dates else None

    @property
    def tier1_total(self) -> int:
        return sum(c.tier_1_count for c in self.contributions)

    @property
    def total_cells_all(self) -> int:
        return sum(c.total_cells for c in self.contributions)


@dataclass(frozen=True)
class PortfolioSnapshot:
    """
    A complete portfolio view across multiple territory/commodity entries.
    Entries are ranked by portfolio_score descending.
    snapshot_id is a SHA-256 of the sorted entry IDs — stable for identical entry sets.
    """
    snapshot_id:   str
    commodity:     Optional[str]    # None = all commodities
    territory_type: Optional[TerritoryType]
    entries:       tuple[PortfolioEntry, ...]   # ranked, highest score first
    generated_at:  str
    total_entries: int
    risk_summary:  dict    # {"LOW": n, "MEDIUM": n, "HIGH": n}