"""
Aurora OSI vNext — Data Room Model
Phase AH §AH.1

Defines all data-room artifacts, package structure, delivery links,
access log entries, and watermark metadata.

CONSTITUTIONAL RULES:
  Rule 1: All artifacts are verbatim canonical projections.
          No recomputation, rescoring, or transformation occurs during packaging.
  Rule 2: Every artifact carries a sha256_hash computed at package-time.
          Hash verification proves the artifact has not been modified post-package.
  Rule 3: DeliveryLink is time-limited — expires_at is mandatory.
  Rule 4: Every download is logged in DataRoomAccessLog (append-only).
  Rule 5: No import from core/*.
  Rule 6: cost_model_version is mandatory on any artifact derived from cost estimates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ArtifactType(str, Enum):
    CANONICAL_SCAN_JSON   = "canonical_scan_json"
    GEOJSON_LAYER         = "geojson_layer"
    KML_EXPORT            = "kml_export"
    KMZ_EXPORT            = "kmz_export"
    DIGITAL_TWIN_DATASET  = "digital_twin_dataset"
    GEOLOGICAL_REPORT     = "geological_report"
    AUDIT_TRAIL_BUNDLE    = "audit_trail_bundle"
    COST_ESTIMATE         = "cost_estimate"
    VALIDATION_SUMMARY    = "validation_summary"


class DeliveryLinkStatus(str, Enum):
    ACTIVE   = "active"
    EXPIRED  = "expired"
    REVOKED  = "revoked"
    CONSUMED = "consumed"   # single-use links


@dataclass(frozen=True)
class DataRoomArtifact:
    """
    One artifact in a data-room package.

    PROOF OF NO RECOMPUTATION:
      content_source_ref is the canonical storage path or report_id.
      The artifact content is a verbatim read from that source.
      sha256_hash is computed from the bytes read — not from any formula.
    """
    artifact_id:         str
    artifact_type:       ArtifactType
    filename:            str
    content_source_ref:  str        # storage path / entity id of the canonical source
    sha256_hash:         str        # SHA-256 of the artifact bytes
    size_bytes:          int
    created_at:          str        # ISO 8601 UTC
    is_verbatim:         bool       # must be True for all artifacts
    watermark_id:        Optional[str] = None   # set if watermarking applied
    cost_model_version:  Optional[str] = None   # set on COST_ESTIMATE artifacts


@dataclass(frozen=True)
class DataRoomPackage:
    """
    A complete, immutable data-room package for one scan delivery.

    package_hash: SHA-256 of the concatenated artifact hashes (sorted by artifact_id).
                  Proves the entire package is unchanged.
    """
    package_id:           str
    scan_id:              str
    recipient_id:         str          # user or organisation ID
    created_at:           str
    artifacts:            tuple[DataRoomArtifact, ...]
    package_hash:         str          # hash of all artifact hashes concatenated (sorted)
    pipeline_version:     str          # from VersionRegistry
    report_engine_version: str
    calibration_version_id: str
    cost_model_version:   str          # from scan_cost_model.COST_MODEL_VERSION
    notes:                str = ""

    def artifact(self, artifact_type: ArtifactType) -> Optional[DataRoomArtifact]:
        for a in self.artifacts:
            if a.artifact_type == artifact_type:
                return a
        return None

    def verify_integrity(self) -> bool:
        """
        Recompute package_hash from artifact hashes and compare.
        Returns True if package is intact.
        """
        import hashlib
        sorted_hashes = sorted(a.sha256_hash for a in self.artifacts)
        computed = hashlib.sha256("".join(sorted_hashes).encode()).hexdigest()
        return computed == self.package_hash


@dataclass(frozen=True)
class WatermarkMetadata:
    """
    Watermark applied to a delivered artifact.
    Watermarking is non-destructive to the canonical data — it adds a visible
    recipient label to PDF/HTML reports and a metadata field to JSON/KML.
    """
    watermark_id:   str
    recipient_id:   str
    recipient_name: str
    applied_at:     str
    artifact_id:    str
    method:         str    # "metadata_field" | "pdf_header" | "json_wrapper"


@dataclass(frozen=True)
class DeliveryLink:
    """
    A time-limited signed URL token for secure package delivery.

    SECURITY:
      - expires_at is mandatory and enforced at access time.
      - token is a cryptographically random 256-bit value (hex-encoded).
      - max_downloads = None means unlimited within the expiry window.
      - status transitions: ACTIVE → EXPIRED | REVOKED | CONSUMED.
    """
    link_id:       str
    package_id:    str
    recipient_id:  str
    token:         str        # 64-char hex (256-bit random)
    created_at:    str
    expires_at:    str        # ISO 8601 UTC — mandatory
    max_downloads: Optional[int]   # None = unlimited
    downloads_used: int
    status:        DeliveryLinkStatus
    ip_whitelist:  tuple[str, ...] = ()   # empty = any IP allowed


@dataclass(frozen=True)
class DataRoomAccessLog:
    """
    Append-only access log entry. Written on every download attempt.
    """
    log_id:        str
    link_id:       str
    package_id:    str
    recipient_id:  str
    accessed_at:   str        # ISO 8601 UTC
    ip_address:    str
    user_agent:    str
    artifact_type: Optional[ArtifactType]
    outcome:       str        # "allowed" | "expired" | "revoked" | "ip_blocked" | "limit_reached"
    bytes_served:  int        # 0 if access denied


def new_package_id() -> str:
    import uuid
    return f"drp-{uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid4()))}"


def new_link_id() -> str:
    import uuid
    return f"drl-{uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid4()))}"


def new_log_id() -> str:
    import uuid
    return f"dal-{uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid4()))}"


def generate_delivery_token() -> str:
    """Generate a 256-bit cryptographically secure token (64-char hex)."""
    import secrets
    return secrets.token_hex(32)