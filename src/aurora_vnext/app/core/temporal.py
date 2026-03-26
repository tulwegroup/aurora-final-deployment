"""
Aurora OSI vNext — Temporal Coherence Score (STUB)
Phase B §7 | Implemented in Phase I

Responsibilities (when implemented):
  - Compute InSAR persistence sub-score q_insar (§7.3)
  - Compute thermal stability sub-score q_therm (§7.3)
  - Compute vegetation stress persistence sub-score q_veg (§7.3)
  - Compute moisture stability sub-score q_moist (§7.3)
  - Compute temporal coherence T_i^(c) as WEIGHTED GEOMETRIC MEAN (§7.2)
  - Apply temporal hard veto when T_i < τ_temp_veto (§7.4)

CONSTITUTIONAL RULE: Geometric mean is constitutionally required — NOT arithmetic mean.
One unstable modality must strongly penalize the total score.
This is the ONLY location for temporal coherence computation.
"""

# Phase I implementation placeholder