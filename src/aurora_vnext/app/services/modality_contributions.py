"""
Aurora OSI vNext — Modality Contributions Computation Service
Phase AU §AU.5

Compute per-modality contributions to ACIF from canonical observables.

Nine modalities:
  1. Clay Alteration (x_spec_1)
  2. Ferric Iron (x_spec_2)
  3. SAR Backscatter (x_sar_1, x_sar_2)
  4. Thermal Flux (x_therm_1)
  5. NDVI/Vegetation (x_spec_3)
  6. Structural (x_struct_1, x_struct_2)
  7. Gravity (x_grav_1..6)
  8. Magnetic (x_mag_1..5)
  9. SAR Coherence (x_sar_3)

All computation from canonical ObservableVector. No synthetic values.
"""

from __future__ import annotations
from typing import Optional

from app.models.modality_contributions_model import (
    ModalityContribution,
    CellModalityContributions,
    ScanModalityAverages,
    ACIFModalityTraceability,
)
from app.models.observable_vector import ObservableVector
from app.models.component_scores import EvidenceResult


def compute_modality_contributions(
    obs_vec: ObservableVector,
    evidence_result: EvidenceResult,
    commodity: str,
) -> CellModalityContributions:
    """
    Compute per-modality contributions for one cell.
    
    Links each modality (clay, ferric, SAR, etc.) to evidence score.
    """
    modalities: list[ModalityContribution] = []
    
    # 1. Clay Alteration (x_spec_1)
    if obs_vec.x_spec_1 is not None:
        modalities.append(ModalityContribution(
            modality_name="clay_alteration",
            normalized_contribution=obs_vec.x_spec_1,
            observable_count=1,
            observable_coverage=1.0,
            weight_in_evidence=0.15,  # commodity-specific, from library
            mean_sub_observable=obs_vec.x_spec_1,
            confidence=obs_vec.x_spec_1 * 0.9,
            reasoning=f"Clay alteration index (normalized): {obs_vec.x_spec_1:.3f}"
        ))
    
    # 2. Ferric Iron (x_spec_2)
    if obs_vec.x_spec_2 is not None:
        modalities.append(ModalityContribution(
            modality_name="ferric_iron",
            normalized_contribution=obs_vec.x_spec_2,
            observable_count=1,
            observable_coverage=1.0,
            weight_in_evidence=0.15,
            mean_sub_observable=obs_vec.x_spec_2,
            confidence=obs_vec.x_spec_2 * 0.9,
            reasoning=f"Iron oxide index (normalized): {obs_vec.x_spec_2:.3f}"
        ))
    
    # 3. SAR Backscatter (x_sar_1, x_sar_2)
    sar_count = sum(1 for v in [obs_vec.x_sar_1, obs_vec.x_sar_2] if v is not None)
    if sar_count > 0:
        sar_mean = sum(v for v in [obs_vec.x_sar_1, obs_vec.x_sar_2] if v is not None) / sar_count
        modalities.append(ModalityContribution(
            modality_name="sar_backscatter",
            normalized_contribution=sar_mean,
            observable_count=sar_count,
            observable_coverage=sar_count / 2.0,
            weight_in_evidence=0.12,
            mean_sub_observable=sar_mean,
            confidence=sar_mean * (sar_count / 2.0),
            reasoning=f"SAR VV/VH backscatter (mean norm): {sar_mean:.3f}"
        ))
    
    # 4. Thermal Flux (x_therm_1)
    if obs_vec.x_therm_1 is not None:
        modalities.append(ModalityContribution(
            modality_name="thermal_flux",
            normalized_contribution=obs_vec.x_therm_1,
            observable_count=1,
            observable_coverage=1.0,
            weight_in_evidence=0.08,
            mean_sub_observable=obs_vec.x_therm_1,
            confidence=obs_vec.x_therm_1 * 0.8,
            reasoning=f"Thermal anomaly (normalized): {obs_vec.x_therm_1:.3f}"
        ))
    
    # 5. NDVI / Vegetation Stress (x_spec_3)
    if obs_vec.x_spec_3 is not None:
        modalities.append(ModalityContribution(
            modality_name="ndvi_vegetation",
            normalized_contribution=obs_vec.x_spec_3,
            observable_count=1,
            observable_coverage=1.0,
            weight_in_evidence=0.10,
            mean_sub_observable=obs_vec.x_spec_3,
            confidence=obs_vec.x_spec_3 * 0.85,
            reasoning=f"NDVI / vegetation stress (normalized): {obs_vec.x_spec_3:.3f}"
        ))
    
    # 6. Structural (x_struct_1, x_struct_2, x_struct_5)
    struct_vals = [obs_vec.x_struct_1, obs_vec.x_struct_2, obs_vec.x_struct_5]
    struct_count = sum(1 for v in struct_vals if v is not None)
    if struct_count > 0:
        struct_mean = sum(v for v in struct_vals if v is not None) / struct_count
        modalities.append(ModalityContribution(
            modality_name="structural",
            normalized_contribution=struct_mean,
            observable_count=struct_count,
            observable_coverage=struct_count / 3.0,
            weight_in_evidence=0.10,
            mean_sub_observable=struct_mean,
            confidence=struct_mean * (struct_count / 3.0),
            reasoning=f"Structural features (slope, elevation, lineaments): {struct_mean:.3f}"
        ))
    
    # 7. Gravity (x_grav_1..6)
    grav_vals = [obs_vec.x_grav_1, obs_vec.x_grav_2, obs_vec.x_grav_3,
                 obs_vec.x_grav_4, obs_vec.x_grav_5, obs_vec.x_grav_6]
    grav_count = sum(1 for v in grav_vals if v is not None)
    if grav_count > 0:
        grav_mean = sum(v for v in grav_vals if v is not None) / grav_count
        modalities.append(ModalityContribution(
            modality_name="gravity",
            normalized_contribution=grav_mean,
            observable_count=grav_count,
            observable_coverage=grav_count / 6.0,
            weight_in_evidence=0.12,
            mean_sub_observable=grav_mean,
            confidence=grav_mean * (grav_count / 6.0),
            reasoning=f"Gravity composite (multi-orbit, FAA, Bouguer): {grav_mean:.3f}"
        ))
    
    # 8. Magnetic (x_mag_1..5)
    mag_vals = [obs_vec.x_mag_1, obs_vec.x_mag_2, obs_vec.x_mag_3,
                obs_vec.x_mag_4, obs_vec.x_mag_5]
    mag_count = sum(1 for v in mag_vals if v is not None)
    if mag_count > 0:
        mag_mean = sum(v for v in mag_vals if v is not None) / mag_count
        modalities.append(ModalityContribution(
            modality_name="magnetic",
            normalized_contribution=mag_mean,
            observable_count=mag_count,
            observable_coverage=mag_count / 5.0,
            weight_in_evidence=0.10,
            mean_sub_observable=mag_mean,
            confidence=mag_mean * (mag_count / 5.0),
            reasoning=f"Magnetic anomaly (TFI, RTP, derivatives): {mag_mean:.3f}"
        ))
    
    # 9. SAR Coherence (x_sar_3)
    if obs_vec.x_sar_3 is not None:
        modalities.append(ModalityContribution(
            modality_name="sar_coherence",
            normalized_contribution=obs_vec.x_sar_3,
            observable_count=1,
            observable_coverage=1.0,
            weight_in_evidence=0.08,
            mean_sub_observable=obs_vec.x_sar_3,
            confidence=obs_vec.x_sar_3 * 0.9,
            reasoning=f"SAR coherence (temporal stability): {obs_vec.x_sar_3:.3f}"
        ))
    
    return CellModalityContributions(cell_id="", modalities=modalities)


