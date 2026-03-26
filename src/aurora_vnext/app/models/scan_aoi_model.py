"""
Aurora OSI vNext — Scan AOI Model
Phase AA §AA.1

Defines the immutable ScanAOI record for area-of-interest scan initiation.

CONSTITUTIONAL RULES:
  Rule 1 (Immutability): Once created, a ScanAOI record is never mutated.
          Any geometry change requires a new ScanAOI with a new aoi_id.
  Rule 2 (Cryptographic enforcement): geometry_hash is SHA-256 of the
          canonical JSON-serialised, sorted, normalised geometry coordinates.
          Stored at creation. Any geometry drift is detectable.
  Rule 3 (Versioning): aoi_version starts at 1. If a user adjusts the
          geometry, a new ScanAOI is created with source_aoi_id pointing
          to the original.
  Rule 4 (Reproducibility): All scans derived from this AOI reference both
          aoi_id and geometry_hash. These are immutable after save.
  Rule 5: No ACIF, no tier computation, no scientific scoring in this layer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class GeometryType(str, Enum):
    POLYGON   = "polygon"
    RECTANGLE = "rectangle"
    CIRCLE    = "circle"     # stored as polygon after server-side conversion


class SourceType(str, Enum):
    DRAWN             = "drawn"
    UPLOADED_KML      = "uploaded_kml"
    UPLOADED_GEOJSON  = "uploaded_geojson"
    IMPORTED_BOUNDARY = "imported_boundary"


class ValidationStatus(str, Enum):
    PENDING  = "pending"
    VALID    = "valid"
    INVALID  = "invalid"


class EnvironmentClassification(str, Enum):
    ONSHORE  = "onshore"
    OFFSHORE = "offshore"
    MIXED    = "mixed"
    UNKNOWN  = "unknown"


def _canonical_geometry_bytes(geometry: dict) -> bytes:
    """
    Produce deterministic bytes for geometry hashing.

    Sorts all dict keys recursively; truncates coordinate precision to 8
    decimal places to absorb floating-point noise while preserving
    sub-metre accuracy. Returns UTF-8 encoded JSON.

    PROOF: same geometry always produces the same bytes — deterministic
    because sort_keys=True and coordinate values are rounded before serialise.
    """
    def _normalise(obj):
        if isinstance(obj, dict):
            return {k: _normalise(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_normalise(i) for i in obj]
        if isinstance(obj, float):
            return round(obj, 8)
        return obj

    normalised = _normalise(geometry)
    return json.dumps(normalised, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_geometry_hash(geometry: dict) -> str:
    """
    SHA-256 of the canonical normalised geometry bytes.
    Returns lowercase hex string (64 chars).
    """
    return hashlib.sha256(_canonical_geometry_bytes(geometry)).hexdigest()


@dataclass(frozen=True)
class ScanAOI:
    """
    Immutable area-of-interest record.

    geometry: GeoJSON-compatible dict — coordinates in WGS84.
    geometry_hash: SHA-256 of normalised geometry. Computed at creation and
                   stored. Never recomputed — any mismatch indicates mutation.
    aoi_version: starts at 1; incremented only by creating a NEW ScanAOI.
    canonical_geometry_snapshot: verbatim copy of geometry at creation time,
                                  stored separately to detect any post-creation drift.
    """
    aoi_id:                     str
    geometry_type:              GeometryType
    geometry:                   dict              # GeoJSON coordinates dict
    geometry_hash:              str               # SHA-256 hex, computed at creation
    canonical_geometry_snapshot: str              # JSON-serialised verbatim snapshot
    aoi_version:                int
    source_aoi_id:              Optional[str]     # if derived from a prior AOI
    centroid:                   dict              # {"lat": float, "lon": float}
    bbox:                       dict              # {"min_lat","max_lat","min_lon","max_lon"}
    area_km2:                   float
    created_by:                 str
    created_at:                 str               # ISO 8601 UTC
    source_type:                SourceType
    source_file_hash:           Optional[str]     # SHA-256 of uploaded file, if applicable
    map_projection:             str               # always "EPSG:4326" after normalisation
    validation_status:          ValidationStatus
    environment:                EnvironmentClassification
    validation_errors:          tuple[str, ...]   # empty if valid

    def verify_geometry_integrity(self) -> bool:
        """
        Recompute geometry_hash from stored geometry and compare.
        Returns True if geometry is intact.

        PROOF: any silent mutation of self.geometry will produce a different
        hash and this method will return False.
        """
        recomputed = compute_geometry_hash(self.geometry)
        return recomputed == self.geometry_hash

    def assert_geometry_integrity(self) -> None:
        """Raise ValueError if geometry hash does not match — hard guard."""
        if not self.verify_geometry_integrity():
            raise ValueError(
                f"AOI {self.aoi_id}: geometry integrity check FAILED. "
                f"Stored hash {self.geometry_hash!r} does not match recomputed hash. "
                f"Geometry has been silently mutated."
            )


def new_aoi(
    geometry_type: GeometryType,
    geometry: dict,
    centroid: dict,
    bbox: dict,
    area_km2: float,
    created_by: str,
    source_type: SourceType,
    validation_status: ValidationStatus,
    environment: EnvironmentClassification,
    validation_errors: tuple[str, ...] = (),
    source_file_hash: Optional[str] = None,
    source_aoi_id: Optional[str] = None,
    aoi_version: int = 1,
) -> ScanAOI:
    """
    Factory: creates a new ScanAOI with cryptographic hash computed at creation.
    Returns an immutable (frozen) dataclass instance.
    """
    import uuid
    aoi_id             = str(uuid.uuid4())
    geometry_hash      = compute_geometry_hash(geometry)
    canonical_snapshot = json.dumps(
        json.loads(_canonical_geometry_bytes(geometry).decode("utf-8")),
        sort_keys=True, indent=2
    )
    return ScanAOI(
        aoi_id                    = aoi_id,
        geometry_type             = geometry_type,
        geometry                  = geometry,
        geometry_hash             = geometry_hash,
        canonical_geometry_snapshot = canonical_snapshot,
        aoi_version               = aoi_version,
        source_aoi_id             = source_aoi_id,
        centroid                  = centroid,
        bbox                      = bbox,
        area_km2                  = area_km2,
        created_by                = created_by,
        created_at                = datetime.utcnow().isoformat(),
        source_type               = source_type,
        source_file_hash          = source_file_hash,
        map_projection            = "EPSG:4326",
        validation_status         = validation_status,
        environment               = environment,
        validation_errors         = validation_errors,
    )