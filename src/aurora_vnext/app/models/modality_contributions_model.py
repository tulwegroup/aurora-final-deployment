"""
Aurora OSI vNext — Modality Contributions Models
Phase AU §AU.5 — ACIF Transparency Layer

Modality-level contributions bridge observables to final ACIF.

Required modalities (9 total):
  1. Clay Alteration (spectral x_spec_1)
  2. Iron Oxide / Ferric (spectral x_spec_2)
  3. SAR Backscatter (SAR x_sar_1, x_sar_2)
  4. Thermal Flux (thermal x_therm_1)
  5. NDVI / Vegetation Stress (spectral x_spec_3)
  6. Structural (structural x_struct_1, x_struct_2)
  7. Gravity (gravity x_grav_1..6)
  8. Magnetic (magnetic x_mag_1..5)
  9. SAR Coherence (SAR x_sar_3)

Each modality:
- Aggregates sub-observables
- Computes normalized contribution (0–1)
- Links to evidence/component scores
- Persists in scan output

No synthetic computation. All from canonical observables.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ModalityContribution(BaseModel):
    """
    One modality's contribution to ACIF.
    
    Modality aggregates multiple observables, computes normalized
    contribution (0–1), and links to evidence/component impact.
    """
    modality_name: str = Field(
        description="clay_alteration | ferric_iron | sar_backscatter | thermal_flux | "
                    "ndvi_vegetation | structural | gravity | magnetic | sar_coherence"
    )
    normalized_contribution: float = Field(
        ge=0.0, le=1.0,
        description="Normalized modality contribution to evidence score (0–1)"
    )
    observable_count: int = Field(
        ge=0, description="Number of sub-observables in this modality"
    )
    observable_coverage: float = Field(
        ge=0.0, le=1.0,
        description="Fraction of modality observables present (non-null)"
    )
    weight_in_evidence: float = Field(
        ge=0.0, le=1.0,
        description="Weight assigned to this modality in evidence formula"
    )
    mean_sub_observable: float = Field(
        ge=0.0, le=1.0,
        description="Mean normalized value of sub-observables [0,1]"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this modality (combination of coverage + weight)"
    )
    reasoning: str = Field(
        description="Human-readable explanation of contribution"
    )


class CellModalityContributions(BaseModel):
    """
    Per-cell modality breakdown.
    
    Explains how each modality contributed to that cell's ACIF.
    """
    cell_id: str
    modalities: list[ModalityContribution] = Field(default_factory=list)
    
    @property
    def dominant_modality(self) -> Optional[ModalityContribution]:
        """Return modality with highest normalized_contribution."""
        if not self.modalities:
            return None
        return max(self.modalities, key=lambda m: m.normalized_contribution)
    
    @property
    def total_contribution(self) -> float:
        """Sum of weighted contributions (should ≈ evidence score)."""
        return sum(m.normalized_contribution * m.weight_in_evidence for m in self.modalities)


class ScanModalityAverages(BaseModel):
    """
    Scan-level modality aggregation.
    
    Computes mean normalized contribution across all cells for each modality.
    Exposed via API for UI visualization.
    Persisted in CanonicalScan.
    """
    clay_alteration: float = Field(ge=0.0, le=1.0, description="Mean clay contribution [0,1]")
    ferric_iron: float = Field(ge=0.0, le=1.0, description="Mean ferric contribution [0,1]")
    sar_backscatter: float = Field(ge=0.0, le=1.0, description="Mean SAR backscatter [0,1]")
    thermal_flux: float = Field(ge=0.0, le=1.0, description="Mean thermal [0,1]")
    ndvi_vegetation: float = Field(ge=0.0, le=1.0, description="Mean NDVI [0,1]")
    structural: float = Field(ge=0.0, le=1.0, description="Mean structural [0,1]")
    gravity: float = Field(ge=0.0, le=1.0, description="Mean gravity [0,1]")
    magnetic: float = Field(ge=0.0, le=1.0, description="Mean magnetic [0,1]")
    sar_coherence: float = Field(ge=0.0, le=1.0, description="Mean SAR coherence [0,1]")
    
    def as_dict(self) -> dict[str, float]:
        """Return as ordered dict for API/UI."""
        return {
            "clay_alteration": self.clay_alteration,
            "ferric_iron": self.ferric_iron,
            "sar_backscatter": self.sar_backscatter,
            "thermal_flux": self.thermal_flux,
            "ndvi_vegetation": self.ndvi_vegetation,
            "structural": self.structural,
            "gravity": self.gravity,
            "magnetic": self.magnetic,
            "sar_coherence": self.sar_coherence,
        }
    
    def sorted_by_contribution(self) -> list[tuple[str, float]]:
        """Return modalities sorted by contribution (descending)."""
        return sorted(self.as_dict().items(), key=lambda x: x[1], reverse=True)


class ACIFModalityTraceability(BaseModel):
    """
    Full traceability chain: observables → modalities → components → ACIF.
    
    Explains every step in the ACIF computation for interpretability.
    """
    scan_id: str
    cell_id: Optional[str] = None  # None for scan-level, set for cell-level
    
    # Modality contributions
    modality_contributions: ScanModalityAverages
    
    # Component breakdown
    evidence_score: float = Field(ge=0.0, le=1.0, description="Ẽ")
    causal_score: float = Field(ge=0.0, le=1.0, description="C")
    physics_score: float = Field(ge=0.0, le=1.0, description="Ψ")
    temporal_score: float = Field(ge=0.0, le=1.0, description="T")
    province_prior: float = Field(ge=0.0, le=1.0, description="Π")
    uncertainty: float = Field(ge=0.0, le=1.0, description="U")
    
    # Final ACIF
    acif_score: float = Field(ge=0.0, le=1.0, description="ACIF = Ẽ × C × Ψ × T × Π × (1-U)")
    
    # Veto status
    causal_veto_fired: bool = Field(default=False)
    physics_veto_fired: bool = Field(default=False)
    temporal_veto_fired: bool = Field(default=False)
    
    def explain_modality_contribution(self, modality: str) -> str:
        """Generate human-readable explanation for one modality."""
        mods = self.modality_contributions.as_dict()
        value = mods.get(modality, 0.0)
        return f"{modality}: {value:.3f} contribution to evidence score"
    
    def explain_acif_formula(self) -> str:
        """Explain ACIF computation step-by-step."""
        return (
            f"ACIF = Ẽ(E={self.evidence_score:.3f}) "
            f"× C({self.causal_score:.3f}) × Ψ({self.physics_score:.3f}) "
            f"× T({self.temporal_score:.3f}) × Π({self.province_prior:.3f}) "
            f"× (1-U={1-self.uncertainty:.3f}) = {self.acif_score:.3f}"
        )