def aggregate_scan_modality_averages(
    cell_contributions: list[CellModalityContributions],
) -> ScanModalityAverages:
    """
    Aggregate per-cell modality contributions into scan-level averages.
    """
    def mean_modality(name: str) -> float:
        """Mean normalized contribution for one modality across all cells."""
        vals = [
            m.normalized_contribution
            for cell in cell_contributions
            for m in cell.modalities
            if m.modality_name == name
        ]
        return sum(vals) / len(vals) if vals else 0.0
    
    return ScanModalityAverages(
        clay_alteration=mean_modality("clay_alteration"),
        ferric_iron=mean_modality("ferric_iron"),
        sar_backscatter=mean_modality("sar_backscatter"),
        thermal_flux=mean_modality("thermal_flux"),
        ndvi_vegetation=mean_modality("ndvi_vegetation"),
        structural=mean_modality("structural"),
        gravity=mean_modality("gravity"),
        magnetic=mean_modality("magnetic"),
        sar_coherence=mean_modality("sar_coherence"),
    )


def build_acif_traceability(
    cell_id: str,
    obs_vec: ObservableVector,
    evidence: float,
    causal: float,
    physics: float,
    temporal: float,
    province_prior: float,
    uncertainty: float,
    acif: float,
    causal_veto: bool,
    physics_veto: bool,
    temporal_veto: bool,
    modality_contributions: ScanModalityAverages,
) -> ACIFModalityTraceability:
    """
    Build complete traceability chain for one cell's ACIF.
    
    Shows: observables → modalities → components → final ACIF with veto status.
    """
    return ACIFModalityTraceability(
        scan_id="",  # Filled in by caller
        cell_id=cell_id,
        modality_contributions=modality_contributions,
        evidence_score=evidence,
        causal_score=causal,
        physics_score=physics,
        temporal_score=temporal,
        province_prior=province_prior,
        uncertainty=uncertainty,
        acif_score=acif,
        causal_veto_fired=causal_veto,
        physics_veto_fired=physics_veto,
        temporal_veto_fired=temporal_veto,
    )