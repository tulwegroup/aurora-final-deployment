"""
Aurora OSI vNext — Scan Cost Model
Phase AG §AG.1

Models the computational and operational cost of a scan in terms of:
  - cost per km²
  - cost per resolution tier (micro, small, medium, large, xlarge)
  - cost per cell count estimate
  - parallel execution discount factor

CONSTITUTIONAL RULES:
  Rule 1: Cost model is pure infrastructure metadata.
          No scientific constants, no ACIF formula, no tier derivation.
  Rule 2: Benchmark values (e.g. Yilgarn ACIF mean) must NEVER appear in
          cost computation. Cost is based on AOI geometry and resolution only.
  Rule 3: Validation detection rates (Phase AF) must not trigger implicit
          recalibration or cost curve adjustment.
  Rule 4: All cost estimates are advisory — they do not alter canonical outputs.
  Rule 5: No import from core/*.

BENCHMARK USAGE CONSTRAINT (Phase AG approval condition):
  Yilgarn benchmark and other Phase AF reference values are DESCRIPTIVE ONLY.
  They are never used to rescale ACIF, adjust thresholds, or derive cost constants.
  Cost constants below are derived from infrastructure measurement only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResolutionTier(str, Enum):
    MICRO  = "micro"    # ≤ 50 km²  — exploratory
    SMALL  = "small"    # 50–500 km²
    MEDIUM = "medium"   # 500–5 000 km²
    LARGE  = "large"    # 5 000–50 000 km²
    XLARGE = "xlarge"   # > 50 000 km²  — country scale


# ---------------------------------------------------------------------------
# Infrastructure cost constants
# These are derived from cloud compute pricing (AWS, 2026-Q1) and internal
# cell processing benchmarks — not from any scientific measurement.
# ---------------------------------------------------------------------------

# Base compute cost per cell (USD) — includes GPU inference + S3 read/write
_COST_PER_CELL_USD = 0.00012   # $0.12 per 1000 cells

# Resolution multiplier — higher resolution = more overlapping sensor reads
_RESOLUTION_MULTIPLIER = {
    "low":      0.6,
    "standard": 1.0,
    "high":     1.8,
    "ultra":    3.2,
}

# Parallel execution discount (fraction of serial cost) — from measured AWS Batch throughput
_PARALLEL_DISCOUNT = {
    1:   1.00,   # serial — no discount
    2:   0.90,   # 2 workers
    4:   0.78,   # 4 workers
    8:   0.65,   # 8 workers
    16:  0.55,   # 16 workers
    32:  0.48,   # 32 workers (approximately linear at this scale)
}

# Cell density per km² by resolution (cells/km²) — geometry-based, not scientific
_CELLS_PER_KM2 = {
    "low":      0.5,    # 2 km cells
    "standard": 4.0,    # 500 m cells
    "high":     16.0,   # 250 m cells
    "ultra":    64.0,   # 125 m cells
}

# Cost tier classification by estimated USD cost
_COST_TIER_BANDS_USD = [
    (0,    5,    "micro"),
    (5,    50,   "small"),
    (50,   500,  "medium"),
    (500,  5000, "large"),
    (5000, None, "xlarge"),
]


@dataclass(frozen=True)
class ScanCostEstimate:
    """
    Cost estimate for one scan configuration.
    All values are advisory — they do not affect canonical scan outputs.
    """
    aoi_area_km2:          float
    resolution:            str
    estimated_cells:       int
    cost_per_cell_usd:     float
    resolution_multiplier: float
    estimated_cost_usd:    float
    cost_per_km2_usd:      float
    cost_tier:             str           # "micro" | "small" | "medium" | "large" | "xlarge"
    parallel_workers:      int
    parallel_discount:     float
    parallel_cost_usd:     float          # estimated_cost_usd × parallel_discount
    notes:                 tuple[str, ...]


@dataclass(frozen=True)
class CostModelSummary:
    """Summary across multiple scan configurations or AOIs."""
    total_area_km2:     float
    total_cells:        int
    serial_cost_usd:    float
    parallel_cost_usd:  float
    parallel_workers:   int
    savings_usd:        float
    savings_pct:        float
    scans_estimated:    int


def _classify_cost_tier(cost_usd: float) -> str:
    for lo, hi, label in _COST_TIER_BANDS_USD:
        if hi is None or cost_usd < hi:
            if cost_usd >= lo:
                return label
    return "xlarge"


def _parallel_discount_factor(workers: int) -> float:
    """Return the discount factor for the nearest configured worker count."""
    keys = sorted(_PARALLEL_DISCOUNT.keys())
    best = keys[0]
    for k in keys:
        if workers >= k:
            best = k
    return _PARALLEL_DISCOUNT[best]


def estimate_scan_cost(
    aoi_area_km2:     float,
    resolution:       str = "standard",
    parallel_workers: int = 1,
) -> ScanCostEstimate:
    """
    Estimate the cost of a single scan.

    Args:
      aoi_area_km2:     AOI area in km² (from stored geometry, not recomputed)
      resolution:       "low" | "standard" | "high" | "ultra"
      parallel_workers: number of parallel workers (for discount calculation)

    Returns:
      ScanCostEstimate — advisory only, does not modify any canonical record.

    PROOF: uses only infrastructure constants and AOI geometry.
    No scientific constants, no ACIF, no tier derivation.
    """
    cells_per_km2 = _CELLS_PER_KM2.get(resolution, _CELLS_PER_KM2["standard"])
    res_mult      = _RESOLUTION_MULTIPLIER.get(resolution, 1.0)

    estimated_cells  = max(1, int(aoi_area_km2 * cells_per_km2))
    base_cost        = estimated_cells * _COST_PER_CELL_USD
    adjusted_cost    = base_cost * res_mult
    cost_per_km2     = adjusted_cost / aoi_area_km2 if aoi_area_km2 > 0 else 0.0

    discount        = _parallel_discount_factor(parallel_workers)
    parallel_cost   = adjusted_cost * discount
    cost_tier       = _classify_cost_tier(adjusted_cost)

    notes = []
    if aoi_area_km2 > 50_000:
        notes.append("Country-scale AOI — consider tiling into sub-AOIs for optimal parallelism.")
    if parallel_workers == 1:
        notes.append("Serial execution — use parallel_workers ≥ 4 for cost reduction.")
    if resolution == "ultra":
        notes.append("Ultra resolution — 3.2× cost multiplier. Recommend for targeted drill planning only.")

    return ScanCostEstimate(
        aoi_area_km2          = round(aoi_area_km2, 4),
        resolution            = resolution,
        estimated_cells       = estimated_cells,
        cost_per_cell_usd     = _COST_PER_CELL_USD,
        resolution_multiplier = res_mult,
        estimated_cost_usd    = round(adjusted_cost, 4),
        cost_per_km2_usd      = round(cost_per_km2, 6),
        cost_tier             = cost_tier,
        parallel_workers      = parallel_workers,
        parallel_discount     = discount,
        parallel_cost_usd     = round(parallel_cost, 4),
        notes                 = tuple(notes),
    )


def summarise_portfolio_costs(
    aoi_configs: list[dict],   # each: {"area_km2": float, "resolution": str}
    parallel_workers: int = 8,
) -> CostModelSummary:
    """
    Summarise total cost across a portfolio of AOI configurations.

    Args:
      aoi_configs: list of {"area_km2": float, "resolution": str}
      parallel_workers: workers available for parallel execution

    Returns:
      CostModelSummary — total and per-run cost breakdown.
    """
    estimates = [
        estimate_scan_cost(c["area_km2"], c.get("resolution", "standard"), 1)
        for c in aoi_configs
    ]
    total_area  = sum(e.aoi_area_km2 for e in estimates)
    total_cells = sum(e.estimated_cells for e in estimates)
    serial_cost = sum(e.estimated_cost_usd for e in estimates)
    discount    = _parallel_discount_factor(parallel_workers)
    par_cost    = serial_cost * discount
    savings     = serial_cost - par_cost

    return CostModelSummary(
        total_area_km2    = round(total_area, 4),
        total_cells       = total_cells,
        serial_cost_usd   = round(serial_cost, 4),
        parallel_cost_usd = round(par_cost, 4),
        parallel_workers  = parallel_workers,
        savings_usd       = round(savings, 4),
        savings_pct       = round((savings / serial_cost * 100) if serial_cost > 0 else 0, 2),
        scans_estimated   = len(estimates),
    )