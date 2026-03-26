"""
Aurora OSI vNext — Observable Vector and Version Registry Models
Phase F §F.2

ObservableVector: 42-field normalised sensor observation for one scan cell.
VersionRegistry: 8-field locked version state persisted with every CanonicalScan.

CONSTITUTIONAL RULE: All 42 field values must be in [0.0, 1.0].
Missing observables are represented as None (null) — never as 0.0 (which would
incorrectly imply a zero observation rather than a missing sensor).

No scientific logic. No scoring. No imports from core/ or services/.
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, model_validator

# Bounded float type: represents a normalised observable value in [0, 1]
NormalisedFloat = Annotated[float, Field(ge=0.0, le=1.0)]


class ObservableVector(BaseModel):
    """
    Canonical 42-observable normalised input vector for one scan cell.

    Each field corresponds to a specific sensor modality sub-score.
    Values are normalised to [0, 1] per §3.2.
    None indicates a missing observable — handled by uncertainty module per §3.3.

    Fields are grouped by modality:
      - Spectral (8):       x_spec_1..8
      - SAR (6):            x_sar_1..6
      - Thermal (4):        x_therm_1..4
      - Gravity (6):        x_grav_1..6
      - Magnetic (5):       x_mag_1..5
      - Structural (5):     x_struct_1..5
      - Hydrological (4):   x_hydro_1..4
      - Offshore (4):       x_off_1..4 — only populated for offshore cells after correction

    Total: 8+6+4+6+5+5+4+4 = 42
    """

    # Spectral (optical reflectance, vegetation indices, mineral absorption)
    x_spec_1: Optional[NormalisedFloat] = None
    x_spec_2: Optional[NormalisedFloat] = None
    x_spec_3: Optional[NormalisedFloat] = None
    x_spec_4: Optional[NormalisedFloat] = None
    x_spec_5: Optional[NormalisedFloat] = None
    x_spec_6: Optional[NormalisedFloat] = None
    x_spec_7: Optional[NormalisedFloat] = None
    x_spec_8: Optional[NormalisedFloat] = None

    # SAR (backscatter, coherence, decomposition components)
    x_sar_1: Optional[NormalisedFloat] = None
    x_sar_2: Optional[NormalisedFloat] = None
    x_sar_3: Optional[NormalisedFloat] = None
    x_sar_4: Optional[NormalisedFloat] = None
    x_sar_5: Optional[NormalisedFloat] = None
    x_sar_6: Optional[NormalisedFloat] = None

    # Thermal (land surface temperature anomaly, heat flow, thermal inertia, emissivity)
    x_therm_1: Optional[NormalisedFloat] = None
    x_therm_2: Optional[NormalisedFloat] = None
    x_therm_3: Optional[NormalisedFloat] = None
    x_therm_4: Optional[NormalisedFloat] = None

    # Gravity (free-air anomaly, Bouguer anomaly, vertical gradient, horizontal gradient,
    #          short-wavelength, isostatic residual)
    x_grav_1: Optional[NormalisedFloat] = None
    x_grav_2: Optional[NormalisedFloat] = None
    x_grav_3: Optional[NormalisedFloat] = None
    x_grav_4: Optional[NormalisedFloat] = None
    x_grav_5: Optional[NormalisedFloat] = None
    x_grav_6: Optional[NormalisedFloat] = None

    # Magnetic (total field anomaly, RTP, analytic signal, horizontal derivative, depth-to-source)
    x_mag_1: Optional[NormalisedFloat] = None
    x_mag_2: Optional[NormalisedFloat] = None
    x_mag_3: Optional[NormalisedFloat] = None
    x_mag_4: Optional[NormalisedFloat] = None
    x_mag_5: Optional[NormalisedFloat] = None

    # Structural geology (lineament density, fault proximity, fold axis, dome detection, DEM curvature)
    x_struct_1: Optional[NormalisedFloat] = None
    x_struct_2: Optional[NormalisedFloat] = None
    x_struct_3: Optional[NormalisedFloat] = None
    x_struct_4: Optional[NormalisedFloat] = None
    x_struct_5: Optional[NormalisedFloat] = None

    # Hydrological (soil moisture, drainage anomaly, groundwater proxy, vegetation stress)
    x_hydro_1: Optional[NormalisedFloat] = None
    x_hydro_2: Optional[NormalisedFloat] = None
    x_hydro_3: Optional[NormalisedFloat] = None
    x_hydro_4: Optional[NormalisedFloat] = None

    # Offshore corrections (only populated after CorrectedOffshoreCell gate — §9.4)
    # x_off_1: water-column reflectance residual
    # x_off_2: SST anomaly (normalised)
    # x_off_3: SSH anomaly (normalised)
    # x_off_4: chlorophyll anomaly (normalised)
    x_off_1: Optional[NormalisedFloat] = None
    x_off_2: Optional[NormalisedFloat] = None
    x_off_3: Optional[NormalisedFloat] = None
    x_off_4: Optional[NormalisedFloat] = None

    @model_validator(mode="after")
    def validate_observable_count(self) -> "ObservableVector":
        """Confirm the vector dimension matches the constitutional constant of 42."""
        all_fields = [f for f in self.model_fields]
        assert len(all_fields) == 42, (
            f"ObservableVector must have exactly 42 fields (constitutional requirement). "
            f"Found {len(all_fields)}."
        )
        return self

    def missing_count(self) -> int:
        """Number of null (missing sensor) observables in this vector."""
        return sum(1 for f in self.model_fields if getattr(self, f) is None)

    def present_count(self) -> int:
        """Number of non-null observables in this vector."""
        return 42 - self.missing_count()

    def coverage_fraction(self) -> float:
        """Fraction of observables present [0, 1]."""
        return self.present_count() / 42

    model_config = {"frozen": True}