"""
Aurora OSI vNext — Multi-Orbit Gravity Decomposition Service (STUB)
Phase B §6.3 | Implemented in Phase H

Responsibilities (when implemented):
  - Decompose gravity from LEO, MEO, legacy missions into long/medium/short wavelengths
  - Super-resolve short-wavelength component via vertical gradient tensor (§6.3)
  - Produce g_composite per cell for physics module consumption

Note: Gravity decomposition is a SERVICE (sensor preprocessing).
The physics residuals computed from g_composite live exclusively in core/physics.py.
"""

# Phase H implementation placeholder