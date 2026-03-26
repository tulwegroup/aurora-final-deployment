"""
Aurora OSI vNext — Reprocess Controller (STUB)
Phase B §16 | Implemented in Phase L

Responsibilities (when implemented):
  - Create new ScanJob + new CanonicalScan record with parent_scan_id set
  - Copy AOI and bounds from parent scan
  - Run full pipeline with updated Θ_c parameters
  - Write audit record BEFORE starting reprocess
  - Persist reprocess lineage: {parent_id → new_id, changed fields, actor, timestamp}
"""

# Phase L implementation placeholder