"""
Aurora OSI vNext — Data Room Packager
Phase AH §AH.2

Assembles a DataRoomPackage from canonical stored artifacts.

CONSTITUTIONAL RULES:
  Rule 1: All artifact content is read verbatim from storage.
          No recomputation, rescoring, or transformation.
  Rule 2: SHA-256 is computed from bytes read — not from formulas.
  Rule 3: Watermarking adds recipient metadata only; it does not alter
          canonical data fields (acif_score, tier, veto, etc.).
  Rule 4: No import from core/*.
  Rule 5: package_hash is computed from sorted artifact hashes — reproducible.

PROOF OF ZERO SCIENTIFIC RECOMPUTATION:
  _read_canonical_scan_bytes()  → JSON serialise stored scan dict (verbatim)
  _read_geojson_bytes()         → fetch stored GeoJSON from storage (verbatim)
  _read_kml_bytes()             → fetch stored KML export bytes (verbatim)
  _read_twin_dataset_bytes()    → fetch stored voxel records (verbatim CSV)
  _read_report_bytes()          → fetch stored GeologicalReport (verbatim)
  _build_audit_trail_bytes()    → assemble audit fields from stored records
  None of these call core.scoring, core.tiering, core.gates, or core.priors.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.data_room_model import (
    DataRoomPackage, DataRoomArtifact, ArtifactType,
    WatermarkMetadata, DeliveryLink, DeliveryLinkStatus, DataRoomAccessLog,
    new_package_id, new_link_id, new_log_id, generate_delivery_token,
)
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Artifact byte builders — all verbatim reads
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_scan_to_bytes(scan: dict) -> bytes:
    """
    Serialise a canonical scan dict to canonical JSON bytes.
    Uses sorted keys for determinism. No formula applied.
    """
    return json.dumps(scan, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _geojson_to_bytes(geojson: dict) -> bytes:
    """Serialise a GeoJSON FeatureCollection verbatim."""
    return json.dumps(geojson, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _build_audit_trail(
    scan:              dict,
    calibration_trace: Optional[dict],
    report_audit:      Optional[dict],
    package_id:        str,
    recipient_id:      str,
) -> bytes:
    """
    Assemble audit trail bundle from stored audit fields.
    All values are verbatim from storage — no computation.
    """
    bundle = {
        "package_id":              package_id,
        "recipient_id":            recipient_id,
        "generated_at":            datetime.now(timezone.utc).isoformat(),
        "scan_id":                 scan.get("scan_id"),
        "pipeline_version":        scan.get("pipeline_version"),
        "scan_input_hash":         scan.get("scan_input_hash"),
        "scan_output_hash":        scan.get("scan_output_hash"),
        "version_registry_snapshot": scan.get("version_registry_snapshot", {}),
        "calibration_version_id":  (calibration_trace or {}).get("calibration_version_id"),
        "calibration_applied_at":  (calibration_trace or {}).get("applied_at"),
        "report_audit":            report_audit or {},
        "no_recomputation_statement": (
            "All values in this data room package are verbatim projections of "
            "canonical stored outputs. No scoring, tiering, gate evaluation, "
            "or calibration was performed during package assembly."
        ),
    }
    return json.dumps(bundle, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _apply_watermark_to_json(data: bytes, watermark: WatermarkMetadata) -> bytes:
    """
    Apply watermark by wrapping JSON in a {_watermark: ..., data: ...} envelope.
    Canonical data fields are untouched — only the wrapper is added.
    """
    inner = json.loads(data.decode("utf-8"))
    wrapped = {
        "_watermark": {
            "recipient_id":   watermark.recipient_id,
            "recipient_name": watermark.recipient_name,
            "applied_at":     watermark.applied_at,
            "watermark_id":   watermark.watermark_id,
        },
        "data": inner,
    }
    return json.dumps(wrapped, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# Package builder
# ---------------------------------------------------------------------------

def build_data_room_package(
    scan:              dict,
    geojson_layers:    list[dict],          # list of GeoJSON FeatureCollections
    kml_bytes:         Optional[bytes],
    twin_csv_bytes:    Optional[bytes],     # pre-exported digital twin CSV from storage
    report_dict:       Optional[dict],      # GeologicalReport serialised dict from storage
    calibration_trace: Optional[dict],
    recipient_id:      str,
    pipeline_version:  str,
    report_engine_version: str,
    calibration_version_id: str,
    cost_model_version: str,
    watermark:         Optional[WatermarkMetadata] = None,
) -> DataRoomPackage:
    """
    Assemble a DataRoomPackage from verbatim canonical artifacts.

    PROOF: Every _*_to_bytes() call reads stored data only.
           No core.scoring, core.tiering, core.gates calls are made.
           Verified by test_no_core_imports_in_packager().
    """
    now    = datetime.now(timezone.utc).isoformat()
    pkg_id = new_package_id()
    artifacts: list[DataRoomArtifact] = []

    def _make_artifact(
        a_type:    ArtifactType,
        filename:  str,
        src_ref:   str,
        data:      bytes,
        extra:     dict = None,
    ) -> DataRoomArtifact:
        h    = _sha256(data)
        size = len(data)
        wm_id = watermark.watermark_id if watermark else None
        return DataRoomArtifact(
            artifact_id        = f"{pkg_id}_{a_type.value}",
            artifact_type      = a_type,
            filename           = filename,
            content_source_ref = src_ref,
            sha256_hash        = h,
            size_bytes         = size,
            created_at         = now,
            is_verbatim        = True,
            watermark_id       = wm_id,
            cost_model_version = (extra or {}).get("cost_model_version"),
        )

    # 1. Canonical scan JSON
    scan_bytes = _canonical_scan_to_bytes(scan)
    if watermark:
        scan_bytes = _apply_watermark_to_json(scan_bytes, watermark)
    artifacts.append(_make_artifact(
        ArtifactType.CANONICAL_SCAN_JSON,
        f"scan_{scan['scan_id']}.json",
        f"canonical_scans/{scan['scan_id']}",
        scan_bytes,
    ))

    # 2. GeoJSON layers
    for i, gj in enumerate(geojson_layers):
        gj_bytes = _geojson_to_bytes(gj)
        if watermark:
            gj_bytes = _apply_watermark_to_json(gj_bytes, watermark)
        artifacts.append(_make_artifact(
            ArtifactType.GEOJSON_LAYER,
            f"layer_{i:02d}_{scan['scan_id']}.geojson",
            f"geojson_exports/{scan['scan_id']}/layer_{i}",
            gj_bytes,
        ))

    # 3. KML export
    if kml_bytes:
        artifacts.append(_make_artifact(
            ArtifactType.KML_EXPORT,
            f"export_{scan['scan_id']}.kml",
            f"kml_exports/{scan['scan_id']}",
            kml_bytes,
        ))

    # 4. Digital twin dataset
    if twin_csv_bytes:
        artifacts.append(_make_artifact(
            ArtifactType.DIGITAL_TWIN_DATASET,
            f"twin_{scan['scan_id']}.csv",
            f"twin_exports/{scan['scan_id']}",
            twin_csv_bytes,
        ))

    # 5. Geological report
    if report_dict:
        report_bytes = json.dumps(report_dict, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")
        if watermark:
            report_bytes = _apply_watermark_to_json(report_bytes, watermark)
        artifacts.append(_make_artifact(
            ArtifactType.GEOLOGICAL_REPORT,
            f"report_{scan['scan_id']}.json",
            f"reports/{report_dict.get('report_id', 'unknown')}",
            report_bytes,
        ))

    # 6. Audit trail bundle
    report_audit = report_dict.get("audit") if report_dict else None
    audit_bytes  = _build_audit_trail(scan, calibration_trace, report_audit,
                                      pkg_id, recipient_id)
    artifacts.append(_make_artifact(
        ArtifactType.AUDIT_TRAIL_BUNDLE,
        f"audit_{pkg_id}.json",
        f"audit/{pkg_id}",
        audit_bytes,
    ))

    # Compute package integrity hash
    sorted_hashes = sorted(a.sha256_hash for a in artifacts)
    package_hash  = hashlib.sha256("".join(sorted_hashes).encode()).hexdigest()

    logger.info("data_room_package_built", extra={
        "package_id": pkg_id, "scan_id": scan["scan_id"],
        "recipient_id": recipient_id, "artifacts": len(artifacts),
        "package_hash": package_hash[:16],
    })

    return DataRoomPackage(
        package_id             = pkg_id,
        scan_id                = scan["scan_id"],
        recipient_id           = recipient_id,
        created_at             = now,
        artifacts              = tuple(artifacts),
        package_hash           = package_hash,
        pipeline_version       = pipeline_version,
        report_engine_version  = report_engine_version,
        calibration_version_id = calibration_version_id,
        cost_model_version     = cost_model_version,
    )


# ---------------------------------------------------------------------------
# Delivery link management
# ---------------------------------------------------------------------------

def create_delivery_link(
    package_id:    str,
    recipient_id:  str,
    expires_at:    str,
    max_downloads: Optional[int] = None,
    ip_whitelist:  list[str] = None,
) -> DeliveryLink:
    """Create a time-limited signed delivery link for a package."""
    return DeliveryLink(
        link_id        = new_link_id(),
        package_id     = package_id,
        recipient_id   = recipient_id,
        token          = generate_delivery_token(),
        created_at     = datetime.now(timezone.utc).isoformat(),
        expires_at     = expires_at,
        max_downloads  = max_downloads,
        downloads_used = 0,
        status         = DeliveryLinkStatus.ACTIVE,
        ip_whitelist   = tuple(ip_whitelist or []),
    )


def check_link_access(
    link:       DeliveryLink,
    ip_address: str,
    now_utc:    Optional[str] = None,
) -> str:
    """
    Check if a delivery link grants access.
    Returns: "allowed" | "expired" | "revoked" | "ip_blocked" | "limit_reached"
    """
    from datetime import datetime, timezone
    now_str = now_utc or datetime.now(timezone.utc).isoformat()

    if link.status == DeliveryLinkStatus.REVOKED:
        return "revoked"
    if link.status == DeliveryLinkStatus.CONSUMED:
        return "limit_reached"
    if now_str >= link.expires_at:
        return "expired"
    if link.ip_whitelist and ip_address not in link.ip_whitelist:
        return "ip_blocked"
    if link.max_downloads is not None and link.downloads_used >= link.max_downloads:
        return "limit_reached"
    return "allowed"


def log_access(
    link:          DeliveryLink,
    ip_address:    str,
    user_agent:    str,
    outcome:       str,
    artifact_type: Optional[ArtifactType] = None,
    bytes_served:  int = 0,
) -> DataRoomAccessLog:
    """Create an access log entry. Caller is responsible for persisting it."""
    return DataRoomAccessLog(
        log_id        = new_log_id(),
        link_id       = link.link_id,
        package_id    = link.package_id,
        recipient_id  = link.recipient_id,
        accessed_at   = datetime.now(timezone.utc).isoformat(),
        ip_address    = ip_address,
        user_agent    = user_agent,
        artifact_type = artifact_type,
        outcome       = outcome,
        bytes_served  = bytes_served,
    )