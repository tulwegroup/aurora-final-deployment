"""
Aurora OSI vNext — ScanJob Model (STUB)
Implemented in Phase F

ScanJob tracks the MUTABLE state of a scan during pipeline execution.
It is a completely separate type from CanonicalScan.

KEY DISTINCTION (Phase C refinement note):
  ScanJob   = mutable execution record (exists during pipeline processing)
  CanonicalScan = immutable result record (written once at canonical freeze)

ScanJob contains NO score-equivalent fields. It carries only:
  - Pipeline execution state (stage, progress, timestamps)
  - Error details if the pipeline fails
  - Reference to the scan_id for which it is executing

ScanJob is archived after canonical freeze. It is never exposed
through result-bearing API endpoints.
"""

# Phase F implementation placeholder