"""
Aurora OSI vNext — Tiering Engine (STUB)
Phase B §13 | Implemented in Phase J

⚠️  SOLE TIERING AUTHORITY — THIS IS THE ONLY LOCATION WHERE TIERING IS COMPUTED ⚠️

Responsibilities (when implemented):
  - Derive tier thresholds {t1, t2, t3} per provenance rule (§13.3):
      aoi_percentile | commodity_frozen_default | ground_truth_calibrated | reprocessed_vX
  - Assign Tier(i) to each cell against frozen thresholds (§13.2)
  - Compute tier counts {N_T1, N_T2, N_T3, N_below} (§13.4)
  - Persist threshold provenance alongside threshold values

CONSTITUTIONAL RULE (Phase 0 v1.1, Rule 6):
  Thresholds are frozen at scan completion. No post-completion threshold
  substitution, router fallback, or streaming fallback is permitted.
  Threshold provenance is a required persisted field — not an optional annotation.
  Any threshold logic outside this file is a build violation.
"""

# Phase J implementation placeholder