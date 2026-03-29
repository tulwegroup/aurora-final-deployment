"""
Aurora OSI vNext — Geological Gates Models
Phase AU §AU.5 — Interpretability Layer

Geological gates evaluate cell/scan suitability based on observable evidence.
These gates connect to the causal/physics veto system and provide transparency.

Four core gates:
  1. Laterite Weathering / Alteration Profile — clay/iron alteration indices
  2. Topographic Suitability — elevation, slope constraints
  3. Spatial Coherence — cluster integrity, structural continuity
  4. Thermal Signature Consistency — thermal anomaly presence/absence

No synthetic values. All derived from canonical observables.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    """Outcome of a geological gate evaluation."""
    PASS = "PASS"
    WEAK = "WEAK"
    FAIL = "FAIL"


class AlterationGate(BaseModel):
    """
    Laterite Weathering / Alteration Profile Gate
    
    Evaluates presence of clay + iron oxide absorption features.
    PASS: both clay_index > 1.8 AND ferric_ratio > 0.32
    WEAK: one present, one weak
    FAIL: both absent or weak
    """
    status: GateStatus
    confidence: float = Field(ge=0.0, le=1.0, description="0–1, higher = more confident")
    clay_index_norm: Optional[float] = Field(default=None, description="Normalized clay [0,1]")
    ferric_norm: Optional[float] = Field(default=None, description="Normalized ferric [0,1]")
    reasoning: str = Field(description="Human-readable explanation")


class TopographicGate(BaseModel):
    """
    Topographic Suitability Gate
    
    Evaluates elevation and slope for gold/copper/hydrocarbons.
    PASS: slope < 15° OR elevation 200–2500m (onshore)
    WEAK: marginal
    FAIL: extreme slope or elevation
    """
    status: GateStatus
    confidence: float = Field(ge=0.0, le=1.0)
    elevation_m: Optional[float] = Field(default=None)
    slope_deg: Optional[float] = Field(default=None)
    reasoning: str


class SpatialCoherenceGate(BaseModel):
    """
    Spatial Coherence Gate
    
    Evaluates cluster integrity and structural continuity.
    PASS: SAR coherence > 0.65 AND structural signal present
    WEAK: marginal coherence
    FAIL: no coherence / isolated cell
    """
    status: GateStatus
    confidence: float = Field(ge=0.0, le=1.0)
    sar_coherence: Optional[float] = Field(default=None)
    structural_signal: Optional[float] = Field(default=None, description="Lineament/fault density [0,1]")
    reasoning: str


class ThermalGate(BaseModel):
    """
    Thermal Signature Consistency Gate
    
    Evaluates thermal anomaly presence for hydrocarbon/geothermal targets.
    PASS: thermal anomaly present OR commodity is non-thermal (gold, copper)
    WEAK: marginal thermal signal
    FAIL: anti-correlation (unexpected thermal absence)
    """
    status: GateStatus
    confidence: float = Field(ge=0.0, le=1.0)
    thermal_flux: Optional[float] = Field(default=None, description="Normalized thermal [0,1]")
    commodity: str = Field(description="Target commodity (gold, copper, hydrocarbon, etc.)")
    reasoning: str


class CellGeologicalGates(BaseModel):
    """
    Complete geological gate evaluation for one cell.
    
    Constitutional: All gates must be computed from canonical observables.
    No hardcoding, no synthetic values.
    """
    cell_id: str
    alteration: AlterationGate
    topographic: TopographicGate
    spatial_coherence: SpatialCoherenceGate
    thermal: ThermalGate
    
    @property
    def overall_status(self) -> GateStatus:
        """Derive overall status from individual gates."""
        gates = [self.alteration.status, self.topographic.status, 
                 self.spatial_coherence.status, self.thermal.status]
        
        if GateStatus.FAIL in gates:
            return GateStatus.FAIL
        if GateStatus.WEAK in gates:
            return GateStatus.WEAK
        return GateStatus.PASS
    
    @property
    def pass_rate(self) -> float:
        """Fraction of gates in PASS status (0–1)."""
        gates = [self.alteration.status, self.topographic.status,
                 self.spatial_coherence.status, self.thermal.status]
        return sum(1 for g in gates if g == GateStatus.PASS) / len(gates)


class ScanGeologicalGateSummary(BaseModel):
    """
    Scan-level aggregation of geological gates.
    
    Persisted in CanonicalScan for interpretability.
    """
    alteration_pass_rate: float = Field(ge=0.0, le=1.0, description="% of cells PASS alteration")
    topographic_pass_rate: float = Field(ge=0.0, le=1.0)
    spatial_coherence_pass_rate: float = Field(ge=0.0, le=1.0)
    thermal_pass_rate: float = Field(ge=0.0, le=1.0)
    overall_pass_rate: float = Field(ge=0.0, le=1.0, description="Mean across all gates")
    
    cell_gate_details: dict[str, CellGeologicalGates] = Field(
        default_factory=dict,
        description="Per-cell gate outcomes (optional detail level)"
    )