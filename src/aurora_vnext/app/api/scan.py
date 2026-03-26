"""
Aurora OSI vNext — Scan Execution and Status API (STUB)
Implemented in Phase M

Endpoints (when implemented):
  POST /api/v1/scan/region
  POST /api/v1/scan/grid
  POST /api/v1/scan/polygon
  GET  /api/v1/scan/active          — returns ScanJob list (mutable execution state)
  GET  /api/v1/scan/status/{id}     — returns ScanJob if running, CanonicalScanSummary if COMPLETED
  POST /api/v1/scan/{id}/cancel

ARCHITECTURAL RULE: Scan submission routes interact with pipeline/task_queue.py.
Result-bearing routes (status when COMPLETED) read exclusively from canonical storage.
This router has NO import from core/scoring.py, core/tiering.py, or core/gates.py.
"""

# Phase M implementation placeholder