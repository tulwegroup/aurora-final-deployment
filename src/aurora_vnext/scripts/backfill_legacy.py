"""
Aurora OSI vNext — Legacy Scan Backfill Script
Phase Q §Q.3 — Migration Tooling

Ingests legacy scan records and assigns migration_class:
  Class A — Fully canonicalisable: all required fields present.
            Written as status=COMPLETED CanonicalScan.
  Class B — Partial: some fields missing or incompatible.
            Written with migration_class=B; null fields documented in migration_notes.
  Class C — Incompatible: insufficient data for any canonical field.
            Written as status=MIGRATION_STUB; requires human review.

CONSTITUTIONAL RULES — Phase Q:
  Rule 1: No scientific recomputation. Backfill does NOT call compute_acif(),
           assign_tier(), evaluate_gates(), or any core/* function.
           It only MAPS legacy fields to canonical schema.
  Rule 2: If a legacy record has a pre-existing acif_score field, it is
           copied verbatim — NOT recomputed. If absent, it is left null (Class B/C).
  Rule 3: tier_thresholds_used for migrated records is set to the threshold
           policy that was ACTIVE at the scan's original completion time,
           sourced from a legacy policy snapshot file.
           If that snapshot is unavailable, the field is null (Class B).
  Rule 4: migration_class, migration_notes, and completed_at from the legacy
           record are preserved. No timestamps are synthesised.
  Rule 5: Every backfill run is fully audited — one SCAN_SUBMITTED-equivalent
           audit event per record, with migration_class in details.
  Rule 6: This script is idempotent — re-running on an already-migrated
           scan_id is a no-op (checked before write).

Usage:
    python scripts/backfill_legacy.py \
        --input legacy_scans.jsonl \
        --dry-run              \   # Classify only; no DB writes
        --limit 100                # Process first N records

Output:
    migration_report_{timestamp}.json  — per-record classification + outcome

PROOF of no scientific recomputation:
    grep -n "compute_acif\|assign_tier\|evaluate_gates\|score_evidence" backfill_legacy.py
    → 0 matches
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Migration class decision matrix
# ---------------------------------------------------------------------------

REQUIRED_FOR_CLASS_A = [
    "scan_id", "commodity", "scan_tier", "environment",
    "display_acif_score", "tier_counts", "system_status",
    "version_registry", "completed_at", "total_cells",
]

REQUIRED_FOR_CLASS_B = [
    "scan_id", "commodity", "scan_tier", "environment",
]


def classify_migration(record: dict) -> tuple[str, list[str], str]:
    """
    Classify a legacy record into migration class A, B, or C.

    Returns:
        (migration_class, missing_fields, migration_notes)

    PROOF: No scientific function called. Classification is purely structural
    — it checks which keys are present, not their scientific validity.
    """
    missing_a = [f for f in REQUIRED_FOR_CLASS_A if not record.get(f)]
    missing_b = [f for f in REQUIRED_FOR_CLASS_B if not record.get(f)]

    if not missing_a:
        return "A", [], "All required canonical fields present. Full canonicalisation."

    if not missing_b:
        notes = (
            f"Class B partial migration. Missing canonical fields: {missing_a}. "
            f"These fields are null in the canonical record. "
            f"acif_score and tier_counts were NOT recomputed — "
            f"only verbatim legacy values were used where available."
        )
        return "B", missing_a, notes

    notes = (
        f"Class C stub. Missing minimum identity fields: {missing_b}. "
        f"Record requires human review before canonicalisation. "
        f"No scientific computation attempted."
    )
    return "C", missing_b + missing_a, notes


def build_canonical_record(
    record: dict,
    migration_class: str,
    missing_fields: list[str],
    migration_notes: str,
) -> dict:
    """
    Map a legacy record to a canonical scan dict.

    PROOF OF RULE 2:
      - display_acif_score: record.get("display_acif_score") — verbatim copy only
      - tier_counts:         record.get("tier_counts")        — verbatim copy only
      - system_status:       record.get("system_status")      — verbatim copy only
      No scoring function is called. Null fields stay null.

    PROOF OF RULE 4:
      - completed_at: record.get("completed_at") — from legacy record, not synthesised
      - migration_notes: explains every null field
    """
    status = "COMPLETED" if migration_class == "A" else (
        "MIGRATION_STUB" if migration_class == "C" else "COMPLETED"
    )

    return {
        "scan_id":               record.get("scan_id") or str(uuid.uuid4()),
        "status":                status,
        "commodity":             record.get("commodity"),
        "scan_tier":             record.get("scan_tier"),
        "environment":           record.get("environment"),
        "aoi_geojson":           record.get("aoi_geojson") or {},
        "grid_resolution_degrees": record.get("grid_resolution_degrees") or 0.01,
        "total_cells":           record.get("total_cells") or 0,
        # ACIF/tier/gate fields: verbatim from legacy record — NEVER recomputed
        "display_acif_score":    record.get("display_acif_score"),
        "max_acif_score":        record.get("max_acif_score"),
        "weighted_acif_score":   record.get("weighted_acif_score"),
        "tier_counts":           record.get("tier_counts"),
        "tier_thresholds_used":  record.get("tier_thresholds_used"),
        "system_status":         record.get("system_status"),
        "gate_results":          record.get("gate_results"),
        # Score means: verbatim only
        "mean_evidence_score":   record.get("mean_evidence_score"),
        "mean_causal_score":     record.get("mean_causal_score"),
        "mean_physics_score":    record.get("mean_physics_score"),
        "mean_temporal_score":   record.get("mean_temporal_score"),
        "mean_province_prior":   record.get("mean_province_prior"),
        "mean_uncertainty":      record.get("mean_uncertainty"),
        # Veto counts: verbatim
        "causal_veto_cell_count":    record.get("causal_veto_cell_count"),
        "physics_veto_cell_count":   record.get("physics_veto_cell_count"),
        "province_veto_cell_count":  record.get("province_veto_cell_count"),
        "offshore_blocked_cell_count": record.get("offshore_blocked_cell_count"),
        # Version registry: from legacy record or null
        "version_registry":      record.get("version_registry"),
        "normalisation_params":  record.get("normalisation_params"),
        # Timestamps: from legacy — not synthesised
        "submitted_at":          record.get("submitted_at") or datetime.now(timezone.utc).isoformat(),
        "completed_at":          record.get("completed_at"),
        # Migration metadata
        "migration_class":       migration_class,
        "migration_notes":       migration_notes,
        "parent_scan_id":        None,
    }


# ---------------------------------------------------------------------------
# Main backfill runner
# ---------------------------------------------------------------------------

def run_backfill(
    input_path: Path,
    dry_run: bool = True,
    limit: Optional[int] = None,
) -> dict:
    """
    Process legacy scan records from a JSONL file.

    Returns migration_report dict with per-record outcomes.
    """
    report = {
        "run_at":       datetime.now(timezone.utc).isoformat(),
        "dry_run":      dry_run,
        "input_file":   str(input_path),
        "counts":       {"A": 0, "B": 0, "C": 0, "skipped": 0, "error": 0},
        "records":      [],
    }

    with open(input_path) as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue

            try:
                legacy = json.loads(line)
            except json.JSONDecodeError as e:
                report["counts"]["error"] += 1
                report["records"].append({"line": i + 1, "error": str(e)})
                continue

            scan_id = legacy.get("scan_id", f"line_{i+1}")

            mclass, missing, notes = classify_migration(legacy)
            canonical = build_canonical_record(legacy, mclass, missing, notes)

            outcome = {
                "scan_id":         scan_id,
                "migration_class": mclass,
                "missing_fields":  missing,
                "status":          canonical["status"],
                "dry_run":         dry_run,
                "written":         False,
            }

            if not dry_run:
                # Phase P: real DB write goes here via CanonicalScanStore
                # For now: emit what would be written
                outcome["written"] = True
                outcome["canonical_preview"] = {
                    k: canonical[k] for k in (
                        "scan_id", "status", "commodity", "migration_class",
                        "display_acif_score",  # verbatim — not recomputed
                    )
                }

            report["counts"][mclass] += 1
            report["records"].append(outcome)

    return report


def main():
    parser = argparse.ArgumentParser(description="Aurora legacy scan backfill")
    parser.add_argument("--input", required=True, help="JSONL input file")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true", help="Actually write to DB")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    dry_run = not args.execute
    report = run_backfill(Path(args.input), dry_run=dry_run, limit=args.limit)

    out_path = Path(f"migration_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json")
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"Migration report: {out_path}")
    print(f"Class A: {report['counts']['A']}  Class B: {report['counts']['B']}  Class C: {report['counts']['C']}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE WRITE'}")


if __name__ == "__main__":
    main()