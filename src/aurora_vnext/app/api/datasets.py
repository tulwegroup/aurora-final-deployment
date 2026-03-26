"""
Aurora OSI vNext — Dataset API (STUB)
Implemented in Phase M

Endpoints (when implemented):
  GET /api/v1/datasets/summary/{id}
  GET /api/v1/datasets/package/{id}
  GET /api/v1/datasets/geojson/{id}
  GET /api/v1/datasets/raster-spec/{id}
  GET /api/v1/datasets/export/{id}    — admin only; encrypted + audit-logged

ARCHITECTURAL RULE: This layer is PURELY read-only from canonical storage.
Cell coloring thresholds in GeoJSON are sourced from tier_thresholds_used
in the canonical record — never recomputed here.
No import from core/* modules permitted.
"""

# Phase M implementation placeholder