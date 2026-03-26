"""
Aurora OSI vNext — Google Earth Engine Sensor Acquisition Service
Phase K §K.1 | Patent Breakthrough 1–3

Responsibility: fetch raw per-cell sensor stacks from Earth Engine (or
equivalent raster archive) and return typed RawStack objects.

Layer rule: This is a Layer-2 Service.
  - NO scoring formulas.
  - NO observable normalisation.
  - NO ACIF, tiering, or gate logic.
  - Returns ONLY raw (un-normalised) sensor values.

The caller (scan pipeline, Phase L) is responsible for passing stacks to:
  - services/offshore.py   (if environment == OFFSHORE)
  - services/gravity.py    (always)
  - services/harmonization.py (always)

CONSTITUTIONAL IMPORT GUARD: This file must never import from:
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.

GEE client is injected via `GEEClient` interface — the real implementation
uses the earthengine-api SDK; tests supply a `MockGEEClient`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.models.extraction_types import (
    RawBathymetricData,
    RawGravityData,
    RawMagneticData,
    RawOpticalStack,
    RawSARStack,
    RawThermalStack,
)


# ---------------------------------------------------------------------------
# Cell geometry descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CellGeometry:
    """Spatial descriptor for one scan cell."""
    cell_id: str
    scan_id: str
    lat_centre: float
    lon_centre: float
    resolution_m: float          # Cell side length in metres
    environment: str             # "ONSHORE" | "OFFSHORE" | "COMBINED"


# ---------------------------------------------------------------------------
# GEE client interface (dependency injection)
# ---------------------------------------------------------------------------

class GEEClient(ABC):
    """
    Abstract interface for the Earth Engine data source.
    Production implementation: earthengine-api SDK.
    Test implementation: MockGEEClient with synthetic pixel values.
    """

    @abstractmethod
    def fetch_optical(
        self,
        cell: CellGeometry,
        missions: list[str],
        date_start: str,
        date_end: str,
        max_cloud_cover: float,
    ) -> list[RawOpticalStack]:
        """Fetch TOA/BOA reflectance stacks for each available mission."""

    @abstractmethod
    def fetch_sar(
        self,
        cell: CellGeometry,
        missions: list[str],
        date_start: str,
        date_end: str,
    ) -> list[RawSARStack]:
        """Fetch SAR backscatter and coherence stacks."""

    @abstractmethod
    def fetch_thermal(
        self,
        cell: CellGeometry,
        missions: list[str],
        date_start: str,
        date_end: str,
    ) -> list[RawThermalStack]:
        """Fetch thermal infrared stacks."""

    @abstractmethod
    def fetch_gravity(self, cell: CellGeometry) -> Optional[RawGravityData]:
        """Fetch multi-orbit gravity measurements."""

    @abstractmethod
    def fetch_magnetic(self, cell: CellGeometry) -> Optional[RawMagneticData]:
        """Fetch aeromagnetic measurements."""

    @abstractmethod
    def fetch_bathymetric(self, cell: CellGeometry) -> Optional[RawBathymetricData]:
        """Fetch bathymetric/oceanographic data (offshore cells only)."""


# ---------------------------------------------------------------------------
# Raw sensor acquisition orchestrator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawSensorBundle:
    """
    Complete raw sensor bundle for one cell.
    All values are un-normalised; None indicates sensor absent or unavailable.
    """
    cell: CellGeometry
    optical_stacks: list[RawOpticalStack] = field(default_factory=list)
    sar_stacks: list[RawSARStack]         = field(default_factory=list)
    thermal_stacks: list[RawThermalStack] = field(default_factory=list)
    gravity: Optional[RawGravityData]     = None
    magnetic: Optional[RawMagneticData]   = None
    bathymetric: Optional[RawBathymetricData] = None

    @property
    def has_optical(self) -> bool:
        return bool(self.optical_stacks)

    @property
    def has_gravity(self) -> bool:
        return self.gravity is not None

    @property
    def has_bathymetric(self) -> bool:
        return self.bathymetric is not None


def acquire_raw_sensor_bundle(
    cell: CellGeometry,
    client: GEEClient,
    date_start: str,
    date_end: str,
    optical_missions: Optional[list[str]] = None,
    sar_missions: Optional[list[str]] = None,
    thermal_missions: Optional[list[str]] = None,
    max_cloud_cover: float = 0.20,
) -> RawSensorBundle:
    """
    Orchestrate all sensor acquisitions for one cell.

    Calls each fetch method independently — a failure in one sensor type
    does not block the others. Missing sensors are represented as empty
    lists / None values, which the harmonisation layer converts to
    MissingObservable with u_sensor_contribution = 1.0.

    Args:
        cell:              Cell spatial descriptor
        client:            GEEClient implementation (injected)
        date_start/end:    ISO date range for acquisition window
        optical_missions:  Preferred missions (default: Sentinel-2, Landsat-9)
        sar_missions:      Preferred SAR missions (default: Sentinel-1)
        thermal_missions:  Preferred thermal missions (default: ECOSTRESS, ASTER)
        max_cloud_cover:   Maximum cloud fraction for optical scenes

    Returns:
        RawSensorBundle with all available stacks.
    """
    opt_missions  = optical_missions  or ["Sentinel-2", "Landsat-9"]
    sar_missions_ = sar_missions      or ["Sentinel-1"]
    therm_missions = thermal_missions or ["ECOSTRESS", "ASTER"]

    optical  = client.fetch_optical(cell, opt_missions, date_start, date_end, max_cloud_cover)
    sar      = client.fetch_sar(cell, sar_missions_, date_start, date_end)
    thermal  = client.fetch_thermal(cell, therm_missions, date_start, date_end)
    gravity  = client.fetch_gravity(cell)
    magnetic = client.fetch_magnetic(cell)
    bathy    = client.fetch_bathymetric(cell) if cell.environment in ("OFFSHORE", "COMBINED") else None

    return RawSensorBundle(
        cell=cell,
        optical_stacks=optical,
        sar_stacks=sar,
        thermal_stacks=thermal,
        gravity=gravity,
        magnetic=magnetic,
        bathymetric=bathy,
    )


# ---------------------------------------------------------------------------
# Mock GEE client for testing / development
# ---------------------------------------------------------------------------

class MockGEEClient(GEEClient):
    """
    Synthetic GEE client for unit tests and pipeline dry-runs.
    Returns plausible raw values — NOT normalised, NOT scored.
    """

    def __init__(self, seed_values: Optional[dict[str, float]] = None):
        self._seed = seed_values or {}

    def fetch_optical(self, cell, missions, date_start, date_end, max_cloud_cover):
        results = []
        band_maps = {
            "Sentinel-2": {"B2": 0.04, "B3": 0.06, "B4": 0.08, "B5": 0.10,
                            "B8": 0.25, "B8A": 0.24, "B11": 0.35, "B12": 0.42},
            "Landsat-9":  {"B2": 0.04, "B3": 0.06, "B4": 0.09, "B5": 0.22,
                            "B6": 0.33, "B7": 0.40},
        }
        for mission in missions:
            if mission in band_maps:
                results.append(RawOpticalStack(
                    cell_id=cell.cell_id, scan_id=cell.scan_id,
                    mission=mission, scene_id=f"mock_{mission}_scene",
                    acquisition_date=date_start,
                    band_values=dict(band_maps[mission]),
                    cloud_cover_fraction=0.05,
                ))
        return results

    def fetch_sar(self, cell, missions, date_start, date_end):
        return [RawSARStack(
            cell_id=cell.cell_id, scan_id=cell.scan_id,
            mission="Sentinel-1", polarisation="VV",
            backscatter_vv=-12.5, backscatter_vh=-18.0,
            coherence=0.72, incidence_angle_deg=38.5,
            acquisition_date=date_start,
        )]

    def fetch_thermal(self, cell, missions, date_start, date_end):
        return [RawThermalStack(
            cell_id=cell.cell_id, scan_id=cell.scan_id,
            mission="ECOSTRESS",
            lst_kelvin=308.5, heat_flow_mw_m2=85.0,
            thermal_inertia=1500.0, emissivity=0.94,
            acquisition_date=date_start,
        )]

    def fetch_gravity(self, cell):
        return RawGravityData(
            cell_id=cell.cell_id, scan_id=cell.scan_id,
            free_air_leo_mgal=-2.5, free_air_meo_mgal=5.1,
            free_air_legacy_mgal=4.8,
            bouguer_anomaly_mgal=-22.0,
            vertical_gradient_eotvos=3200.0,
            terrain_elevation_m=450.0,
        )

    def fetch_magnetic(self, cell):
        return RawMagneticData(
            cell_id=cell.cell_id, scan_id=cell.scan_id,
            total_field_nt=48320.0, rtp_anomaly_nt=340.0,
            analytic_signal_nt_m=0.15,
            horizontal_derivative_nt_m=0.08,
            depth_to_source_m=1200.0,
        )

    def fetch_bathymetric(self, cell):
        if cell.environment not in ("OFFSHORE", "COMBINED"):
            return None
        return RawBathymetricData(
            cell_id=cell.cell_id, scan_id=cell.scan_id,
            water_depth_m=850.0,
            seafloor_slope_deg=2.5,
            sst_celsius=24.5,
            ssh_m=0.18,
            chlorophyll_mg_m3=0.8,
            backscatter_db=-15.0,
        )