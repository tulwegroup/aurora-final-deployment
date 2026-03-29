"""
Aurora OSI vNext — Geological Gates Computation Service
Phase AU §AU.5

Evaluate four geological gates per cell:
1. Laterite Weathering / Alteration (clay + iron)
2. Topographic Suitability
3. Spatial Coherence (SAR coherence + structural)
4. Thermal Signature

All computation from canonical observables. No synthetic values.

Returns: CellGeologicalGates with PASS/WEAK/FAIL per gate.
"""

from __future__ import annotations
from typing import Optional

from app.models.geological_gates_model import (
    GateStatus,
    AlterationGate,
    TopographicGate,
    SpatialCoherenceGate,
    ThermalGate,
    CellGeologicalGates,
    ScanGeologicalGateSummary,
)
from app.models.observable_vector import ObservableVector


def evaluate_alteration_gate(
    obs_vec: ObservableVector,
    cell_id: str,
) -> AlterationGate:
    """
    Laterite Weathering / Alteration Profile Gate.
    
    PASS: clay_norm > 0.55 AND ferric_norm > 0.40
    WEAK: one > threshold, other marginal
    FAIL: both weak or absent
    """
    clay_norm = obs_vec.x_spec_1  # Normalized clay index
    ferric_norm = obs_vec.x_spec_2  # Normalized ferric ratio
    
    if clay_norm is None or ferric_norm is None:
        return AlterationGate(
            status=GateStatus.FAIL,
            confidence=0.0,
            clay_index_norm=clay_norm,
            ferric_norm=ferric_norm,
            reasoning="Spectral data missing — cannot evaluate alteration profile"
        )
    
    clay_pass = clay_norm > 0.55
    ferric_pass = ferric_norm > 0.40
    
    if clay_pass and ferric_pass:
        status = GateStatus.PASS
        confidence = min(clay_norm, ferric_norm)
        reasoning = f"Clay ({clay_norm:.3f}) and ferric ({ferric_norm:.3f}) both present — strong alteration profile"
    elif clay_pass or ferric_pass:
        status = GateStatus.WEAK
        confidence = max(clay_norm, ferric_norm) * 0.5
        reasoning = f"Clay ({clay_norm:.3f}) or ferric ({ferric_norm:.3f}) present — partial alteration"
    else:
        status = GateStatus.FAIL
        confidence = max(clay_norm, ferric_norm) * 0.2
        reasoning = f"Clay ({clay_norm:.3f}) and ferric ({ferric_norm:.3f}) both weak — insufficient alteration"
    
    return AlterationGate(
        status=status,
        confidence=confidence,
        clay_index_norm=clay_norm,
        ferric_norm=ferric_norm,
        reasoning=reasoning
    )


def evaluate_topographic_gate(
    obs_vec: ObservableVector,
    cell_id: str,
) -> TopographicGate:
    """
    Topographic Suitability Gate.
    
    Evaluates elevation (x_struct_2) and slope (x_struct_1).
    PASS: slope < 0.3 (30° norm) AND elevation in reasonable range
    WEAK: marginal
    FAIL: extreme slope or elevation
    """
    slope_norm = obs_vec.x_struct_1  # Normalized slope [0,1]
    elevation_norm = obs_vec.x_struct_2  # Normalized elevation [0,1]
    
    if slope_norm is None or elevation_norm is None:
        return TopographicGate(
            status=GateStatus.WEAK,
            confidence=0.5,
            elevation_m=None,
            slope_deg=None,
            reasoning="Topographic data missing — weak gate status"
        )
    
    # Convert normalized values back to physical ranges (for reasoning)
    slope_deg = slope_norm * 90  # 0–90° range
    elevation_m = 500 + (elevation_norm * 3500)  # 500–4000m range
    
    slope_suitable = slope_norm < 0.3  # < 27° suitable
    elevation_suitable = 0.15 < elevation_norm < 0.95  # 1000–3800m suitable
    
    if slope_suitable and elevation_suitable:
        status = GateStatus.PASS
        confidence = 0.8
        reasoning = f"Slope {slope_deg:.1f}° and elevation {elevation_m:.0f}m both suitable"
    elif slope_suitable or elevation_suitable:
        status = GateStatus.WEAK
        confidence = 0.5
        reasoning = f"Slope {slope_deg:.1f}° or elevation {elevation_m:.0f}m marginal"
    else:
        status = GateStatus.FAIL
        confidence = 0.2
        reasoning = f"Slope {slope_deg:.1f}° too steep or elevation {elevation_m:.0f}m unsuitable"
    
    return TopographicGate(
        status=status,
        confidence=confidence,
        elevation_m=elevation_m,
        slope_deg=slope_deg,
        reasoning=reasoning
    )


