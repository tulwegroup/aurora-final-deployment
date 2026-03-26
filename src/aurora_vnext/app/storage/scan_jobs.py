"""
Aurora OSI vNext — Scan Job Store (STUB)
Implemented in Phase G

Manages the MUTABLE ScanJob execution records.
Completely separate from canonical_scans storage.

ScanJob records are archived (not deleted) after canonical freeze.
They contain NO score-equivalent fields — only pipeline execution state.
"""

# Phase G implementation placeholder