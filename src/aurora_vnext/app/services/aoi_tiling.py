"""
Aurora OSI vNext — AOI Tiling & Workload Estimator
Phase AA §AA.3

Estimates scan workload for a validated AOI.

Produces:
  - Estimated cell count
  - Cost tier
  - Resolution options
  - Offshore/onshore cell split

CONSTITUTIONAL RULE: This service computes infrastructure metadata only
(cell count, resolution, cost tier). It performs no scientific scoring,
ACIF computation, or tier assignment. All estimates are workload figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResolutionTier(str, Enum):
    FINE    = "fine"       # ~1 km² per cell
    MEDIUM  = "medium"     # ~5 km² per cell
    COARSE  = "coarse"     # ~25 km² per cell
    SURVEY  = "survey"     # ~100 km² per cell — regional reconnaissance


class CostTier(str, Enum):
    MICRO   = "micro"      # < 100 cells
    SMALL   = "small"      # 100–1,000 cells
    MEDIUM  = "medium"     # 1,000–10,000 cells
    LARGE   = "large"      # 10,000–100,000 cells
    XLARGE  = "xlarge"     # > 100,000 cells


_CELL_SIZE_KM2: dict[ResolutionTier, float] = {
    ResolutionTier.FINE:   1.0,
    ResolutionTier.MEDIUM: 5.0,
    ResolutionTier.COARSE: 25.0,
    ResolutionTier.SURVEY: 100.0,
}


def _cost_tier(cell_count: int) -> CostTier:
    if cell_count < 100:        return CostTier.MICRO
    if cell_count < 1_000:      return CostTier.SMALL
    if cell_count < 10_000:     return CostTier.MEDIUM
    if cell_count < 100_000:    return CostTier.LARGE
    return CostTier.XLARGE


@dataclass(frozen=True)
class TilingEstimate:
    resolution:         ResolutionTier
    cell_size_km2:      float
    estimated_cells:    int
    cost_tier:          CostTier
    area_km2:           float
    offshore_fraction:  Optional[float]   # fraction of area that is offshore (heuristic)
    estimated_onshore_cells:  int
    estimated_offshore_cells: int


@dataclass(frozen=True)
class WorkloadPreview:
    area_km2:   float
    options:    list[TilingEstimate]
    default_resolution: ResolutionTier


def estimate_workload(
    area_km2: float,
    offshore_fraction: float = 0.0,
) -> WorkloadPreview:
    """
    Produce a WorkloadPreview for all available resolution tiers.

    offshore_fraction: [0, 1] — fraction of cells estimated to be offshore.
    Returns options sorted from finest to coarsest.
    """
    options: list[TilingEstimate] = []

    for resolution in [
        ResolutionTier.FINE, ResolutionTier.MEDIUM,
        ResolutionTier.COARSE, ResolutionTier.SURVEY,
    ]:
        cell_size = _CELL_SIZE_KM2[resolution]
        total = max(1, int(area_km2 / cell_size))
        offshore = int(total * max(0.0, min(1.0, offshore_fraction)))
        onshore  = total - offshore
        options.append(TilingEstimate(
            resolution               = resolution,
            cell_size_km2            = cell_size,
            estimated_cells          = total,
            cost_tier                = _cost_tier(total),
            area_km2                 = area_km2,
            offshore_fraction        = offshore_fraction,
            estimated_onshore_cells  = onshore,
            estimated_offshore_cells = offshore,
        ))

    # Default: MEDIUM unless area is very small (< 50 km²) → FINE
    default = ResolutionTier.FINE if area_km2 < 50 else ResolutionTier.MEDIUM

    return WorkloadPreview(
        area_km2           = area_km2,
        options            = options,
        default_resolution = default,
    )