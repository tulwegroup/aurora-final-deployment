"""
Aurora OSI vNext — Mineral System Logic Registry
Phase AB §AB.2

Approved mineral-system logic for geological interpretation grounding.

Each entry defines the expected geoscientific drivers, deposit models,
known signatures, and key observables for a given commodity.

CONSTITUTIONAL RULES:
  Rule 1: Entries in this registry are APPROVED geological knowledge.
          The report engine is permitted to cite them as grounding context.
  Rule 2: No entry modifies scores, thresholds, tiers, or ACIF.
          This registry informs interpretation only.
  Rule 3: Every entry carries a version string. The report audit trail
          records mineral_system_logic_version at report generation time.
  Rule 4: No import from core/*.

REAL-WORLD GROUNDING:
  Deposit models sourced from:
  - USGS Mineral Deposit Models (Cox & Singer 1986; Hofstra & Kreiner 2020)
  - CRIRSCO reporting standards
  - GSA / national geological survey commodity guides
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


REGISTRY_VERSION = "1.0.0"


@dataclass(frozen=True)
class MineralSystemEntry:
    """
    Approved geological knowledge for one commodity.

    deposit_models:     List of recognised deposit model names (USGS / CRIRSCO)
    expected_drivers:   Observable types expected to show positive signal for this commodity
    structural_context: Expected structural setting description
    key_observables:    Canonical observable keys that typically carry diagnostic signal
    geophysical_signature: Expected geophysical expression in the canonical feature space
    uncertainty_note:   Standard uncertainty caveat for this commodity
    known_false_positives: Common false positive situations to flag in interpretation
    version:            Entry version string
    """
    commodity:             str
    deposit_models:        tuple[str, ...]
    expected_drivers:      tuple[str, ...]
    structural_context:    str
    key_observables:       tuple[str, ...]    # canonical observable keys e.g. x_spec_7, x_grav_1
    geophysical_signature: str
    uncertainty_note:      str
    known_false_positives: tuple[str, ...]
    version:               str


_REGISTRY: dict[str, MineralSystemEntry] = {

    "gold": MineralSystemEntry(
        commodity          = "gold",
        deposit_models     = (
            "Orogenic gold (USGS model 36a)",
            "Epithermal low-sulphidation (USGS model 25a)",
            "Epithermal high-sulphidation (USGS model 25b)",
            "Carlin-type sediment-hosted (USGS model 26a)",
            "IOCG-associated gold",
        ),
        expected_drivers   = (
            "Hydrothermal alteration zones (SWIR spectral signature)",
            "Structural corridors and shear zones",
            "Gravity lows associated with granitoid intrusions",
            "Iron oxide / gossanous outcrop (optical spectral)",
            "Linear magnetic lows (demagnetisation in alteration zones)",
        ),
        structural_context = (
            "Gold mineralisation commonly associated with crustal-scale shear zones, "
            "brittle-ductile transition zones, and second- or third-order splays. "
            "Favourable contacts between competent and incompetent lithologies."
        ),
        key_observables    = (
            "x_spec_7", "x_spec_8",    # SWIR1, SWIR2 — alteration clay minerals
            "x_grav_1", "x_grav_5",    # Bouguer, residual short-wavelength
            "x_mag_2",                  # RTP anomaly
            "x_struct_1", "x_struct_2", # structural fabric
        ),
        geophysical_signature = (
            "Residual gravity low over granitoid bodies. Magnetic low over "
            "propylitic / phyllic alteration zones. Short-wavelength structural "
            "lineaments in enhanced analytic signal."
        ),
        uncertainty_note   = (
            "Spectral alteration signatures are not unique to gold; argillic "
            "alteration is common in many geological settings. Gravity and magnetic "
            "signatures require multi-observable confirmation. Remote sensing cannot "
            "confirm grade, depth extent, or continuity."
        ),
        known_false_positives = (
            "Laterite / deep weathering profiles producing similar SWIR signatures",
            "Unrelated granitoid intrusions producing gravity lows",
            "Regional metamorphic fabrics mimicking structural corridors",
        ),
        version = "1.0.0",
    ),

    "copper": MineralSystemEntry(
        commodity          = "copper",
        deposit_models     = (
            "Porphyry copper (USGS model 17)",
            "IOCG (iron oxide copper-gold, USGS model 24b)",
            "Volcanogenic massive sulphide (VMS, USGS model 28a)",
            "Sediment-hosted stratiform copper (USGS model 30b)",
        ),
        expected_drivers   = (
            "Alteration haloes around intrusive centres (potassic, phyllic, propylitic)",
            "Circular gravity anomaly patterns over porphyry systems",
            "Iron oxide surface expression (ASTER/optical)",
            "Magnetic highs over magnetite-bearing intrusions",
        ),
        structural_context = (
            "Porphyry systems cluster in convergent margin settings above subduction zones. "
            "IOCG systems in compressional to extensional transition settings with deep-crustal "
            "fluid pathways. VMS systems in marine volcanic arc or back-arc basins."
        ),
        key_observables    = (
            "x_spec_3", "x_spec_7",    # Red / SWIR — iron oxide, alteration
            "x_grav_1", "x_grav_4",    # Bouguer, medium-wavelength residual
            "x_mag_1", "x_mag_4",      # Total field, horizontal derivative
            "x_therm_1",               # Thermal — hydrothermal heat flow
        ),
        geophysical_signature = (
            "Concentric geophysical zonation over porphyry centres: central magnetic high "
            "(magnetite-stable potassic zone), annular magnetic low (magnetite-destructive "
            "phyllic), peripheral gravity high (dense dyke swarms). Elevated thermal flux."
        ),
        uncertainty_note   = (
            "Alteration zonation pattern is diagnostic but requires multi-observable "
            "confirmation. Many porphyry-like geophysical signatures are barren. "
            "Depth and grade cannot be inferred from surface remote sensing alone."
        ),
        known_false_positives = (
            "Mafic / ultramafic intrusions producing similar magnetic patterns",
            "Unrelated iron oxide formation (BIF, ferricrete) producing optical signatures",
            "Basinal thermal anomalies unrelated to mineralisation",
        ),
        version = "1.0.0",
    ),

    "lithium": MineralSystemEntry(
        commodity          = "lithium",
        deposit_models     = (
            "Pegmatite-hosted spodumene (LCT-type)",
            "Salar / continental brine (evaporite-hosted)",
            "Hectorite clay (lacustrine volcanic)",
        ),
        expected_drivers   = (
            "Granitic / pegmatitic host rock expression in spectral data",
            "Evaporite basin geomorphology for salar targets",
            "Structural trapping in continental rift settings",
            "Gravity low over pegmatite/granitic bodies",
        ),
        structural_context = (
            "Pegmatite Li in late-stage leucogranite systems, commonly in metamorphic "
            "belts or post-collisional settings. Salar brines in high-altitude arid "
            "basins with evaporitic sequences and active or palaeo-hydrothermal input."
        ),
        key_observables    = (
            "x_spec_4", "x_spec_6",    # NIR / NIRn — vegetation stress, mineral expression
            "x_grav_3", "x_grav_5",    # Long-wavelength, short-wavelength gravity
            "x_hydro_1", "x_hydro_2",  # Hydrological indicators
            "x_therm_2",               # Heat flow — salar hydrothermal
        ),
        geophysical_signature = (
            "Gravity low over leucogranite / pegmatite bodies. Flat magnetic signature. "
            "For salars: low-relief basins with surface expression in SWIR bands, "
            "strong thermal anomalies from solar-heated brine."
        ),
        uncertainty_note   = (
            "Li is not directly detectable by remote sensing. Spectral and geophysical "
            "signatures indicate host rock or geological setting only. Brine chemistry, "
            "evaporation rates, and resource concentration require ground validation."
        ),
        known_false_positives = (
            "Barren leucogranites with no Li enrichment",
            "Non-Li evaporite basins with similar morphology",
            "Mica-rich metamorphic terranes producing similar spectral signatures",
        ),
        version = "1.0.0",
    ),

    "nickel": MineralSystemEntry(
        commodity          = "nickel",
        deposit_models     = (
            "Magmatic Ni-Cu-PGE sulphide (USGS model 5a)",
            "Laterite Ni (saprolite / limonite type)",
            "Komatiite-hosted Ni sulphide",
        ),
        expected_drivers   = (
            "Mafic / ultramafic host rocks (gravity high, magnetic high)",
            "Thermal anomaly from cooling intrusions or active komatiites",
            "Structural depressions hosting komatiitic flows",
        ),
        structural_context = (
            "Magmatic Ni sulphides in basal portions of mafic-ultramafic intrusions "
            "or komatiitic flows in Archean greenstone belts. Lateritic Ni developed "
            "over ultramafic basement under deep tropical weathering conditions."
        ),
        key_observables    = (
            "x_grav_1", "x_grav_2",    # Bouguer, composite — mafic density
            "x_mag_1", "x_mag_3",      # Total field, analytic signal
            "x_therm_1", "x_therm_3",  # Thermal, thermal inertia
            "x_spec_5",                # NIR — vegetation/regolith
        ),
        geophysical_signature = (
            "Gravity high and magnetic high pair over ultramafic / mafic bodies. "
            "Thermal inertia contrast at contact zones. Analytic signal picks up "
            "intrusive contacts and dyke swarms."
        ),
        uncertainty_note   = (
            "Mafic/ultramafic geophysical expression is common and does not imply "
            "sulphide mineralisation. Ni tenor, sulphide saturation, and structural "
            "setting require geochemical and drill confirmation."
        ),
        known_false_positives = (
            "Barren mafic intrusions (gabbros, dolerites)",
            "Banded Iron Formation producing magnetic highs",
            "Laterite profiles over non-ultramafic basement",
        ),
        version = "1.0.0",
    ),
}


def get_entry(commodity: str) -> Optional[MineralSystemEntry]:
    return _REGISTRY.get(commodity.lower())


def list_commodities() -> list[str]:
    return sorted(_REGISTRY.keys())


def registry_version() -> str:
    return REGISTRY_VERSION