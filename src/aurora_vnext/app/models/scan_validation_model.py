"""
Aurora OSI vNext — Scan Validation Models
Phase AU §AU.1 | Part A — Scan Validation Framework

CONSTITUTIONAL RULES:
  Rule 1: These models carry NO scientific computation.
          Validation is observational — counting nulls, measuring uniqueness, etc.
  Rule 2: Validation summary is appended to CanonicalScan at canonical freeze time.
          It is read-only thereafter (immutable).
  Rule 3: Validation status is NOT used to modify ACIF, tiers, or gates.
          Validation is purely informational for user trust + debugging.

Outputs:
  - SensorCoverageReport: per-modality data availability (%)
  - ObservableDistributionReport: per-observable null counts, range, uniqueness
  - VectorIntegrityReport: per-cell vector uniqueness detection + duplication
  - ComponentContributionReport: ACIF component breakdown + correlation
  - ScanValidationStatus enum: VALID_FOR_RANKING | PARTIAL_MODALITY_SUPPORT | etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ScanValidationStatus(str, Enum):
    """
    CONSTITUTIONAL validation status flag for scan trustworthiness.
    
    This flag communicates to users whether the scan is safe to rank,
    or whether results should be viewed with warnings/caveats.
    """
    
    VALID_FOR_RANKING = "valid_for_ranking"
    # All major sensors present (S2, S1, thermal, DEM).
    # Observable coverage > 80%. Vector uniqueness > 90%.
    # ACIF varies naturally (not uniform). No alert flags.
    # → Safe to tier and rank alongside other scans.
    
    PARTIAL_MODALITY_SUPPORT = "partial_modality_support"
    # 2-3 modalities valid, but not all 4.
    # Example: S2 + SAR present, but no thermal or DEM data.
    # Observable coverage 50-80%. Vector uniqueness 60-90%.
    # ACIF based on incomplete signal.
    # → Present with explicit warning: "Tier assignments based on limited data."
    
    INSUFFICIENT_SPECTRAL_SUPPORT = "insufficient_spectral_support"
    # S2 coverage < 50% OR spectral indices (clay, ferric) null across ALL cells.
    # SAR/thermal may compensate, but alteration signal is missing.
    # Observable coverage < 50% for spectral modality.
    # → Tier results with warning: "Spectral alteration indices unavailable."
    
    INSUFFICIENT_DATA = "insufficient_data"
    # Multi-modal coverage < 50%. Most observables null.
    # Cannot compute reliable evidence score.
    # → Do not rank. Return with error message.
    # (User should resubmit with different AOI / resolution / date range.)


@dataclass(frozen=True)
class SensorCoverageReport:
    """Per-modality data availability and quality metrics."""
    
    total_cells: int
    
    # Sentinel-2 optical (B4, B8, B11, B12)
    s2_valid_cells: int          # cells with all 4 bands valid
    s2_coverage_pct: float       # (s2_valid_cells / total_cells) * 100
    s2_cloud_mean_pct: float     # mean cloud % across valid cells
    s2_null_cells: int           # cells with at least one null band
    
    # Sentinel-1 SAR (VV, VH)
    s1_valid_cells: int          # cells with VV + VH valid
    s1_coverage_pct: float
    s1_null_cells: int
    
    # Landsat 8/9 thermal (B10)
    thermal_valid_cells: int     # cells with B10 valid
    thermal_coverage_pct: float
    thermal_null_cells: int
    
    # SRTM DEM (elevation, slope)
    dem_valid_cells: int         # cells with elevation + slope valid
    dem_coverage_pct: float
    dem_null_cells: int
    
    # Multi-modal aggregates
    all_modalities_valid_cells: int  # cells with ALL 4 modalities present
    multi_modal_coverage_pct: float  # (all_modalities_valid_cells / total_cells) * 100
    
    # Alert flags
    s2_below_50pct: bool
    s1_below_50pct: bool
    thermal_below_50pct: bool
    dem_below_50pct: bool
    any_modality_zero_coverage: bool


@dataclass(frozen=True)
class ObservableStatistics:
    """Per-observable value statistics."""
    
    key: str                    # e.g., "x_spec_1", "x_sar_3"
    valid_cells: int           # non-null count
    coverage_pct: float        # (valid_cells / total_cells) * 100
    null_cells: int            # total_cells - valid_cells
    
    min_value: Optional[float]  # None if all null
    max_value: Optional[float]
    mean_value: Optional[float]
    stdev_value: Optional[float]
    
    unique_value_count: int    # cardinality
    repeated_value_pct: float  # % cells with most-frequent value
    
    # Alert flags
    zero_coverage: bool        # coverage_pct == 0.0
    low_coverage: bool         # coverage_pct < 50.0
    suspicious_uniform: bool   # repeated_value_pct > 80.0


@dataclass(frozen=True)
class ObservableDistributionReport:
    """Per-observable availability, range, and uniqueness."""
    
    cell_count: int
    
    # Statistics per observable (dict keyed by observable key)
    observable_stats: dict[str, ObservableStatistics]
    
    # Summary counts
    zero_coverage_count: int      # observables with 0% coverage
    low_coverage_count: int       # observables with < 50% coverage
    suspicious_uniform_count: int # observables with suspicious uniformity
    
    # Alerts — observable keys
    zero_coverage_observables: list[str]
    low_coverage_observables: list[str]
    suspicious_uniform_observables: list[str]


@dataclass(frozen=True)
class VectorDuplicationEntry:
    """One entry in duplication detection."""
    
    cell_count: int             # how many cells share this vector
    cell_ids: list[str]         # which cells
    vector_hash: str            # hash of the vector


@dataclass(frozen=True)
class VectorIntegrityReport:
    """Per-cell vector uniqueness and duplication detection."""
    
    cell_count: int
    
    # Raw observables
    raw_vector_uniqueness_pct: float
    raw_vector_duplicates: list[VectorDuplicationEntry]
    
    # Normalized observables
    normalized_vector_uniqueness_pct: float
    normalized_vector_duplicates: list[VectorDuplicationEntry]
    
    # Near-duplicates (Euclidean distance < 0.05 in normalized space)
    near_duplicate_cluster_count: int
    max_cluster_size: int
    
    # Alert
    broadcasting_suspected: bool   # if uniqueness < 20%


@dataclass(frozen=True)
class ComponentContributionReport:
    """Per-cell and scan-level ACIF component breakdown."""
    
    scan_id: str
    commodity: str
    
    # Scan-level means (aggregates)
    mean_evidence_score: float
    mean_causal_score: float
    mean_physics_score: float
    mean_temporal_score: float
    mean_province_prior: float
    mean_uncertainty: float
    mean_acif: float
    
    # ACIF distribution percentiles
    acif_p25: float
    acif_p50: float
    acif_p75: float
    acif_p90: float
    acif_stdev: float
    
    # Component correlation (Pearson r with ACIF)
    evidence_acif_correlation: Optional[float]
    physics_acif_correlation: Optional[float]
    temporal_acif_correlation: Optional[float]
    
    # Veto summary
    cells_with_causal_veto: int
    cells_with_physics_veto: int
    cells_with_temporal_veto: int
    cells_with_province_veto: int
    cells_with_any_veto: int
    
    # Modality contribution averages
    spectral_contribution_mean: Optional[float]
    sar_contribution_mean: Optional[float]
    thermal_contribution_mean: Optional[float]
    gravity_contribution_mean: Optional[float]
    magnetic_contribution_mean: Optional[float]


@dataclass(frozen=True)
class ScanValidationSummary:
    """
    Complete validation summary for one scan.
    Written to CanonicalScan at canonical freeze time.
    Immutable thereafter.
    """
    
    scan_id: str
    
    # Five core validation reports
    validation_status: ScanValidationStatus
    sensor_coverage: SensorCoverageReport
    observable_distribution: ObservableDistributionReport
    vector_integrity: VectorIntegrityReport
    component_contributions: ComponentContributionReport
    
    # User-facing alerts
    alert_messages: list[str]      # e.g., "Spectral indices missing for 100% of cells"
    warning_messages: list[str]    # e.g., "Only 45% multi-modal coverage"
    
    # Diagnostic trace (for debugging / support)
    diagnostics: dict              # arbitrary debug info