"""
Aurora OSI vNext — Legacy Migration Execution Pipeline
Phase R §R.2

Full Class A / B / C migration pipeline with DB writes via CanonicalScanStore.

Classification rules (from Phase Q backfill_legacy.py — unchanged):
  Class A: All REQUIRED_FOR_CLASS_A fields present → status=COMPLETED
  Class B: Identity fields present; result fields absent → status=COMPLETED, null results
  Class C: Identity fields missing → status=MIGRATION_STUB

═══════════════════════════════════════════════════════════════════════════
CONSTITUTIONAL RULES — Phase R:

  Rule 1 (No Recomputation):
    No call to compute_acif(), assign_tier(), evaluate_gates(), or any
    core/* function. All result fields are COPIED verbatim from the legacy
    record. Absent fields are stored as NULL — never estimated or imputed.

  Rule 2 (Canonical Fidelity):
    For Class A records: every canonical field written to DB must be
    bit-for-bit identical to the value in the legacy source record.
    This is verified by MigrationFidelityChecker.verify_class_a().

  Rule 3 (Class B null contract):
    Class B records may not have acif_score, tier_counts, system_status,
    or gate_results fields populated by this pipeline. If present in the
    legacy record they are copied; if absent they remain NULL.
    The pipeline NEVER synthesises these values.

  Rule 4 (Idempotency):
    Re-running migration on an already-written scan_id is a no-op.
    Status=skipped is returned; no DB write occurs.

  Rule 5 (Audit trail):
    Every successful write generates an audit event via AuditLogStore.
    Audit event includes migration_class, scan_id, and executed_by.

  Rule 6 (No core/* imports):
    This module must never import from core/scoring, core/tiering,
    core/gates, core/evidence, core/causal, core/physics, core/temporal,
    core/priors, or core/uncertainty.

LAYER: Layer-2 Pipeline. May import from models/, config/, storage/.
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.models.data_room_model import MigrationRecord, MigrationRunReport


# ---------------------------------------------------------------------------
# Classification constants — structural only, no scientific values
# ---------------------------------------------------------------------------

REQUIRED_FOR_CLASS_A = [
    "scan_id", "commodity", "scan_tier", "environment",
    "display_acif_score", "tier_counts", "system_status",
    "version_registry", "completed_at", "total_cells",
]

REQUIRED_FOR_CLASS_B = [
    "scan_id", "commodity", "scan_tier", "environment",
]

# Result fields — must NOT be synthesised under Class B/C
RESULT_FIELDS = frozenset({
    "display_acif_score", "max_acif_score", "weighted_acif_score",
    "tier_counts", "tier_thresholds_used", "system_status", "gate_results",
    "mean_evidence_score", "mean_causal_score", "mean_physics_score",
    "mean_temporal_score", "mean_province_prior", "mean_uncertainty",
    "causal_veto_cell_count", "physics_veto_cell_count",
    "province_veto_cell_count", "offshore_blocked_cell_count",
})


# ---------------------------------------------------------------------------
# Storage protocol — injected; never imported from storage/ here
# ---------------------------------------------------------------------------

class CanonicalWriteAdapter(Protocol):
    async def exists(self, scan_id: str) -> bool: ...
    async def write_canonical(self, record: dict) -> None: ...


class AuditWriteAdapter(Protocol):
    async def append_migration_event(
        self,
        scan_id: str,
        migration_class: str,
        actor_email: str,
        notes: str,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Classification (structural — no scientific logic)
# ---------------------------------------------------------------------------

def classify_record(record: dict) -> tuple[str, list[str], str]:
    """
    Classify one legacy record. Returns (class, missing_fields, notes).

    PROOF: no function from core/* is called. Only dict key presence checked.
    """
    missing_a = [f for f in REQUIRED_FOR_CLASS_A if record.get(f) is None]
    missing_b = [f for f in REQUIRED_FOR_CLASS_B if record.get(f) is None]

    if not missing_a:
        return (
            "A",
            [],
            "All canonical fields present. Verbatim copy. No recomputation.",
        )
    if not missing_b:
        result_nulled = [f for f in missing_a if f in RESULT_FIELDS]
        return (
            "B",
            missing_a,
            (
                f"Identity fields present; result fields absent: {result_nulled}. "
                f"Null stored — NOT recomputed or estimated. "
                f"Non-result missing fields: {[f for f in missing_a if f not in RESULT_FIELDS]}."
            ),
        )
    return (
        "C",
        missing_a + missing_b,
        f"Minimum identity fields missing: {missing_b}. Written as MIGRATION_STUB. Human review required.",
    )


# ---------------------------------------------------------------------------
# Canonical record builder — verbatim copy only
# ---------------------------------------------------------------------------

def build_canonical_dict(
    record: dict,
    migration_class: str,
    missing_fields: list[str],
    migration_notes: str,
) -> dict:
    """
    Map legacy dict to canonical schema dict.

    PROOF OF NO RECOMPUTATION (Rule 1 + Rule 3):
      Every result field is record.get(field) — verbatim or None.
      No arithmetic, no core/* call, no imputation occurs.
      Class B missing result fields become None in the canonical record.
    """
    status = (
        "MIGRATION_STUB" if migration_class == "C"
        else "COMPLETED"
    )

    def v(key):
        """Verbatim field copy — None if absent."""
        return record.get(key)

    return {
        # Identity
        "scan_id":                     v("scan_id") or str(uuid.uuid4()),
        "status":                      status,
        "commodity":                   v("commodity"),
        "scan_tier":                   v("scan_tier"),
        "environment":                 v("environment"),
        "aoi_geojson":                 v("aoi_geojson") or {},
        "grid_resolution_degrees":     v("grid_resolution_degrees"),
        "total_cells":                 v("total_cells"),
        # Result fields — verbatim copy or None (NEVER recomputed)
        "display_acif_score":          v("display_acif_score"),
        "max_acif_score":              v("max_acif_score"),
        "weighted_acif_score":         v("weighted_acif_score"),
        "tier_counts":                 v("tier_counts"),
        "tier_thresholds_used":        v("tier_thresholds_used"),
        "system_status":               v("system_status"),
        "gate_results":                v("gate_results"),
        "mean_evidence_score":         v("mean_evidence_score"),
        "mean_causal_score":           v("mean_causal_score"),
        "mean_physics_score":          v("mean_physics_score"),
        "mean_temporal_score":         v("mean_temporal_score"),
        "mean_province_prior":         v("mean_province_prior"),
        "mean_uncertainty":            v("mean_uncertainty"),
        "causal_veto_cell_count":      v("causal_veto_cell_count"),
        "physics_veto_cell_count":     v("physics_veto_cell_count"),
        "province_veto_cell_count":    v("province_veto_cell_count"),
        "offshore_blocked_cell_count": v("offshore_blocked_cell_count"),
        # Version registry and normalisation — verbatim or None
        "version_registry":            v("version_registry"),
        "normalisation_params":        v("normalisation_params"),
        # Timestamps — from legacy record, not synthesised
        "submitted_at":                v("submitted_at"),
        "completed_at":                v("completed_at"),
        # Reprocess lineage
        "parent_scan_id":              v("parent_scan_id"),
        # Migration metadata
        "migration_class":             migration_class,
        "migration_notes":             migration_notes,
    }


# ---------------------------------------------------------------------------
# Fidelity checker — Class A only
# ---------------------------------------------------------------------------

class MigrationFidelityChecker:
    """
    Verifies that a Class A canonical record is bit-for-bit identical
    to its source legacy record for all REQUIRED_FOR_CLASS_A fields.

    PROOF: comparison uses equality (==) only — no re-evaluation of values.
    """

    @staticmethod
    def verify_class_a(legacy: dict, canonical: dict) -> dict:
        """
        Returns {"passed": bool, "failures": list[{field, legacy_val, canonical_val}]}.
        Called after build_canonical_dict() for Class A records.
        """
        failures = []
        for field in REQUIRED_FOR_CLASS_A:
            leg_val = legacy.get(field)
            can_val = canonical.get(field)
            # Serialise to JSON for deterministic comparison of nested dicts/lists
            if json.dumps(leg_val, default=str, sort_keys=True) != \
               json.dumps(can_val, default=str, sort_keys=True):
                failures.append({
                    "field":         field,
                    "legacy_value":  leg_val,
                    "canonical_value": can_val,
                })
        return {"passed": len(failures) == 0, "failures": failures}


# ---------------------------------------------------------------------------
# Migration executor
# ---------------------------------------------------------------------------

async def execute_migration(
    legacy_records: list[dict],
    canonical_store: CanonicalWriteAdapter,
    audit_store: AuditWriteAdapter,
    executed_by: str,
    dry_run: bool = True,
    run_id: Optional[str] = None,
) -> MigrationRunReport:
    """
    Execute Class A/B/C migration pipeline with DB writes.

    Args:
        legacy_records:   List of legacy scan dicts (from JSONL / batch loader).
        canonical_store:  Write adapter for canonical_scans table.
        audit_store:      Write adapter for audit_log table.
        executed_by:      Email of the admin executing the migration.
        dry_run:          If True, classify and validate only — no DB writes.
        run_id:           Optional run UUID for idempotency tracking.

    Returns:
        MigrationRunReport with per-record outcomes and proof_summary.
    """
    run_id = run_id or str(uuid.uuid4())
    run_at = datetime.now(timezone.utc).isoformat()
    counts = {"A": 0, "B": 0, "C": 0, "skipped": 0, "error": 0}
    records: list[MigrationRecord] = []
    fidelity_failures: list[dict] = []

    for idx, legacy in enumerate(legacy_records):
        scan_id = legacy.get("scan_id") or f"unknown_line_{idx}"

        try:
            # Rule 4: idempotency check
            if not dry_run and await canonical_store.exists(scan_id):
                counts["skipped"] += 1
                records.append(MigrationRecord(
                    scan_id=scan_id,
                    migration_class="—",
                    source_file_line=idx,
                    missing_fields=[],
                    db_status="skipped",
                    error_message=None,
                    canonical_status="already_exists",
                    executed_at=run_at,
                    dry_run=dry_run,
                ))
                continue

            # Classify (structural — no scientific logic)
            mclass, missing, notes = classify_record(legacy)
            canonical = build_canonical_dict(legacy, mclass, missing, notes)

            # Fidelity check for Class A (Rule 2)
            fidelity = None
            if mclass == "A":
                fidelity = MigrationFidelityChecker.verify_class_a(legacy, canonical)
                if not fidelity["passed"]:
                    fidelity_failures.append({
                        "scan_id": scan_id,
                        "failures": fidelity["failures"],
                    })

            db_status = "dry_run"
            if not dry_run:
                await canonical_store.write_canonical(canonical)
                # Rule 5: audit trail
                await audit_store.append_migration_event(
                    scan_id=scan_id,
                    migration_class=mclass,
                    actor_email=executed_by,
                    notes=notes,
                )
                db_status = "written"

            counts[mclass] += 1
            records.append(MigrationRecord(
                scan_id=scan_id,
                migration_class=mclass,
                source_file_line=idx,
                missing_fields=missing,
                db_status=db_status,
                error_message=None,
                canonical_status=canonical["status"],
                executed_at=run_at,
                dry_run=dry_run,
            ))

        except Exception as e:
            counts["error"] += 1
            records.append(MigrationRecord(
                scan_id=scan_id,
                migration_class="error",
                source_file_line=idx,
                missing_fields=[],
                db_status="error",
                error_message=str(e),
                canonical_status="error",
                executed_at=run_at,
                dry_run=dry_run,
            ))

    proof_summary = {
        "scientific_functions_called": 0,
        "recomputed_fields":           [],
        "fidelity_class_a_failures":   fidelity_failures,
        "fidelity_passed":             len(fidelity_failures) == 0,
        "null_contract_class_b":       "All absent result fields stored as NULL — not estimated.",
        "idempotency":                 f"{counts['skipped']} records skipped (already migrated).",
        "audit_events_written":        counts["A"] + counts["B"] + counts["C"] if not dry_run else 0,
    }

    return MigrationRunReport(
        run_id=run_id,
        run_at=run_at,
        dry_run=dry_run,
        input_file="(in-memory batch)",
        counts=counts,
        records=records,
        proof_summary=proof_summary,
    )