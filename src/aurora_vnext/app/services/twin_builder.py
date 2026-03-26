"""
Aurora OSI vNext — Digital Twin Builder Service (STUB)
Phase B §15 | Implemented in Phase N

Responsibilities (when implemented):
  - Read frozen CanonicalScan record (read-only, post-freeze)
  - Project 2D scan cells to 3D voxel columns via depth kernel D^(c)(z) (§15.2)
  - Build DigitalTwinVoxel records with commodity_probs, expected_density,
    uncertainty, temporal_score, physics_residual
  - Write versioned voxel records to storage/twin.py

CONSTITUTIONAL RULE: Twin builder READS canonical outputs only.
It performs NO re-scoring, NO re-aggregation, NO re-tiering.
Every voxel value is a deterministic projection from the frozen canonical scan.
"""

# Phase N implementation placeholder