def evaluate_spatial_coherence_gate(
    obs_vec: ObservableVector,
    cell_id: str,
) -> SpatialCoherenceGate:
    """
    Spatial Coherence Gate.
    
    SAR coherence (x_sar_3) and structural signal (x_struct_5 lineament density).
    PASS: coherence > 0.65 AND structural present
    WEAK: one present
    FAIL: no coherence/structure
    """
    coherence_norm = obs_vec.x_sar_3  # Normalized SAR coherence [0,1]
    structural_norm = obs_vec.x_struct_5  # Normalized lineament density [0,1]
    
    if coherence_norm is None:
        coherence_norm = 0.0
    if structural_norm is None:
        structural_norm = 0.0
    
    coherence_pass = coherence_norm > 0.65
    structure_pass = structural_norm > 0.40
    
    if coherence_pass and structure_pass:
        status = GateStatus.PASS
        confidence = min(coherence_norm, structural_norm)
        reasoning = f"SAR coherence ({coherence_norm:.3f}) and structural signal ({structural_norm:.3f}) both strong"
    elif coherence_pass or structure_pass:
        status = GateStatus.WEAK
        confidence = max(coherence_norm, structural_norm) * 0.6
        reasoning = f"SAR coherence ({coherence_norm:.3f}) or structure ({structural_norm:.3f}) present"
    else:
        status = GateStatus.FAIL
        confidence = 0.2
        reasoning = f"SAR coherence ({coherence_norm:.3f}) and structure ({structural_norm:.3f}) both weak"
    
    return SpatialCoherenceGate(
        status=status,
        confidence=confidence,
        sar_coherence=coherence_norm,
        structural_signal=structural_norm,
        reasoning=reasoning
    )


def evaluate_thermal_gate(
    obs_vec: ObservableVector,
    commodity: str,
    cell_id: str,
) -> ThermalGate:
    """
    Thermal Signature Consistency Gate.
    
    For non-thermal commodities (gold, copper): PASS if thermal is present OR weak
    For thermal commodities (hydrocarbon): PASS if thermal anomaly present
    """
    thermal_norm = obs_vec.x_therm_1  # Normalized thermal flux [0,1]
    
    if thermal_norm is None:
        thermal_norm = 0.0
    
    # Commodity classification
    is_thermal_commodity = commodity.lower() in ("hydrocarbon", "geothermal")
    
    if is_thermal_commodity:
        # Thermal commodities require thermal signal
        if thermal_norm > 0.50:
            status = GateStatus.PASS
            confidence = thermal_norm
            reasoning = f"Strong thermal anomaly ({thermal_norm:.3f}) suitable for {commodity}"
        elif thermal_norm > 0.30:
            status = GateStatus.WEAK
            confidence = thermal_norm * 0.7
            reasoning = f"Weak thermal signal ({thermal_norm:.3f}) marginal for {commodity}"
        else:
            status = GateStatus.FAIL
            confidence = 0.2
            reasoning = f"Insufficient thermal ({thermal_norm:.3f}) for {commodity} exploration"
    else:
        # Non-thermal commodities (gold, copper) don't require thermal
        status = GateStatus.PASS
        confidence = 0.8
        reasoning = f"Thermal signal optional for {commodity} (non-thermal commodity)"
    
    return ThermalGate(
        status=status,
        confidence=confidence,
        thermal_flux=thermal_norm,
        commodity=commodity,
        reasoning=reasoning
    )


def evaluate_cell_geological_gates(
    cell_id: str,
    obs_vec: ObservableVector,
    commodity: str,
) -> CellGeologicalGates:
    """
    Evaluate all four geological gates for one cell.
    
    Returns: CellGeologicalGates with PASS/WEAK/FAIL per gate.
    """
    return CellGeologicalGates(
        cell_id=cell_id,
        alteration=evaluate_alteration_gate(obs_vec, cell_id),
        topographic=evaluate_topographic_gate(obs_vec, cell_id),
        spatial_coherence=evaluate_spatial_coherence_gate(obs_vec, cell_id),
        thermal=evaluate_thermal_gate(obs_vec, commodity, cell_id),
    )


def aggregate_scan_gates(cell_gates: list[CellGeologicalGates]) -> ScanGeologicalGateSummary:
    """
    Aggregate per-cell gates into scan-level summary.
    
    Computes pass rates and overall pass rate.
    """
    if not cell_gates:
        return ScanGeologicalGateSummary(
            alteration_pass_rate=0.0,
            topographic_pass_rate=0.0,
            spatial_coherence_pass_rate=0.0,
            thermal_pass_rate=0.0,
            overall_pass_rate=0.0,
        )
    
    n = len(cell_gates)
    alteration_pass = sum(1 for g in cell_gates if g.alteration.status == GateStatus.PASS) / n
    topographic_pass = sum(1 for g in cell_gates if g.topographic.status == GateStatus.PASS) / n
    coherence_pass = sum(1 for g in cell_gates if g.spatial_coherence.status == GateStatus.PASS) / n
    thermal_pass = sum(1 for g in cell_gates if g.thermal.status == GateStatus.PASS) / n
    overall = (alteration_pass + topographic_pass + coherence_pass + thermal_pass) / 4
    
    return ScanGeologicalGateSummary(
        alteration_pass_rate=alteration_pass,
        topographic_pass_rate=topographic_pass,
        spatial_coherence_pass_rate=coherence_pass,
        thermal_pass_rate=thermal_pass,
        overall_pass_rate=overall,
        cell_gate_details={g.cell_id: g for g in cell_gates},
    )