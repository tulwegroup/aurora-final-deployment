"""
Aurora OSI vNext — Multi-Orbit Gravity Decomposition Service
Phase H §H.3 | Phase B §6.3

Decomposes gravity signals from multiple orbital platforms into wavelength
bands and super-resolves the short-wavelength component via the vertical
gradient tensor.

Wavelength decomposition:
  g_long   ← MEO / legacy (long-wavelength: crustal structure, lithosphere)
  g_medium ← LEO (medium-wavelength: upper mantle, regional geology)
  g_short  ← Super-resolved via vertical gradient Γ_zz and height offset δh
  g_composite = g_long + g_medium + g_short

This GravityComposite is:
  - Stored in harmonised_tensors.gravity_composite
  - Consumed by core/physics.py to compute gravity residuals R_grav
  - NOT scored here — this is a service (Layer 2), not a scientific module

No scoring. No ACIF. No tiering. No imports from core/scoring, tiering, gates.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.extraction_types import GravityComposite, RawGravityData


# ---------------------------------------------------------------------------
# §6.3 — Multi-orbit decomposition
# ---------------------------------------------------------------------------

def decompose_gravity_multi_orbit(
    raw: RawGravityData,
    orbit_weights: Optional[dict[str, float]] = None,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Partition raw gravity observations into long / medium / short wavelength
    components using a weighted spectral partition.

    Default orbit weights reflect typical signal-to-noise contributions:
      LEO (GRACE-FO): medium wavelength, high temporal resolution
      MEO (GOCE):     long wavelength, high spatial resolution
      Legacy (EGM):   long wavelength, static reference

    Args:
        raw:            RawGravityData with per-platform observations
        orbit_weights:  Optional override for {source: weight} fractions.
                        Must sum to 1.0 per wavelength band assignment.

    Returns:
        (g_long, g_medium, g_short) — all in mGal, any may be None.
    """
    # Default spectral partition weights
    _default_weights = {
        "meo_long_fraction": 0.70,     # MEO dominates long-wavelength
        "leo_medium_fraction": 0.85,   # LEO dominates medium-wavelength
        "legacy_long_fraction": 0.30,  # Legacy contributes to long-wavelength
    }
    w = orbit_weights or _default_weights

    # Long-wavelength: blend MEO and legacy observations
    g_long = None
    if raw.free_air_meo_mgal is not None and raw.free_air_legacy_mgal is not None:
        g_long = (
            w.get("meo_long_fraction", 0.70) * raw.free_air_meo_mgal
            + w.get("legacy_long_fraction", 0.30) * raw.free_air_legacy_mgal
        )
    elif raw.free_air_meo_mgal is not None:
        g_long = raw.free_air_meo_mgal
    elif raw.free_air_legacy_mgal is not None:
        g_long = raw.free_air_legacy_mgal

    # Medium-wavelength: LEO (temporally sensitive to fluid/mass changes)
    g_medium = None
    if raw.free_air_leo_mgal is not None:
        g_medium = w.get("leo_medium_fraction", 0.85) * raw.free_air_leo_mgal

    # Short-wavelength: cannot be isolated without vertical gradient (needs super-resolution)
    # Returned as None here — super_resolve_short_wavelength applies it separately
    g_short = None

    return g_long, g_medium, g_short


def super_resolve_short_wavelength(
    gamma_zz_eotvos: Optional[float],
    delta_h_m: Optional[float],
) -> Optional[float]:
    """
    Super-resolve the short-wavelength gravity component using the vertical
    gradient tensor Γ_zz (§6.3).

    Short-wavelength signal: g_short ≈ Γ_zz × δh
    where:
      Γ_zz = vertical gradient of vertical gravity (Eötvös, 1 Eötvös = 1e-9 s⁻²)
      δh = height separation between observing platform levels (m)

    This reveals subsurface density contrasts at finer spatial resolution
    than satellite altitude alone permits.

    Returns:
        g_short in mGal, or None if either input is unavailable.
    """
    if gamma_zz_eotvos is None or delta_h_m is None or delta_h_m == 0:
        return None

    # Convert Eötvös to mGal/m: 1 Eötvös = 1e-9 s⁻² = 1e-4 mGal/m
    gamma_zz_mgal_m = gamma_zz_eotvos * 1e-4
    g_short = gamma_zz_mgal_m * delta_h_m
    return g_short


def compose_g_composite(
    g_long: Optional[float],
    g_medium: Optional[float],
    g_short: Optional[float],
) -> Optional[float]:
    """
    Sum the three wavelength components into a composite gravity signal.

    g_composite = g_long + g_medium + g_short

    Any None component is treated as zero contribution (not excluded from sum)
    unless ALL three are None (no gravity data available).

    Returns:
        g_composite in mGal, or None if no components available.
    """
    if g_long is None and g_medium is None and g_short is None:
        return None
    return (g_long or 0.0) + (g_medium or 0.0) + (g_short or 0.0)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def build_gravity_composite(
    raw: RawGravityData,
    orbit_weights: Optional[dict[str, float]] = None,
) -> GravityComposite:
    """
    Full multi-orbit gravity decomposition pipeline for one cell.

    1. Decompose into wavelength bands (decompose_gravity_multi_orbit)
    2. Super-resolve short wavelength if vertical gradient available
    3. Compose into g_composite

    Returns:
        GravityComposite with all components and metadata.
    """
    g_long, g_medium, _ = decompose_gravity_multi_orbit(raw, orbit_weights)

    # Super-resolve short wavelength using vertical gradient tensor
    g_short = super_resolve_short_wavelength(
        gamma_zz_eotvos=raw.vertical_gradient_eotvos,
        delta_h_m=50.0,  # Default 50m platform height separation
    )

    g_composite = compose_g_composite(g_long, g_medium, g_short)

    # Determine which orbit sources contributed
    sources: list[str] = []
    if raw.free_air_leo_mgal is not None:
        sources.append("LEO")
    if raw.free_air_meo_mgal is not None:
        sources.append("MEO")
    if raw.free_air_legacy_mgal is not None:
        sources.append("legacy")

    return GravityComposite(
        cell_id=raw.cell_id,
        scan_id=raw.scan_id,
        g_long_mgal=g_long,
        g_medium_mgal=g_medium,
        g_short_mgal=g_short,
        g_composite_mgal=g_composite,
        delta_h_m=50.0,
        orbit_sources_used=tuple(sources),
        super_resolution_applied=(raw.vertical_gradient_eotvos is not None),
    )