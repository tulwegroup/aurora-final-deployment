"""
Aurora OSI vNext — GEE Worker to Observable Vector Bridge
Phase AU §AU.2 — Data Integration Layer

Transforms GEE worker cell output → canonical ObservableVector input

CONSTITUTIONAL ORDER:
  1. GEE worker delivers: raw S2 bands (B4, B8, B11, B12), S1, thermal, DEM
  2. Spectral extraction (spectral_extraction.py): B4,B8,B11,B12 → x_spec_1..8
  3. This module: build raw observable stack for normalisation
  4. Normalisation (core/normalisation.py): raw values → [0,1]
  5. Evidence scoring (core/evidence.py): normalised → component scores
  6. ACIF (core/scoring.py): assembly

No scoring logic here. Pure data mapping.
"""

from __future__ import annotations
from typing import Optional

from app.models.observable_vector import ObservableVector
from app.services.spectral_extraction import extract_spectral_indices_from_s2_bands


def build_raw_observable_stack_from_gee_cell(
    gee_cell: dict,
) -> dict[str, Optional[float]]:
    """
    Transform a single GEE worker cell output into a raw observable stack.
    
    Input: GEE cell dict with 's2', 's1', 'thermal', 'dem' keys
    Output: Dict mapping all 42 x_spec_*/x_sar_*/etc. keys to raw values
    
    The raw stack is the input to compute_scan_normalisation_params() in normalisation.py.
    All values remain in their native ranges (not yet normalised to [0,1]).
    Missing observables are None (not 0).
    
    Args:
        gee_cell: Output from GEE worker processing_batch() for one cell
                  {
                    'cell_id': str,
                    'center_lat': float,
                    'center_lon': float,
                    's2': {'valid': bool, 'B4': float, 'B8': float, 'B11': float, 'B12': float, ...},
                    's1': {'valid': bool, 'VV': float, 'VH': float},
                    'thermal': {'valid': bool, 'B10': float},
                    'dem': {'valid': bool, 'elevation': float, 'slope': float},
                  }
    
    Returns:
        {
            'x_spec_1': float or None,
            'x_spec_2': float or None,
            ...
            'x_sar_1': float or None,
            ...
            (42 total keys)
        }
    """
    raw_stack: dict[str, Optional[float]] = {}
    
    # =========================================================================
    # SPECTRAL OBSERVABLES (x_spec_1..8) — from S2 bands via bridge
    # =========================================================================
    s2_data = gee_cell.get('s2', {})
    spectral_indices = extract_spectral_indices_from_s2_bands(
        b4=s2_data.get('B4'),
        b8=s2_data.get('B8'),
        b11=s2_data.get('B11'),
        b12=s2_data.get('B12'),
    )
    for i in range(1, 9):
        raw_stack[f'x_spec_{i}'] = spectral_indices.get(f'x_spec_{i}')
    
    # =========================================================================
    # SAR OBSERVABLES (x_sar_1..6) — from S1 backscatter
    # =========================================================================
    s1_data = gee_cell.get('s1', {})
    if s1_data.get('valid', False):
        vv = s1_data.get('VV')
        vh = s1_data.get('VH')
        
        # SAR sub-scores (raw dB values, to be normalised later)
        raw_stack['x_sar_1'] = vv  # VV backscatter (dB)
        raw_stack['x_sar_2'] = vh  # VH backscatter (dB)
        raw_stack['x_sar_3'] = abs(vv - vh) if (vv and vh) else None  # Cross-pol difference
        raw_stack['x_sar_4'] = (abs(vv) + abs(vh)) / 2 if (vv and vh) else None  # Mean backscatter
        raw_stack['x_sar_5'] = abs(vv) / (abs(vh) + 1e-8) if (vv and vh) else None  # VV/VH ratio
        raw_stack['x_sar_6'] = None  # Coherence (placeholder)
    else:
        for i in range(1, 7):
            raw_stack[f'x_sar_{i}'] = None
    
    # =========================================================================
    # THERMAL OBSERVABLES (x_therm_1..4) — from L8 B10
    # =========================================================================
    thermal_data = gee_cell.get('thermal', {})
    if thermal_data.get('valid', False):
        b10_kelvin = thermal_data.get('B10')
        if b10_kelvin:
            # Thermal sub-scores (raw Kelvin, to be normalised)
            raw_stack['x_therm_1'] = b10_kelvin
            raw_stack['x_therm_2'] = max(0, b10_kelvin - 273.15)  # Celsius
            raw_stack['x_therm_3'] = None  # Emissivity (not in simplified model)
            raw_stack['x_therm_4'] = None  # Thermal inertia (not in simplified model)
        else:
            for i in range(1, 5):
                raw_stack[f'x_therm_{i}'] = None
    else:
        for i in range(1, 5):
            raw_stack[f'x_therm_{i}'] = None
    
    # =========================================================================
    # GRAVITY OBSERVABLES (x_grav_1..6) — placeholder (not in GEE output)
    # =========================================================================
    # Gravity data requires external global grids (Bouguer, FAA, etc.)
    # Not available from GEE worker; would come from separate service
    for i in range(1, 7):
        raw_stack[f'x_grav_{i}'] = None
    
    # =========================================================================
    # MAGNETIC OBSERVABLES (x_mag_1..5) — placeholder
    # =========================================================================
    # Magnetic data requires external global grids (IGRF, derivatives, etc.)
    # Not available from GEE worker; would come from separate service
    for i in range(1, 6):
        raw_stack[f'x_mag_{i}'] = None
    
    # =========================================================================
    # STRUCTURAL OBSERVABLES (x_struct_1..5) — from DEM
    # =========================================================================
    dem_data = gee_cell.get('dem', {})
    if dem_data.get('valid', False):
        elevation = dem_data.get('elevation')
        slope = dem_data.get('slope')
        
        raw_stack['x_struct_1'] = slope  # Slope (degrees)
        raw_stack['x_struct_2'] = elevation  # Elevation (meters)
        raw_stack['x_struct_3'] = None  # Curvature (not in simplified model)
        raw_stack['x_struct_4'] = None  # Aspect (not in simplified model)
        raw_stack['x_struct_5'] = None  # Lineament density (not in simplified model)
    else:
        for i in range(1, 6):
            raw_stack[f'x_struct_{i}'] = None
    
    # =========================================================================
    # HYDROLOGICAL OBSERVABLES (x_hydro_1..4) — placeholder
    # =========================================================================
    # Hydrological indices require soil moisture, precipitation data
    # Not available from GEE worker in simplified model
    for i in range(1, 5):
        raw_stack[f'x_hydro_{i}'] = None
    
    # =========================================================================
    # OFFSHORE OBSERVABLES (x_off_1..4) — only after CorrectedOffshoreCell gate
    # =========================================================================
    # Offshore corrections are applied separately in offshore correction module
    # Not populated here (onshore cells only)
    for i in range(1, 5):
        raw_stack[f'x_off_{i}'] = None
    
    return raw_stack


