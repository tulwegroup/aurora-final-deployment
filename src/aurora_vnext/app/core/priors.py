"""
Aurora OSI vNext — Province Prior Score (STUB)
Phase B §8 | Implemented in Phase I

Responsibilities (when implemented):
  - Look up province prior Π^(c)(r_i) from tectono-stratigraphic database (§8.2)
  - Apply province hard veto: P_i^(c) = 0 for geologically impossible provinces (§8.3)
  - Compute Bayesian posterior update when ground-truth calibration data available (§8.4)
  - Store posterior as new province_prior_version — never overwrite baseline prior

CONSTITUTIONAL RULE: Province impossibility triggers P = 0 (absolute veto),
not a low score. By the multiplicative ACIF structure, P = 0 zeros the full cell score.
This is the ONLY location for province prior computation.
"""

# Phase I implementation placeholder