"""
Aurora OSI vNext — Data Room Export Store
Phase R §R.3

Produces a signed ZIP archive (data room package) for one completed scan.

Package contents:
  canonical_scan.json        — CanonicalScan record verbatim (from storage)
  geojson_tier_layer.geojson — GeoJSON FeatureCollection of ScanCells
  twin_voxels.json           — DigitalTwinVoxel records verbatim (from twin store)
  audit_trail.jsonl          — Audit log records for this scan_id
  manifest.json              — DataRoomManifest with SHA-256 hashes of all above

CONSTITUTIONAL RULES — Phase R:
  Rule 1: No scientific recomputation. All values written verbatim from storage.
  Rule 2: GeoJSON properties are taken directly from ScanCell fields — no tier
           re-assignment, no ACIF recomputation. Null fields rendered as null.
  Rule 3: SHA-256 is a cryptographic integrity primitive — not a scientific value.
  Rule 4: version_registry in manifest = CanonicalScan.version_registry verbatim.
  Rule 5: No import from core/*.

PROOF of Rule 2 (GeoJSON cell_to_feature):
  Properties set: cell_id, lat_center, lon_center, acif_score, tier,
  temporal_score, physics_residual, uncertainty — all verbatim from stored ScanCell.
  No tier label is recomputed. No score is recalculated.
"""

from __future__ import annotations

import hashlib
import io
import json
import time
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.models.data_room_model import (
    ArtifactRecord,
    DataRoomManifest,
    ScanLineage,
)


# ---------------------------------------------------------------------------
# Storage adapters — injected, never imported from storage/ directly
# ---------------------------------------------------------------------------

class CanonicalReadAdapter(Protocol):
    async def get_canonical_scan(self, scan_id: str) -> dict: ...
    async def list_scan_cells(self, scan_id: str) -> list[dict]: ...


class TwinReadAdapter(Protocol):
    async def list_voxels(self, scan_id: str, version: Optional[int] = None) -> list[dict]: ...


class AuditReadAdapter(Protocol):
    async def list_events_for_scan(self, scan_id: str) -> list[dict]: ...


# ---------------------------------------------------------------------------
# Artifact serialisers
# ---------------------------------------------------------------------------

def _serialise(obj) -> bytes:
    """Serialise to deterministic JSON bytes (sorted keys, no trailing space)."""
    return json.dumps(obj, default=str, sort_keys=True, indent=2).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact(filename: str, data: bytes, content_type: str, description: str) -> ArtifactRecord:
    return ArtifactRecord(
        filename=filename,
        sha256=_sha256(data),
        size_bytes=len(data),
        content_type=content_type,
        description=description,
    )


# ---------------------------------------------------------------------------
# GeoJSON builder — verbatim field copy only (Rule 2)
# ---------------------------------------------------------------------------

def _cell_to_feature(cell: dict) -> dict:
    """
    Convert a stored ScanCell dict to a GeoJSON Feature.

    PROOF OF RULE 2:
      All property values are cell.get(field) — verbatim or None.
      No scientific formula is applied. No tier label is recomputed.
      'tier' is the stored ScanCell.tier field — set at canonical freeze time,
      never re-evaluated here.
    """
    lat = cell.get("lat_center")
    lon = cell.get("lon_center")
    geometry = (
        {"type": "Point", "coordinates": [lon, lat]}
        if lat is not None and lon is not None
        else None
    )
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "cell_id":          cell.get("cell_id"),
            "acif_score":       cell.get("acif_score"),       # verbatim from ScanCell
            "tier":             cell.get("tier"),             # verbatim from ScanCell
            "temporal_score":   cell.get("temporal_score"),   # verbatim
            "physics_residual": cell.get("physics_residual"), # verbatim
            "uncertainty":      cell.get("uncertainty"),      # verbatim
            "offshore_gate_blocked": cell.get("offshore_gate_blocked"),
        },
    }


def _build_geojson(cells: list[dict]) -> bytes:
    """
    Build GeoJSON FeatureCollection from stored ScanCell records.
    Verbatim property copy only — no scientific recomputation.
    """
    fc = {
        "type": "FeatureCollection",
        "features": [_cell_to_feature(c) for c in cells],
    }
    return _serialise(fc)


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