def build_observable_vector_from_raw_stack(
    raw_stack: dict[str, float],
) -> ObservableVector:
    """
    Construct a normalised ObservableVector from a raw observable stack.
    
    Note: This is BEFORE normalisation. Raw stack is in native ranges.
    Normalisation (z-score) is applied by core/normalisation.py.
    
    Args:
        raw_stack: Output from build_raw_observable_stack_from_gee_cell()
    
    Returns:
        ObservableVector with 42 fields (x_spec_1..8, x_sar_1..6, etc.)
        Values are raw (not normalised). None for missing observables.
    """
    return ObservableVector(
        x_spec_1=raw_stack.get('x_spec_1'),
        x_spec_2=raw_stack.get('x_spec_2'),
        x_spec_3=raw_stack.get('x_spec_3'),
        x_spec_4=raw_stack.get('x_spec_4'),
        x_spec_5=raw_stack.get('x_spec_5'),
        x_spec_6=raw_stack.get('x_spec_6'),
        x_spec_7=raw_stack.get('x_spec_7'),
        x_spec_8=raw_stack.get('x_spec_8'),
        x_sar_1=raw_stack.get('x_sar_1'),
        x_sar_2=raw_stack.get('x_sar_2'),
        x_sar_3=raw_stack.get('x_sar_3'),
        x_sar_4=raw_stack.get('x_sar_4'),
        x_sar_5=raw_stack.get('x_sar_5'),
        x_sar_6=raw_stack.get('x_sar_6'),
        x_therm_1=raw_stack.get('x_therm_1'),
        x_therm_2=raw_stack.get('x_therm_2'),
        x_therm_3=raw_stack.get('x_therm_3'),
        x_therm_4=raw_stack.get('x_therm_4'),
        x_grav_1=raw_stack.get('x_grav_1'),
        x_grav_2=raw_stack.get('x_grav_2'),
        x_grav_3=raw_stack.get('x_grav_3'),
        x_grav_4=raw_stack.get('x_grav_4'),
        x_grav_5=raw_stack.get('x_grav_5'),
        x_grav_6=raw_stack.get('x_grav_6'),
        x_mag_1=raw_stack.get('x_mag_1'),
        x_mag_2=raw_stack.get('x_mag_2'),
        x_mag_3=raw_stack.get('x_mag_3'),
        x_mag_4=raw_stack.get('x_mag_4'),
        x_mag_5=raw_stack.get('x_mag_5'),
        x_struct_1=raw_stack.get('x_struct_1'),
        x_struct_2=raw_stack.get('x_struct_2'),
        x_struct_3=raw_stack.get('x_struct_3'),
        x_struct_4=raw_stack.get('x_struct_4'),
        x_struct_5=raw_stack.get('x_struct_5'),
        x_hydro_1=raw_stack.get('x_hydro_1'),
        x_hydro_2=raw_stack.get('x_hydro_2'),
        x_hydro_3=raw_stack.get('x_hydro_3'),
        x_hydro_4=raw_stack.get('x_hydro_4'),
        x_off_1=raw_stack.get('x_off_1'),
        x_off_2=raw_stack.get('x_off_2'),
        x_off_3=raw_stack.get('x_off_3'),
        x_off_4=raw_stack.get('x_off_4'),
    )