"""
Aurora OSI vNext — Physics Consistency Score (STUB)
Phase B §6 | Implemented in Phase I

Responsibilities (when implemented):
  - Compute gravity data residual R_grav = ||W_d(g_obs - g_pred)||^2 (§6.1)
  - Compute Poisson physics residual R_phys = ||∇²Φ - 4πGρ||^2 (§6.2)
  - Compute Darcy flow residual R_darcy for fluid/hydrocarbon systems (§6.5)
  - Compute water-column residual R_wc for offshore systems (§6.5)
  - Compute physics consistency score Ψ_i = exp(-λ₁R_grav - λ₂R_phys) (§6.4)
  - Apply physics hard veto when residuals exceed tolerance bounds (§6.6)

Physics residuals are FIRST-CLASS OUTPUTS — they must be persisted in every
canonical scan cell record, not treated as internal diagnostic values.

CONSTITUTIONAL RULE: This is the ONLY location for physics consistency scoring
and physics residual computation.
"""

# Phase I implementation placeholder