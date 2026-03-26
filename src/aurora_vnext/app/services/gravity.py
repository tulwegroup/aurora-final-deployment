"""
Aurora OSI vNext — Multi-Orbit Gravity Decomposition Service
Phase K §K.3 | Phase B §6.3

Responsibility: Decompose raw multi-orbit gravity observations into
wavelength-separated components and produce a GravityComposite.

Layer rule: This is a Layer-2 Service.
  - NO scoring, tiering, gates, or ACIF logic.
  - Returns ONLY GravityComposite (raw, un-scored gravity data).
  - core/physics.py is the sole authority for residual computation.

Wavelength decomposition:
  g_long   ← MEO / legacy (long-wavelength: crustal, lithospheric structure)
  g_medium ← LEO (medium-wavelength: upper mantle, regional geology)
  g_short  ← Super-resolved via vertical gradient Γ_zz and height offset δh
  g_composite = g_long + g_medium + g_short

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models.extraction_types import GravityComposite, RawGravityData


# Default wavelength partition weights
_DEFAULT_WEIGHTS: dict[str, float] = {
    "meo_long_fraction":    0.70,
    "leo_medium_fraction":  0.85,
    "legacy_long_fraction": 0.30,
}

# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL PHYSICS PARAMETER: δh  (vertical separation between orbital levels)
# ─────────────────────────────────────────────────────────────────────────────
#
# CONSTITUTIONAL RULE:
#   δh MUST be supplied by the caller from Θ_c (commodity configuration).
#   The shallow-system fallback below exists for unit tests and mock pipelines
#   ONLY.  The scan pipeline (Phase L) is PROHIBITED from using this fallback;
#   it must fetch delta_h_m from the active commodity’s Θ_c parameter block.
#   Using this constant in production without a Θ_c override is a
#   physics_model_version violation and will be caught by the pipeline guard
#   in pipeline/scan_pipeline.py.
#
# See config/constants.py — DELTA_H_SHALLOW_FALLBACK_M for the versioning
# policy and DELTA_H_RANGE_MIN_M / DELTA_H_RANGE_MAX_M for allowed bounds.
# ─────────────────────────────────────────────────────────────────────────────
DELTA_H_SHALLOW_FALLBACK_M: float = 50.0
# ^ SHALLOW-SYSTEM FALLBACK ONLY — valid for lateritic/gossan/shallow offshore.
# ^ Production scan pipeline MUST override this with Θ_c.delta_h_m.
# ^ See commodity/library.py for per-family δh values.


def decompose_wavelength_bands(
    raw: RawGravityData,
    weights: Optional[dict[str, float]] = None,
) -> tuple[Optional[float], Optional[float]]:
    """
    §6.3 — Partition raw gravity into long-wavelength and medium-wavelength bands.

    Long-wavelength  ← weighted blend of MEO and legacy static model.
    Medium-wavelength ← LEO (temporally sensitive, regional fluid/mass changes).

    Returns:
        (g_long_mgal, g_medium_mgal) — both in mGal, either may be None.
    """
    w = weights or _DEFAULT_WEIGHTS

    g_long: Optional[float] = None
    if raw.free_air_meo_mgal is not None and raw.free_air_legacy_mgal is not None:
        g_long = (w.get("meo_long_fraction", 0.70) * raw.free_air_meo_mgal
                  + w.get("legacy_long_fraction", 0.30) * raw.free_air_legacy_mgal)
    elif raw.free_air_meo_mgal is not None:
        g_long = raw.free_air_meo_mgal
    elif raw.free_air_legacy_mgal is not None:
        g_long = raw.free_air_legacy_mgal

    g_medium: Optional[float] = None
    if raw.free_air_leo_mgal is not None:
        g_medium = w.get("leo_medium_fraction", 0.85) * raw.free_air_leo_mgal

    return g_long, g_medium


def super_resolve_short_wavelength(
    gamma_zz_eotvos: Optional[float],
    delta_h_m: float,           # REQUIRED — must be supplied from Θ_c; no default
) -> Optional[float]:
    """
    §6.3 — Super-resolve the short-wavelength gravity component.

    Formula:
      g_short [mGal] = Γ_zz [Eötvös] × 1e-4 [mGal·m / Eötvös] × δh [m]

    Factor breakdown:
      1e-4 [mGal·m / Eötvös]:
        Unit conversion: 1 Eötvös = 10⁻⁹ s⁻²; 1 mGal = 10⁻⁵ m/s²
        Γ_zz [E] → Γ_zz × 10⁻⁹ [s⁻²] = Γ_zz × 10⁻⁴ [mGal/m]
        Multiplied by δh [m] → result in [mGal].  ✓

      δh [m]  (DELTA_H_DEFAULT_M = 50 m by default):
        Vertical sampling interval — the height separation across which
        the gradient is applied.  See DELTA_H_DEFAULT_M docblock for full
        physical justification, allowed range, and versioning policy.

    Args:
        gamma_zz_eotvos: Vertical gravity gradient Γ_zz in Eötvös units.
        delta_h_m:       Vertical separation δh in metres.
                         DEFAULT = DELTA_H_DEFAULT_M (50 m).
                         Override via Θ_c for deep targets.

    Returns:
        g_short in mGal, or None if gradient unavailable.
    """
    if gamma_zz_eotvos is None or delta_h_m == 0:
        return None
    return gamma_zz_eotvos * 1e-4 * delta_h_m


def compose_gravity_signal(
    g_long: Optional[float],
    g_medium: Optional[float],
    g_short: Optional[float],
) -> Optional[float]:
    """
    §6.3 — Sum wavelength components: g_composite = g_long + g_medium + g_short.

    None components contribute 0 (treated as absent, not missing).
    Returns None only if ALL three are None.
    """
    if g_long is None and g_medium is None and g_short is None:
        return None
    return (g_long or 0.0) + (g_medium or 0.0) + (g_short or 0.0)


def build_gravity_composite(
    raw: RawGravityData,
    delta_h_m: float,           # REQUIRED — must be supplied from Θ_c; no default
    weights: Optional[dict[str, float]] = None,
) -> GravityComposite:
    """
    Full multi-orbit gravity decomposition for one cell.

    Steps:
      1. Decompose into long/medium bands.
      2. Super-resolve short wavelength via vertical gradient.
      3. Compose g_composite.

    Returns:
        GravityComposite with all components and audit metadata.
    """
    g_long, g_medium = decompose_wavelength_bands(raw, weights)
    g_short = super_resolve_short_wavelength(raw.vertical_gradient_eotvos, delta_h_m)
    g_composite = compose_gravity_signal(g_long, g_medium, g_short)

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
        delta_h_m=delta_h_m,
        orbit_sources_used=tuple(sources),
        super_resolution_applied=(raw.vertical_gradient_eotvos is not None),
    )