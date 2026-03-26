"""
Aurora OSI vNext — Portfolio & Territory Intelligence Model
Phase AD §AD.1 (Corrected)

CORRECTIONS APPLIED:
  - portfolio_score renamed to exploration_priority_index
  - PortfolioWeightConfig added — all weights versioned, configurable, auditable
  - No hard-coded weight constants in this module

CONSTITUTIONAL RULES:
  Rule 1: exploration_priority_index is an AGGREGATION of stored canonical outputs.
          It is NOT a geological score, deposit probability, or ACIF value.
          It must be labeled explicitly as a non-physical aggregation metric.
  Rule 2: All numeric inputs come from stored scan records — never recomputed.
  Rule 3: PortfolioWeightConfig must be persisted and versioned. Any change to
          weights creates a new PortfolioWeightConfig version.
  Rule 4: All result types are frozen and immutable after assembly.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class PortfolioStatus(str, Enum):
    ACTIVE   = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class PortfolioWeightConfig:
    """
    Versioned, auditable configuration for exploration_priority_index weights.

    CORRECTION: replaces hard-coded constants _W_ACIF, _W_TIER1, _W_RISK.
    Every change to weights creates a new PortfolioWeightConfig with a new version_id.
    The version_id is stored in PortfolioScore.weight_config_version for full auditability.

    Formula:
      exploration_priority_index = (
          w_acif_mean   × normalised_acif_mean   +
          w_tier1_density × tier1_density         +
          w_veto_compliance × (1 − veto_rate)
      ) / (w_acif_mean + w_tier1_density + w_veto_compliance)

    Constraint: w_acif_mean + w_tier1_density + w_veto_compliance must sum to 1.0.

    DOCUMENTATION NOTE:
      exploration_priority_index is a non-physical aggregation metric.
      It combines stored canonical outputs for prioritisation purposes only.
      It is not a geological score, deposit probability, resource estimate,
      or ACIF value. It does not trigger any scan-level recomputation.

    Fields:
      version_id:       unique identifier for this weight configuration
      description:      human-readable description of what this version changes
      w_acif_mean:      weight for stored acif_mean ∈ (0, 1)
      w_tier1_density:  weight for tier1_count/total_cells ∈ (0, 1)
      w_veto_compliance: weight for (1 - veto_rate) ∈ (0, 1)
      created_at:       ISO 8601 UTC
      created_by:       actor who created this config version
      parent_version_id: the prior active config (None for genesis)
    """
    version_id:           str
    description:          str
    w_acif_mean:          float
    w_tier1_density:      float
    w_veto_compliance:    float
    created_at:           str
    created_by:           str
    parent_version_id:    Optional[str] = None

    LABEL: str = (
        "exploration_priority_index — non-physical aggregation metric. "
        "Combines stored canonical outputs for prioritisation only. "
        "Not a geological score, ACIF value, or resource estimate."
    )

    def __post_init__(self):
        total = self.w_acif_mean + self.w_tier1_density + self.w_veto_compliance
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"PortfolioWeightConfig weights must sum to 1.0, "
                f"got {total:.6f} (w_acif_mean={self.w_acif_mean}, "
                f"w_tier1_density={self.w_tier1_density}, "
                f"w_veto_compliance={self.w_veto_compliance})"
            )
        for name, val in [
            ("w_acif_mean", self.w_acif_mean),
            ("w_tier1_density", self.w_tier1_density),
            ("w_veto_compliance", self.w_veto_compliance),
        ]:
            if not (0.0 < val < 1.0):
                raise ValueError(
                    f"PortfolioWeightConfig.{name} must be in (0, 1), got {val}"
                )


# Default weight config — genesis version. Must be persisted on first use.
DEFAULT_WEIGHT_CONFIG = PortfolioWeightConfig(
    version_id        = "pwc-default-v1",
    description       = "Default exploration priority weights: acif_mean 0.5, tier1_density 0.3, veto_compliance 0.2",
    w_acif_mean       = 0.5,
    w_tier1_density   = 0.3,
    w_veto_compliance = 0.2,
    created_at        = "2026-03-26T00:00:00",
    created_by        = "system",
    parent_version_id = None,
)


@dataclass(frozen=True)
class ScanContribution:
    """
    Summary of one canonical scan's contribution to a territory portfolio entry.
    All values sourced verbatim from stored CanonicalScan records.
    """
    scan_id:             str
    commodity:           str
    acif_mean:           Optional[float]
    tier_1_count:        int
    tier_2_count:        int
    tier_3_count:        int
    total_cells:         int
    veto_count:          int
    system_status:       str
    completed_at:        str
    calibration_version: str
    aoi_id:              Optional[str]
    geometry_hash:       Optional[str]


@dataclass(frozen=True)
class TerritoryBlock:
    """Geographic territory unit for portfolio intelligence."""
    block_id:       str
    block_name:     str
    territory_type: TerritoryType
    country_code:   str
    commodity:      str
    geometry_wkt:   Optional[str]
    area_km2:       Optional[float]
    scan_count:     int
    scan_ids:       tuple[str, ...]


@dataclass(frozen=True)
class PortfolioRiskProfile:
    """
    Risk profile assembled from stored canonical outputs — not from recomputation.
    risk_tier derived from veto_rate and coverage only.
    """
    veto_rate:       float
    coverage_score:  float
    gt_confidence:   Optional[float]
    scan_diversity:  int
    risk_tier:       RiskTier
    risk_notes:      tuple[str, ...]


@dataclass(frozen=True)
class PortfolioScore:
    """
    exploration_priority_index and supporting metrics for one territory.

    CORRECTION: field renamed from portfolio_score to exploration_priority_index.

    DOCUMENTATION (constitutional requirement):
      exploration_priority_index is a NON-PHYSICAL AGGREGATION METRIC.
      It combines stored canonical outputs (acif_mean, tier1_density, veto compliance)
      using configurable weights from PortfolioWeightConfig.
      It is NOT a geological score, deposit probability, resource estimate, or ACIF value.
      It does not recompute any scan-level scientific output.
      It is intended for exploration prioritisation and portfolio management only.

    weight_config_version: the PortfolioWeightConfig.version_id used to compute this score.
    """
    raw_acif_mean:               Optional[float]   # stored aggregate verbatim
    tier1_density:               float              # tier1_count / total_cells (stored)
    veto_rate:                   float              # veto_count / total_cells (stored)
    exploration_priority_index:  float              # ∈ [0, 1] — non-physical aggregation
    exploration_priority_rank:   Optional[int]      # rank within cohort
    weight_config_version:       str                # PortfolioWeightConfig.version_id
    weights_used:                dict               # {"w_acif_mean": f, "w_tier1_density": f, ...}
    metric_label:                str = (            # must always be present on output
        "exploration_priority_index — non-physical aggregation metric. "
        "Not a geological score or ACIF value."
    )


@dataclass(frozen=True)
class PortfolioEntry:
    """
    Complete portfolio intelligence record for one territory/commodity pair.
    All scientific values sourced verbatim from stored canonical records.
    """
    entry_id:       str
    territory:      TerritoryBlock
    contributions:  tuple[ScanContribution, ...]
    risk:           PortfolioRiskProfile
    score:          PortfolioScore
    status:         PortfolioStatus
    assembled_at:   str
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
    Complete portfolio view across multiple territory/commodity entries.
    snapshot_id: SHA-256 of sorted entry IDs — stable for identical entry sets.
    """
    snapshot_id:         str
    commodity:           Optional[str]
    territory_type:      Optional[TerritoryType]
    entries:             tuple[PortfolioEntry, ...]
    generated_at:        str
    total_entries:       int
    risk_summary:        dict
    weight_config:       PortfolioWeightConfig    # config used for this snapshot