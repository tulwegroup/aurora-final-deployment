"""
Aurora OSI vNext — Spectral Index Extraction Service
Phase AU §AU.2 — Spectral Observable Bridge

CONSTITUTIONAL RULE: This is the ONLY location for extracting spectral indices
from raw Sentinel-2 bands and converting them to canonical x_spec_* observables.

INPUT: Raw S2 bands (B4, B8, B11, B12) from GEE worker
OUTPUT: x_spec_1..8 observable values (raw, pre-normalisation)

ORDER (CONSTITUTIONAL):
  1. Raw sensor values (B4, B8, B11, B12)
  2. Spectral index computation (this module)
  3. Observable vector population
  4. Normalisation (core/normalisation.py)
  5. Component scoring (core/evidence.py, etc.)
  6. ACIF assembly (core/scoring.py)

No scoring. No ACIF. No imports from core/scoring, tiering, gates.
"""

from __future__ import annotations
from typing import Optional


def extract_spectral_indices_from_s2_bands(
    b4: Optional[float],
    b8: Optional[float],
    b11: Optional[float],
    b12: Optional[float],
) -> dict[str, Optional[float]]:
    """
    Extract spectral observable indices from Sentinel-2 raw bands.
    
    All outputs are raw values in their native ranges.
    Normalisation to [0, 1] occurs later in core/normalisation.py.
    
    Args:
        b4:   Red band (wavelength ~665 nm)
        b8:   Near-infrared band (~842 nm)
        b11:  SWIR1 band (~1610 nm)
        b12:  SWIR2 band (~2190 nm)
    
    Returns:
        dict mapping x_spec_1..8 to raw (non-normalised) values or None if missing
    
    Missing band → corresponding observable is None (not 0)
    Constitutional: missing ≠ zero (missing is unknown, zero is measured zero)
    """
    # Guard: if any required band is missing, return all None
    if b4 is None or b8 is None or b11 is None or b12 is None:
        return {
            'x_spec_1': None,
            'x_spec_2': None,
            'x_spec_3': None,
            'x_spec_4': None,
            'x_spec_5': None,
            'x_spec_6': None,
            'x_spec_7': None,
            'x_spec_8': None,
        }
    
    eps = 1e-8  # Avoid division by zero
    
    # x_spec_1: Clay Alteration Index (CAI)
    # Formula: (B11 + B4) / (B11 - B4)
    # High clay absorption in SWIR → high value
    clay_index = (b11 + b4) / (b11 - b4 + eps)
    
    # x_spec_2: Ferric Iron Ratio
    # Formula: B4 / B8
    # Iron oxide absorption in Red vs NIR
    ferric_ratio = b4 / (b8 + eps)
    
    # x_spec_3: Normalized Difference Vegetation Index (NDVI)
    # Formula: (B8 - B4) / (B8 + B4)
    # Vegetation signal (-1 to +1, typical 0–0.8 for vegetation)
    ndvi = (b8 - b4) / (b8 + b4 + eps)
    
    # x_spec_4: Bare Soil Index (BSI)
    # Requires B2 (blue) which we don't have in this simplified model
    # Fallback: use a proxy combining available bands
    # BSI proxy: (B11 + B4) - (B8 + B12) / (B11 + B4) + (B8 + B12)
    bsi_proxy = ((b11 + b4) - (b8 + b12)) / ((b11 + b4) + (b8 + b12) + eps)
    
    # x_spec_5: Normalized Difference Moisture Index (NDMI)
    # Formula: (B8 - B11) / (B8 + B11)
    # Soil/vegetation moisture content
    ndmi = (b8 - b11) / (b8 + b11 + eps)
    
    # x_spec_6: SWIR Ratio (B11/B12)
    # Hydrothermal alteration proxy
    swir_ratio = b11 / (b12 + eps)
    
    # x_spec_7: Red-SWIR1 Ratio
    # Mineral absorption feature depth
    red_swir1_ratio = b4 / (b11 + eps)
    
    # x_spec_8: NIR-SWIR1 Ratio
    # Vegetation-mineral discrimination
    nir_swir1_ratio = b8 / (b11 + eps)
    
    return {
        'x_spec_1': float(clay_index),
        'x_spec_2': float(ferric_ratio),
        'x_spec_3': float(ndvi),
        'x_spec_4': float(bsi_proxy),
        'x_spec_5': float(ndmi),
        'x_spec_6': float(swir_ratio),
        'x_spec_7': float(red_swir1_ratio),
        'x_spec_8': float(nir_swir1_ratio),
    }


def extract_spectral_observables_from_gee_result(
    gee_s2_output: dict,
) -> dict[str, Optional[float]]:
    """
    Convenience wrapper: extract observables from GEE worker S2 output dict.
    
    Args:
        gee_s2_output: Dict with 'B4', 'B8', 'B11', 'B12', 'valid' keys
                       (output from geeWorkerService.fetch_sentinel2)
    
    Returns:
        dict mapping x_spec_1..8 to values
        
    Constitutional: if gee_s2_output['valid'] is False, all observables are None
    """
    if not gee_s2_output.get('valid', False):
        return {f'x_spec_{i}': None for i in range(1, 9)}
    
    return extract_spectral_indices_from_s2_bands(
        b4=gee_s2_output.get('B4'),
        b8=gee_s2_output.get('B8'),
        b11=gee_s2_output.get('B11'),
        b12=gee_s2_output.get('B12'),
    )