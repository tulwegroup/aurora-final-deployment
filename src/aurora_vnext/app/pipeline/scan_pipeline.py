"""
Aurora OSI vNext — Scan Execution Pipeline (STUB)
Implemented in Phase L

Implements the full 21-step scan pipeline from Phase C §7.
This is the only path through which a scan transitions from PENDING to COMPLETED.

KEY DISTINCTION (Phase C / Phase D refinement):
  MUTABLE PHASE   (steps 1–18): Creates and updates ScanJob throughout execution.
  FREEZE POINT    (step 19):    Writes CanonicalScan — single atomic, irreversible write.
  POST-FREEZE     (steps 20–21): Reads from frozen CanonicalScan ONLY — no mutation.

CONSTITUTIONAL RULE: canonical freeze is irreversible.
Storage layer rejects any subsequent write to the same scan_id.
"""

# Phase L implementation placeholder