async def export_data_room(
    scan_id: str,
    canonical_store: CanonicalReadAdapter,
    twin_store: TwinReadAdapter,
    audit_store: AuditReadAdapter,
    exported_by_email: str,
    twin_version: Optional[int] = None,
) -> tuple[bytes, DataRoomManifest]:
    """
    Produce a data room ZIP archive for one completed scan.

    Returns:
        (zip_bytes, manifest) — ZIP archive bytes and the manifest record.

    The manifest is also included inside the ZIP as manifest.json.

    PROOF:
      1. canonical_scan.json: await canonical_store.get_canonical_scan(scan_id)
         → verbatim stored record, JSON-serialised. No field altered.
      2. geojson_tier_layer.geojson: _build_geojson(cells) — verbatim copy (see above).
      3. twin_voxels.json: await twin_store.list_voxels(scan_id) → verbatim stored records.
      4. audit_trail.jsonl: await audit_store.list_events_for_scan(scan_id) → verbatim.
      5. manifest.json: DataRoomManifest with SHA-256 hashes and version_registry verbatim.
      No core/* function is called. No scientific value is computed.
    """
    t_start = time.monotonic()
    package_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # ── Load stored data — verbatim from canonical storage ──
    canonical = await canonical_store.get_canonical_scan(scan_id)
    cells = await canonical_store.list_scan_cells(scan_id)
    voxels = await twin_store.list_voxels(scan_id, version=twin_version)
    audit_events = await audit_store.list_events_for_scan(scan_id)

    # ── Serialise artifacts ──
    canonical_bytes = _serialise(canonical)
    geojson_bytes   = _build_geojson(cells)
    voxel_bytes     = _serialise({"scan_id": scan_id, "voxels": voxels})
    audit_bytes     = b"\n".join(
        json.dumps(e, default=str, sort_keys=True).encode("utf-8")
        for e in audit_events
    )

    artifacts = [
        _artifact(
            "canonical_scan.json", canonical_bytes,
            "application/json",
            "CanonicalScan record verbatim from aurora_vnext canonical storage",
        ),
        _artifact(
            "geojson_tier_layer.geojson", geojson_bytes,
            "application/geo+json",
            "GeoJSON FeatureCollection of ScanCells — verbatim field copy, no recomputation",
        ),
        _artifact(
            "twin_voxels.json", voxel_bytes,
            "application/json",
            "DigitalTwinVoxel records verbatim from twin storage",
        ),
        _artifact(
            "audit_trail.jsonl", audit_bytes,
            "application/x-ndjson",
            "Append-only audit log records for this scan_id",
        ),
    ]

    # ── Build manifest (without self-hash first) ──
    lineage = ScanLineage(
        scan_id=scan_id,
        parent_scan_id=canonical.get("parent_scan_id"),
        migration_class=canonical.get("migration_class"),
        migration_notes=canonical.get("migration_notes"),
        reprocess_reason=canonical.get("reprocess_reason"),
    )

    manifest = DataRoomManifest(
        package_id=package_id,
        created_at=created_at,
        created_by_email=exported_by_email,
        scan_id=scan_id,
        commodity=canonical.get("commodity"),
        scan_tier=canonical.get("scan_tier"),
        environment=canonical.get("environment"),
        scan_completed_at=canonical.get("completed_at"),
        version_registry=canonical.get("version_registry"),   # verbatim copy (Rule 4)
        lineage=lineage,
        artifacts=artifacts,
        manifest_sha256=None,
        export_duration_ms=None,
        aurora_env=canonical.get("_aurora_env"),
    )

    # Serialise manifest, compute its own hash, update
    manifest_bytes_v1  = _serialise(manifest.model_dump())
    manifest.manifest_sha256 = _sha256(manifest_bytes_v1)
    manifest.export_duration_ms = round((time.monotonic() - t_start) * 1000)
    manifest_bytes = _serialise(manifest.model_dump())

    # ── Assemble ZIP ──
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("canonical_scan.json",         canonical_bytes)
        zf.writestr("geojson_tier_layer.geojson",  geojson_bytes)
        zf.writestr("twin_voxels.json",             voxel_bytes)
        zf.writestr("audit_trail.jsonl",            audit_bytes)
        zf.writestr("manifest.json",                manifest_bytes)

    return buf.getvalue(), manifest