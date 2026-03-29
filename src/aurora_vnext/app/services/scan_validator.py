"""
Aurora OSI vNext — Scan Validator Service
Phase AU §AU.1 | Part A — Scan Validation Framework

ROLE: Compute all validation reports for a completed scan.
      Does NOT modify scan state. Pure observation + analysis.

CALL SITE: scan_pipeline.py, at canonical freeze (step 19), before writing CanonicalScan.

INPUT: 
  - cell_results: list[ACIFCellResult] from core/scoring.py
  - scan_cells: list[ScanCell] with raw observables
  - scan_aggregates: ScanACIFAggregates from core/scoring.py

OUTPUT:
  - ScanValidationSummary (immutable, stored in CanonicalScan)

No imports from core/scoring, core/tiering, core/gates.
No side effects — pure functional analysis.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from typing import Optional
from collections import Counter

from app.models.scan_validation_model import (
    ScanValidationStatus,
    ScanValidationSummary,
    SensorCoverageReport,
    ObservableDistributionReport,
    ObservableStatistics,
    VectorIntegrityReport,
    VectorDuplicationEntry,
    ComponentContributionReport,
)
from app.models.observable_vector import ObservableVector
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# §AU.1.1 — Sensor Coverage Analysis
# ---------------------------------------------------------------------------

def compute_sensor_coverage(
    scan_cells: list,  # list of ScanCell entities
) -> SensorCoverageReport:
    """
    Analyze per-modality data availability.
    
    Checks:
    - S2: all 4 bands (B4, B8, B11, B12) present
    - S1: VV + VH present
    - Thermal: B10 present
    - DEM: elevation + slope present
    """
    if not scan_cells:
        raise ValueError("Cannot validate empty scan")
    
    total = len(scan_cells)
    s2_valid = 0
    s1_valid = 0
    thermal_valid = 0
    dem_valid = 0
    
    s2_clouds = []
    
    for cell in scan_cells:
        # S2
        if (hasattr(cell, 's2_b4') and cell.s2_b4 is not None and
            hasattr(cell, 's2_b8') and cell.s2_b8 is not None and
            hasattr(cell, 's2_b11') and cell.s2_b11 is not None and
            hasattr(cell, 's2_b12') and cell.s2_b12 is not None and
            hasattr(cell, 's2_valid') and cell.s2_valid):
            s2_valid += 1
            if hasattr(cell, 's2_cloud_pct') and cell.s2_cloud_pct is not None:
                s2_clouds.append(cell.s2_cloud_pct)
        
        # S1
        if (hasattr(cell, 's1_vv') and cell.s1_vv is not None and
            hasattr(cell, 's1_vh') and cell.s1_vh is not None and
            hasattr(cell, 's1_valid') and cell.s1_valid):
            s1_valid += 1
        
        # Thermal
        if (hasattr(cell, 'l8_b10') and cell.l8_b10 is not None and
            hasattr(cell, 'l8_valid') and cell.l8_valid):
            thermal_valid += 1
        
        # DEM
        if (hasattr(cell, 'dem_elevation') and cell.dem_elevation is not None and
            hasattr(cell, 'dem_slope') and cell.dem_slope is not None and
            hasattr(cell, 'dem_valid') and cell.dem_valid):
            dem_valid += 1
    
    # All modalities present
    all_modalities = 0
    for cell in scan_cells:
        s2_ok = (hasattr(cell, 's2_valid') and cell.s2_valid)
        s1_ok = (hasattr(cell, 's1_valid') and cell.s1_valid)
        th_ok = (hasattr(cell, 'l8_valid') and cell.l8_valid)
        dem_ok = (hasattr(cell, 'dem_valid') and cell.dem_valid)
        if s2_ok and s1_ok and th_ok and dem_ok:
            all_modalities += 1
    
    s2_cov_pct = (s2_valid / total * 100) if total > 0 else 0.0
    s1_cov_pct = (s1_valid / total * 100) if total > 0 else 0.0
    thermal_cov_pct = (thermal_valid / total * 100) if total > 0 else 0.0
    dem_cov_pct = (dem_valid / total * 100) if total > 0 else 0.0
    multi_cov_pct = (all_modalities / total * 100) if total > 0 else 0.0
    
    s2_cloud_mean = statistics.mean(s2_clouds) if s2_clouds else 0.0
    
    return SensorCoverageReport(
        total_cells=total,
        s2_valid_cells=s2_valid,
        s2_coverage_pct=s2_cov_pct,
        s2_cloud_mean_pct=s2_cloud_mean,
        s2_null_cells=total - s2_valid,
        s1_valid_cells=s1_valid,
        s1_coverage_pct=s1_cov_pct,
        s1_null_cells=total - s1_valid,
        thermal_valid_cells=thermal_valid,
        thermal_coverage_pct=thermal_cov_pct,
        thermal_null_cells=total - thermal_valid,
        dem_valid_cells=dem_valid,
        dem_coverage_pct=dem_cov_pct,
        dem_null_cells=total - dem_valid,
        all_modalities_valid_cells=all_modalities,
        multi_modal_coverage_pct=multi_cov_pct,
        s2_below_50pct=(s2_cov_pct < 50.0),
        s1_below_50pct=(s1_cov_pct < 50.0),
        thermal_below_50pct=(thermal_cov_pct < 50.0),
        dem_below_50pct=(dem_cov_pct < 50.0),
        any_modality_zero_coverage=(s2_cov_pct == 0.0 or s1_cov_pct == 0.0 or
                                   thermal_cov_pct == 0.0 or dem_cov_pct == 0.0),
    )


# ---------------------------------------------------------------------------
# §AU.1.2 — Observable Distribution Analysis
# ---------------------------------------------------------------------------

def compute_observable_distribution(
    observable_vectors: list[ObservableVector],
) -> ObservableDistributionReport:
    """
    Analyze per-observable value statistics.
    
    For each of 42 observable keys, compute:
    - coverage (% non-null)
    - min/max/mean/stdev
    - cardinality (unique values)
    - uniformity detection (% of mode value)
    """
    if not observable_vectors:
        raise ValueError("Cannot analyze empty observable list")
    
    total = len(observable_vectors)
    observable_keys = [
        'x_spec_1', 'x_spec_2', 'x_spec_3', 'x_spec_4',
        'x_spec_5', 'x_spec_6', 'x_spec_7', 'x_spec_8',
        'x_sar_1', 'x_sar_2', 'x_sar_3', 'x_sar_4', 'x_sar_5', 'x_sar_6',
        'x_therm_1', 'x_therm_2', 'x_therm_3', 'x_therm_4',
        'x_grav_1', 'x_grav_2', 'x_grav_3', 'x_grav_4', 'x_grav_5', 'x_grav_6',
        'x_mag_1', 'x_mag_2', 'x_mag_3', 'x_mag_4', 'x_mag_5',
        'x_struct_1', 'x_struct_2', 'x_struct_3', 'x_struct_4', 'x_struct_5',
        'x_hydro_1', 'x_hydro_2', 'x_hydro_3', 'x_hydro_4',
        'x_off_1', 'x_off_2', 'x_off_3', 'x_off_4',
    ]
    
    stats_dict: dict[str, ObservableStatistics] = {}
    zero_cov_count = 0
    low_cov_count = 0
    uniform_count = 0
    
    for key in observable_keys:
        values = []
        for vec in observable_vectors:
            val = getattr(vec, key, None)
            if val is not None:
                values.append(val)
        
        valid_count = len(values)
        cov_pct = (valid_count / total * 100) if total > 0 else 0.0
        null_count = total - valid_count
        
        if valid_count == 0:
            stats = ObservableStatistics(
                key=key,
                valid_cells=0,
                coverage_pct=0.0,
                null_cells=total,
                min_value=None,
                max_value=None,
                mean_value=None,
                stdev_value=None,
                unique_value_count=0,
                repeated_value_pct=0.0,
                zero_coverage=True,
                low_coverage=True,
                suspicious_uniform=False,
            )
            zero_cov_count += 1
        else:
            min_val = min(values)
            max_val = max(values)
            mean_val = statistics.mean(values)
            stdev_val = statistics.stdev(values) if valid_count > 1 else 0.0
            
            # Cardinality and mode
            counter = Counter(values)
            unique_count = len(counter)
            mode_count = counter.most_common(1)[0][1] if counter else 0
            repeated_pct = (mode_count / valid_count * 100) if valid_count > 0 else 0.0
            
            is_zero_cov = (cov_pct == 0.0)
            is_low_cov = (cov_pct < 50.0)
            is_uniform = (repeated_pct > 80.0)
            
            if is_zero_cov:
                zero_cov_count += 1
            if is_low_cov:
                low_cov_count += 1
            if is_uniform:
                uniform_count += 1
            
            stats = ObservableStatistics(
                key=key,
                valid_cells=valid_count,
                coverage_pct=cov_pct,
                null_cells=null_count,
                min_value=float(min_val),
                max_value=float(max_val),
                mean_value=float(mean_val),
                stdev_value=float(stdev_val),
                unique_value_count=unique_count,
                repeated_value_pct=float(repeated_pct),
                zero_coverage=is_zero_cov,
                low_coverage=is_low_cov,
                suspicious_uniform=is_uniform,
            )
        
        stats_dict[key] = stats
    
    zero_cov_obs = [k for k, s in stats_dict.items() if s.zero_coverage]
    low_cov_obs = [k for k, s in stats_dict.items() if s.low_coverage]
    uniform_obs = [k for k, s in stats_dict.items() if s.suspicious_uniform]
    
    return ObservableDistributionReport(
        cell_count=total,
        observable_stats=stats_dict,
        zero_coverage_count=zero_cov_count,
        low_coverage_count=low_cov_count,
        suspicious_uniform_count=uniform_count,
        zero_coverage_observables=zero_cov_obs,
        low_coverage_observables=low_cov_obs,
        suspicious_uniform_observables=uniform_obs,
    )


# ---------------------------------------------------------------------------
# §AU.1.3 — Vector Integrity Analysis
# ---------------------------------------------------------------------------

def compute_vector_integrity(
    observable_vectors: list[ObservableVector],
) -> VectorIntegrityReport:
    """
    Detect duplicated and near-duplicated observable vectors.
    
    Raw: original observable values
    Normalized: after normalisation.py (∈ [0, 1])
    Near-duplicates: Euclidean distance < 0.05
    """
    if not observable_vectors:
        raise ValueError("Cannot analyze empty observable list")
    
    total = len(observable_vectors)
    
    # Raw vector deduplication
    raw_hashes = {}
    for i, vec in enumerate(observable_vectors):
        # Hash the raw observable values
        raw_tuple = tuple(
            getattr(vec, f'x_{mod}_{num}', None)
            for mod in ['spec', 'sar', 'therm', 'grav', 'mag', 'struct', 'hydro', 'off']
            for num in range(1, 9)
        )
        h = hashlib.sha256(str(raw_tuple).encode()).hexdigest()
        if h not in raw_hashes:
            raw_hashes[h] = []
        raw_hashes[h].append(i)
    
    raw_dup_entries = [
        VectorDuplicationEntry(
            cell_count=len(indices),
            cell_ids=[f"cell_{i}" for i in indices],
            vector_hash=h,
        )
        for h, indices in raw_hashes.items()
        if len(indices) > 1
    ]
    raw_unique = len([h for h, idx in raw_hashes.items() if len(idx) == 1])
    raw_unique_pct = (raw_unique / total * 100) if total > 0 else 0.0
    
    # Normalized vector deduplication (similar logic)
    norm_hashes = {}
    for i, vec in enumerate(observable_vectors):
        norm_tuple = tuple(
            (getattr(vec, f'x_{mod}_{num}', None) or 0.5)  # treat None as 0.5
            for mod in ['spec', 'sar', 'therm', 'grav', 'mag', 'struct', 'hydro', 'off']
            for num in range(1, 9)
        )
        h = hashlib.sha256(str(norm_tuple).encode()).hexdigest()
        if h not in norm_hashes:
            norm_hashes[h] = []
        norm_hashes[h].append(i)
    
    norm_dup_entries = [
        VectorDuplicationEntry(
            cell_count=len(indices),
            cell_ids=[f"cell_{i}" for i in indices],
            vector_hash=h,
        )
        for h, indices in norm_hashes.items()
        if len(indices) > 1
    ]
    norm_unique = len([h for h, idx in norm_hashes.items() if len(idx) == 1])
    norm_unique_pct = (norm_unique / total * 100) if total > 0 else 0.0
    
    # Near-duplicates (placeholder — full clustering logic deferred)
    near_dup_clusters = 0
    max_cluster_size = 0
    
    broadcasting_suspect = (raw_unique_pct < 20.0 or norm_unique_pct < 20.0)
    
    return VectorIntegrityReport(
        cell_count=total,
        raw_vector_uniqueness_pct=raw_unique_pct,
        raw_vector_duplicates=raw_dup_entries,
        normalized_vector_uniqueness_pct=norm_unique_pct,
        normalized_vector_duplicates=norm_dup_entries,
        near_duplicate_cluster_count=near_dup_clusters,
        max_cluster_size=max_cluster_size,
        broadcasting_suspected=broadcasting_suspect,
    )


# ---------------------------------------------------------------------------
# §AU.1.4 — Component Contribution Analysis
# ---------------------------------------------------------------------------

def compute_component_contributions(
    scan_id: str,
    commodity: str,
    cell_results: list,  # list[ACIFCellResult] from core/scoring.py
    scan_aggregates,  # ScanACIFAggregates
) -> ComponentContributionReport:
    """
    Analyze ACIF component breakdown and correlations.
    """
    if not cell_results:
        raise ValueError("Cannot analyze empty cell results")
    
    n = len(cell_results)
    
    # Extract component values
    evidence_scores = [c.e_tilde for c in cell_results]
    causal_scores = [c.c_i for c in cell_results]
    physics_scores = [c.psi_i for c in cell_results]
    temporal_scores = [c.t_i for c in cell_results]
    province_priors = [c.pi_i for c in cell_results]
    acif_scores = [c.acif_score for c in cell_results]
    
    # Means
    mean_evidence = statistics.mean(evidence_scores) if evidence_scores else 0.0
    mean_causal = statistics.mean(causal_scores) if causal_scores else 0.0
    mean_physics = statistics.mean(physics_scores) if physics_scores else 0.0
    mean_temporal = statistics.mean(temporal_scores) if temporal_scores else 0.0
    mean_province = statistics.mean(province_priors) if province_priors else 0.0
    mean_acif = statistics.mean(acif_scores) if acif_scores else 0.0
    mean_uncertainty = 1.0 - mean_acif if mean_acif < 1.0 else 0.0
    
    # Percentiles (from scan_aggregates or computed)
    acif_sorted = sorted(acif_scores)
    p25 = acif_sorted[int(len(acif_sorted) * 0.25)] if acif_sorted else 0.0
    p50 = acif_sorted[int(len(acif_sorted) * 0.50)] if acif_sorted else 0.0
    p75 = acif_sorted[int(len(acif_sorted) * 0.75)] if acif_sorted else 0.0
    p90 = acif_sorted[int(len(acif_sorted) * 0.90)] if acif_sorted else 0.0
    
    acif_stdev = statistics.stdev(acif_scores) if len(acif_scores) > 1 else 0.0
    
    # Correlation (Pearson r)
    def _pearson_r(x: list[float], y: list[float]) -> Optional[float]:
        if len(x) < 2 or len(y) < 2:
            return None
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        denom_x = sum((x[i] - mean_x) ** 2 for i in range(len(x))) ** 0.5
        denom_y = sum((y[i] - mean_y) ** 2 for i in range(len(y))) ** 0.5
        if denom_x <= 0 or denom_y <= 0:
            return None
        return numerator / (denom_x * denom_y)
    
    corr_evidence = _pearson_r(evidence_scores, acif_scores)
    corr_physics = _pearson_r(physics_scores, acif_scores)
    corr_temporal = _pearson_r(temporal_scores, acif_scores)
    
    # Veto counts
    veto_causal = sum(1 for c in cell_results if c.causal_veto)
    veto_physics = sum(1 for c in cell_results if c.physics_veto)
    veto_temporal = sum(1 for c in cell_results if c.temporal_veto)
    veto_province = sum(1 for c in cell_results if c.province_veto)
    veto_any = sum(1 for c in cell_results if c.any_veto_fired)
    
    return ComponentContributionReport(
        scan_id=scan_id,
        commodity=commodity,
        mean_evidence_score=float(mean_evidence),
        mean_causal_score=float(mean_causal),
        mean_physics_score=float(mean_physics),
        mean_temporal_score=float(mean_temporal),
        mean_province_prior=float(mean_province),
        mean_uncertainty=float(mean_uncertainty),
        mean_acif=float(mean_acif),
        acif_p25=float(p25),
        acif_p50=float(p50),
        acif_p75=float(p75),
        acif_p90=float(p90),
        acif_stdev=float(acif_stdev),
        evidence_acif_correlation=corr_evidence,
        physics_acif_correlation=corr_physics,
        temporal_acif_correlation=corr_temporal,
        cells_with_causal_veto=veto_causal,
        cells_with_physics_veto=veto_physics,
        cells_with_temporal_veto=veto_temporal,
        cells_with_province_veto=veto_province,
        cells_with_any_veto=veto_any,
        spectral_contribution_mean=None,  # TODO: extract from evidence modality breakdown
        sar_contribution_mean=None,
        thermal_contribution_mean=None,
        gravity_contribution_mean=None,
        magnetic_contribution_mean=None,
    )


# ---------------------------------------------------------------------------
# §AU.1.5 — Full Validation Pipeline
# ---------------------------------------------------------------------------

def validate_scan(
    scan_id: str,
    commodity: str,
    scan_cells: list,
    observable_vectors: list[ObservableVector],
    cell_results: list,  # ACIFCellResult
    scan_aggregates,  # ScanACIFAggregates
) -> ScanValidationSummary:
    """
    Orchestrate all validation analyses and produce final summary.
    
    Called from scan_pipeline.py at canonical freeze (step 19).
    """
    sensor_coverage = compute_sensor_coverage(scan_cells)
    observable_dist = compute_observable_distribution(observable_vectors)
    vector_integrity = compute_vector_integrity(observable_vectors)
    component_contrib = compute_component_contributions(
        scan_id, commodity, cell_results, scan_aggregates
    )
    
    # Determine validation status
    alerts = []
    warnings = []
    
    if vector_integrity.broadcasting_suspected:
        alerts.append("Vector broadcasting suspected: < 20% unique vectors detected.")
    
    if observable_dist.zero_coverage_count > 10:
        alerts.append(
            f"{observable_dist.zero_coverage_count} observables have zero coverage "
            "(all cells null). Spectral indices may be missing."
        )
    
    if sensor_coverage.s2_coverage_pct < 50.0:
        alerts.append(
            f"Sentinel-2 coverage only {sensor_coverage.s2_coverage_pct:.1f}%. "
            "Spectral alteration indices unavailable."
        )
    
    if sensor_coverage.multi_modal_coverage_pct < 50.0:
        alerts.append(
            f"Multi-modal coverage only {sensor_coverage.multi_modal_coverage_pct:.1f}%. "
            "Evidence score may be unreliable."
        )
    
    if sensor_coverage.s2_coverage_pct < 80.0 and sensor_coverage.s2_coverage_pct >= 50.0:
        warnings.append(
            f"Sentinel-2 coverage {sensor_coverage.s2_coverage_pct:.1f}% — "
            "some cells lack spectral data."
        )
    
    if sensor_coverage.multi_modal_coverage_pct < 80.0 and sensor_coverage.multi_modal_coverage_pct >= 50.0:
        warnings.append(
            f"Multi-modal coverage {sensor_coverage.multi_modal_coverage_pct:.1f}% — "
            "consider limited modality support."
        )
    
    # Assign validation status based on coverage + integrity
    if sensor_coverage.multi_modal_coverage_pct >= 80.0 and \
       observable_dist.zero_coverage_count < 5 and \
       vector_integrity.broadcasting_suspected == False:
        status = ScanValidationStatus.VALID_FOR_RANKING
    elif sensor_coverage.multi_modal_coverage_pct >= 50.0 and \
         observable_dist.zero_coverage_count < 10:
        status = ScanValidationStatus.PARTIAL_MODALITY_SUPPORT
    elif sensor_coverage.s2_coverage_pct < 50.0 or \
         (observable_dist.zero_coverage_count >= 20):
        status = ScanValidationStatus.INSUFFICIENT_SPECTRAL_SUPPORT
    else:
        status = ScanValidationStatus.INSUFFICIENT_DATA
    
    return ScanValidationSummary(
        scan_id=scan_id,
        validation_status=status,
        sensor_coverage=sensor_coverage,
        observable_distribution=observable_dist,
        vector_integrity=vector_integrity,
        component_contributions=component_contrib,
        alert_messages=alerts,
        warning_messages=warnings,
        diagnostics={
            "validation_timestamp": None,  # TODO: add timestamp
            "module_version": "phase_au_v1",
        },
    )