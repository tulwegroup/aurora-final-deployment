"""
Aurora OSI vNext — Observable Extraction (STUB)
Phase B §3, §4.1 | Implemented in Phase H

Responsibilities (when implemented):
  - Normalize raw sensor values to canonical observable vector (§3.2)
  - Handle missing observables with null value + u_sensor=1.0 (§3.3)
  - Compute modality sub-scores S_i, R_i, T_E_i, G_i, M_i, L_i, H_i, O_i (§4.1)
  - Build canonical ObservableVector per scan cell
  - Offshore sub-score extraction ONLY after CorrectedOffshoreCell provided (§9.4)

CONSTITUTIONAL RULE: This is the ONLY location for observable normalization
and modality sub-score extraction. No other module may normalize observables.
"""

# Phase H implementation placeholder
# All functions will be implemented in Phase H