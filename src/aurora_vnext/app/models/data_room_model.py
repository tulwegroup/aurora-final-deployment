"""
Aurora OSI vNext — Data Room Export Models
Phase R §R.1

Defines the manifest schema for a signed data-room export package.

A data room package is a ZIP archive containing:
  canonical_scan.json        — CanonicalScan record (verbatim)
  geojson_tier_layer.geojson — GeoJSON FeatureCollection of scan cells
  twin_voxels.json           — DigitalTwinVoxel records (verbatim)
  audit_trail.jsonl          — Append-only audit log records for this scan_id
  manifest.json              — This model, including SHA-256 hashes of all above

CONSTITUTIONAL RULES — Phase R:
  Rule 1: No scientific fields are added, derived, or recomputed in this module.
  Rule 2: Manifest values are sourced from stored canonical records only.
  Rule 3: SHA-256 hashes verify artifact integrity — they are not scientific values.
  Rule 4: version_registry in manifest is copied verbatim from CanonicalScan.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ArtifactRecord(BaseModel):
    """One file artifact in the data room package."""
    filename: str
    sha256: str                          # hex digest of file contents
    size_bytes: int
    content_type: str                    # MIME type
    description: str
    model_config = {"frozen": True}


class ScanLineage(BaseModel):
    """Lineage chain for reprocessed scans."""
    scan_id: str
    parent_scan_id: Optional[str]        # None if original
    migration_class: Optional[str]       # A / B / C / None (native scan)
    migration_notes: Optional[str]
    reprocess_reason: Optional[str]
    model_config = {"frozen": True}


class DataRoomManifest(BaseModel):
    """
    Export manifest for one data room package.

    Every field is sourced from stored canonical records — none are derived.
    SHA-256 hashes are computed over the serialised artifact bytes at export time.
    version_registry is copied verbatim from CanonicalScan.version_registry.

    PROOF: No scientific constant, threshold, or formula appears in this schema.
    Numeric fields: size_bytes (file size), sha256 (hash string), export_duration_ms
    (infrastructure timing). None are physics values.
    """
    # Package identity
    manifest_version:  str = "1.0"
    package_id:        str                    # UUID generated at export time
    created_at:        str                    # ISO timestamp
    created_by_email:  str

    # Scan identity — verbatim from CanonicalScan
    scan_id:           str
    commodity:         Optional[str]
    scan_tier:         Optional[str]
    environment:       Optional[str]
    scan_completed_at: Optional[str]          # CanonicalScan.completed_at — verbatim

    # Version registry — verbatim copy from CanonicalScan.version_registry
    version_registry:  Optional[dict]

    # Lineage
    lineage:           ScanLineage

    # Artifact inventory with integrity hashes
    artifacts:         list[ArtifactRecord]

    # Package integrity — SHA-256 of manifest.json itself (computed last)
    manifest_sha256:   Optional[str] = None   # filled after manifest serialisation

    # Infrastructure metadata
    export_duration_ms: Optional[int] = None
    aurora_env:         Optional[str] = None

    model_config = {"frozen": False}          # manifest_sha256 filled after init


class MigrationRecord(BaseModel):
    """
    One record in the migration execution log.
    Written to DB and included in migration completion proof.
    """
    scan_id:           str
    migration_class:   str               # A / B / C
    source_file_line:  Optional[int]
    missing_fields:    list[str]
    db_status:         str               # written / skipped / error
    error_message:     Optional[str]
    canonical_status:  str               # COMPLETED / MIGRATION_STUB
    executed_at:       str               # ISO timestamp
    dry_run:           bool
    model_config = {"frozen": True}


class MigrationRunReport(BaseModel):
    """Full report for one migration execution run."""
    run_id:         str
    run_at:         str
    dry_run:        bool
    input_file:     str
    counts:         dict[str, int]       # {A, B, C, skipped, error}
    records:        list[MigrationRecord]
    proof_summary:  dict                 # filled by completion proof generator
    model_config = {"frozen": True}