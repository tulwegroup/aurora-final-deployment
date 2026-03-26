"""
Aurora OSI vNext — Offshore Correction Pipeline (STUB)
Phase B §9 | Implemented in Phase H

⚠️  MANDATORY PRECONDITION — No offshore cell may proceed to observable
extraction or scoring without passing through this correction pipeline. ⚠️

Responsibilities (when implemented):
  - Determine if a cell is offshore (is_offshore_cell)
  - Apply water-column reflectance correction R_b (§9.2)
  - Compute oceanographic anomalies SST', SSH', Chl' (§9.3)
  - Apply water-column gravity correction g_corr (§9.5)
  - Raise OffshoreGateViolation if any correction step fails

CONSTITUTIONAL RULE: Failure to apply offshore correction before scoring
is a constitutional violation. The pipeline enforces this as a blocking gate.
"""

# Phase H implementation placeholder