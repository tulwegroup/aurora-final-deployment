"""
Aurora OSI vNext — Scan History API (STUB)
Implemented in Phase M

Endpoints (when implemented):
  GET    /api/v1/scan/history        — paginated CanonicalScanSummary list
  GET    /api/v1/scan/{id}           — full CanonicalScan record
  DELETE /api/v1/scan/{id}           — admin only; audit record required
  POST   /api/v1/scan/{id}/reprocess — admin only; creates new versioned scan

ARCHITECTURAL RULE: All responses are read-only projections of CanonicalScan fields.
No field is recomputed. No threshold is derived. No score is recalculated.
"""

# Phase M implementation placeholder