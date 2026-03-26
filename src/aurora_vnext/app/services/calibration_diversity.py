"""
Aurora OSI vNext — Calibration Ground-Truth Diversity Validator
Phase AC additional constraint (applied at Phase AD)

Enforces minimum diversity requirements on the ground-truth record set
before any calibration run is accepted.

Diversity constraints:
  1. Minimum unique sources:    ≥ MIN_UNIQUE_SOURCES distinct provenance source_names
  2. Minimum spatial dispersion: centroid spread ≥ MIN_SPATIAL_DISPERSION_DEG
                                  (great-circle distance between most distant pair)
  3. Minimum geological variation: ≥ MIN_GEOLOGICAL_TYPES distinct geological_data_types

  If any constraint is not met, CalibrationDiversityError is raised.
  Calibration run MUST NOT proceed.

CONSTITUTIONAL RULES:
  Rule 1: Diversity is an infrastructure validation — no scientific scoring.
  Rule 2: Spatial dispersion uses great-circle distance (Haversine) — geometry only.
  Rule 3: Constraints are commodity-scoped — checked per (commodity, province) set.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# Minimum requirements
MIN_UNIQUE_SOURCES       = 2     # unique provenance source_name values
MIN_SPATIAL_DISPERSION_DEG = 0.5  # degrees great-circle between most distant pair
MIN_GEOLOGICAL_TYPES     = 2     # distinct geological_data_type values


class CalibrationDiversityError(ValueError):
    """
    Raised when GT record set does not meet diversity requirements.
    Calibration run must not proceed.
    """


@dataclass(frozen=True)
class DiversityReport:
    """Result of a diversity check — contains pass/fail + metrics for each constraint."""
    commodity:               str
    n_records:               int
    unique_sources:          int
    unique_geological_types: int
    spatial_dispersion_deg:  float
    sources_ok:              bool
    spatial_ok:              bool
    geological_ok:           bool
    errors:                  tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.sources_ok and self.spatial_ok and self.geological_ok


def _haversine_deg(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in degrees between two WGS84 points."""
    R = 6371.0  # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km = R * c
    return km / 111.0   # approximate degrees


def _max_spatial_dispersion(records: list[dict]) -> float:
    """
    Compute the maximum pairwise great-circle distance (in degrees) between
    all GT records that have lat/lon. Returns 0.0 if fewer than 2 located records.
    """
    located = [(r["lat"], r["lon"]) for r in records if r.get("lat") and r.get("lon")]
    if len(located) < 2:
        return 0.0
    max_dist = 0.0
    for i in range(len(located)):
        for j in range(i + 1, len(located)):
            d = _haversine_deg(*located[i], *located[j])
            if d > max_dist:
                max_dist = d
    return max_dist


def validate_gt_diversity(
    commodity:  str,
    records:    list[dict],
    min_unique_sources:    int = MIN_UNIQUE_SOURCES,
    min_dispersion_deg:    float = MIN_SPATIAL_DISPERSION_DEG,
    min_geological_types:  int = MIN_GEOLOGICAL_TYPES,
) -> DiversityReport:
    """
    Validate diversity of GT records for a calibration run.

    Args:
      records: list of approved GT record dicts. Each must have:
        source_name, geological_data_type, and optionally lat, lon.
      commodity: commodity being calibrated (for logging and error messages).

    Returns:
      DiversityReport — call report.passed to check overall result.
      Do NOT proceed with calibration if report.passed is False.
    """
    errors = []

    # 1. Unique sources
    unique_sources = len({r.get("source_name", "") for r in records if r.get("source_name")})
    sources_ok = unique_sources >= min_unique_sources
    if not sources_ok:
        errors.append(
            f"Insufficient source diversity for {commodity}: "
            f"{unique_sources} unique source(s), minimum {min_unique_sources} required. "
            f"Ground-truth records must come from at least {min_unique_sources} independent sources."
        )

    # 2. Spatial dispersion
    dispersion = _max_spatial_dispersion(records)
    spatial_ok = dispersion >= min_dispersion_deg
    if not spatial_ok:
        errors.append(
            f"Insufficient spatial dispersion for {commodity}: "
            f"{dispersion:.3f}° max spread, minimum {min_dispersion_deg}° required. "
            f"Records are spatially clustered — calibration may be geographically biased."
        )

    # 3. Geological type variation
    unique_geo_types = len({r.get("geological_data_type", "") for r in records
                            if r.get("geological_data_type")})
    geological_ok = unique_geo_types >= min_geological_types
    if not geological_ok:
        errors.append(
            f"Insufficient geological context variation for {commodity}: "
            f"{unique_geo_types} geological type(s), minimum {min_geological_types} required. "
            f"Records should include multiple geological data types (e.g., drill + geochemical)."
        )

    return DiversityReport(
        commodity               = commodity,
        n_records               = len(records),
        unique_sources          = unique_sources,
        unique_geological_types = unique_geo_types,
        spatial_dispersion_deg  = round(dispersion, 4),
        sources_ok              = sources_ok,
        spatial_ok              = spatial_ok,
        geological_ok           = geological_ok,
        errors                  = tuple(errors),
    )


def assert_gt_diversity(
    commodity: str,
    records:   list[dict],
    **kwargs,
) -> DiversityReport:
    """
    Run diversity validation and raise CalibrationDiversityError if it fails.
    Call this at the start of CalibrationExecutor.run() before any math.
    """
    report = validate_gt_diversity(commodity, records, **kwargs)
    if not report.passed:
        raise CalibrationDiversityError(
            f"Calibration diversity requirements not met for {commodity}:\n"
            + "\n".join(f"  - {e}" for e in report.errors)
        )
    return report