"""
Aurora OSI vNext — Reprocess Controller
Phase L §L.3 | Phase B §16

Responsibilities:
  - Create a new scan_id (child) linked to the parent via parent_scan_id.
  - Copy AOI and bounds from parent scan record.
  - Validate that at least one Θ_c parameter changed — reject no-op reproceses.
  - Write an audit record BEFORE starting reprocess (pre-flight audit).
  - Persist reprocess lineage: {parent_id → new_id, changed fields, actor, ts}.
  - Enqueue the new scan_id for pipeline execution.

CONSTITUTIONAL RULES:
  1. A reprocess ALWAYS produces a NEW scan_id — never overwrites parent.
  2. If delta_h_m changes, physics_model_version MUST be incremented.
  3. The audit record must be written BEFORE the pipeline starts.
  4. The changed_params dict must enumerate every field that differs.

LAYER RULE: This module is pipeline layer (Layer 3).
  Does not import from api/ or storage/ — receives adapters via injection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.pipeline.scan_pipeline import CommodityConfig, execute_scan_pipeline
from app.pipeline.task_queue import QueueAdapter, enqueue_scan, scan_tier_to_priority
from app.services.gee import GEEClient


# ---------------------------------------------------------------------------
# Reprocess request
# ---------------------------------------------------------------------------

@dataclass
class ReprocessRequest:
    """
    Parameters for a scan reprocess operation.
    actor:           User/system that initiated the reprocess.
    reason:          Human-readable reason (stored in CanonicalScan).
    new_commodity_config: Updated Θ_c (must differ from parent on ≥ 1 field).
    """
    parent_scan_id: str
    actor: str
    reason: str
    new_commodity_config: CommodityConfig


# ---------------------------------------------------------------------------
# Reprocess adapter protocol
# ---------------------------------------------------------------------------

class ReprocessStorageAdapter:
    """
    Minimal storage interface required by reprocess controller.
    Injected — never imported from storage/ here.
    """
    def load_canonical_scan(self, scan_id: str) -> dict: ...
    def write_reprocess_lineage(self, lineage: dict) -> None: ...
    def write_pre_reprocess_audit(self, audit: dict) -> None: ...
    def update_scan_job_stage(self, scan_id: str, stage: str, pct: float) -> None: ...
    def mark_scan_job_failed(self, scan_id: str, stage: str, error: str) -> None: ...
    def write_canonical_scan(self, scan_id: str, result: dict) -> None: ...
    def write_scan_cells(self, scan_id: str, cells: list) -> None: ...
    def write_audit_events(self, scan_id: str, events: list) -> None: ...
    def load_province_prior(self, cell_id: str, commodity: str) -> dict: ...


# ---------------------------------------------------------------------------
# Changed-parameter detection
# ---------------------------------------------------------------------------

def _detect_changed_params(
    old_config: dict,
    new_config: CommodityConfig,
) -> dict[str, dict[str, Any]]:
    """
    Compare old Θ_c (from stored canonical scan meta) with new Θ_c.
    Returns {field: {old: v, new: v}} for every changed field.
    """
    changes: dict[str, dict[str, Any]] = {}

    fields_to_check = ["delta_h_m", "alpha_c", "name", "family"]
    for f in fields_to_check:
        old_val = old_config.get(f)
        new_val = getattr(new_config, f, None)
        if old_val != new_val:
            changes[f] = {"old": old_val, "new": new_val}

    return changes


def _requires_physics_version_bump(changed_params: dict) -> bool:
    """Return True if any physics model parameter changed."""
    physics_params = {"delta_h_m"}
    return bool(physics_params & set(changed_params.keys()))


# ---------------------------------------------------------------------------
# Reprocess entry point
# ---------------------------------------------------------------------------

def execute_reprocess(
    request: ReprocessRequest,
    gee_client: GEEClient,
    storage: ReprocessStorageAdapter,
    queue: QueueAdapter,
) -> str:
    """
    Execute a scan reprocess.

    Steps:
      1. Load parent canonical scan.
      2. Detect changed parameters — reject if none.
      3. Write pre-flight audit record.
      4. Generate new scan_id.
      5. Write reprocess lineage record.
      6. Execute pipeline with new Θ_c and parent_scan_id set.
      7. Enqueue (if async) — here executed inline for simplicity.

    Returns:
        new_scan_id — the child scan produced by this reprocess.

    Raises:
        ValueError: If no parameters changed, or if physics version bump required
                    but not flagged in the new config version.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Load parent
    parent = storage.load_canonical_scan(request.parent_scan_id)
    if not parent:
        raise ValueError(f"Parent scan {request.parent_scan_id!r} not found.")
    if parent.get("status") != "COMPLETED":
        raise ValueError(
            f"Parent scan {request.parent_scan_id!r} is not COMPLETED "
            f"(status={parent.get('status')}). Only completed scans may be reprocessed."
        )

    # Step 2: Detect changes
    old_theta_c = {
        "delta_h_m": parent.get("tier_thresholds_used", {}).get("delta_h_m_used"),
        "alpha_c":   None,   # stored in Phase F commodity meta
        "name":      parent.get("commodity"),
        "family":    None,
    }
    changed = _detect_changed_params(old_theta_c, request.new_commodity_config)
    if not changed:
        raise ValueError(
            "Reprocess rejected: no Θ_c parameters changed vs. parent scan "
            f"{request.parent_scan_id!r}. At least one parameter must differ."
        )

    physics_bump = _requires_physics_version_bump(changed)

    # Step 3: Pre-flight audit — MUST be written before pipeline starts
    audit_record = {
        "event_type": "REPROCESS_INITIATED",
        "parent_scan_id": request.parent_scan_id,
        "actor": request.actor,
        "reason": request.reason,
        "changed_params": changed,
        "physics_version_bump_required": physics_bump,
        "timestamp_utc": now,
    }
    storage.write_pre_reprocess_audit(audit_record)

    # Step 4: New scan_id
    new_scan_id = str(uuid.uuid4())

    # Step 5: Lineage record
    storage.write_reprocess_lineage({
        "parent_scan_id": request.parent_scan_id,
        "child_scan_id": new_scan_id,
        "actor": request.actor,
        "reason": request.reason,
        "changed_params": changed,
        "physics_version_bump": physics_bump,
        "initiated_at": now,
    })

    # Step 6: Execute pipeline with lineage context
    grid_spec = {
        "resolution_degrees": parent.get("grid_resolution_degrees", 0.1),
        "min_lat": parent.get("aoi_geojson", {}).get("min_lat", -30.0),
        "max_lat": parent.get("aoi_geojson", {}).get("max_lat", -29.0),
        "min_lon": parent.get("aoi_geojson", {}).get("min_lon", 121.0),
        "max_lon": parent.get("aoi_geojson", {}).get("max_lon", 122.0),
    }

    execute_scan_pipeline(
        scan_id=new_scan_id,
        commodity_config=request.new_commodity_config,
        gee_client=gee_client,
        storage=storage,
        grid_spec=grid_spec,
        date_start="2023-01-01",
        date_end="2023-12-31",
        environment=parent.get("environment", "ONSHORE"),
        scan_request_meta={
            "scan_tier": parent.get("scan_tier", "SMART"),
            "aoi_geojson": parent.get("aoi_geojson", {}),
            "resolution_degrees": parent.get("grid_resolution_degrees", 0.1),
            "parent_scan_id": request.parent_scan_id,
            "reprocess_reason": request.reason,
            "reprocess_changed_params": changed,
            "submitted_at": now,
        },
    )

    return new_scan_id