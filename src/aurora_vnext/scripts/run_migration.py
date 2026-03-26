"""
Aurora OSI vNext — Phase R Migration Execution CLI
Phase R §R.4

CLI runner for the full Class A/B/C migration pipeline.

Usage:
    # Dry run (classify + validate — no DB writes):
    python scripts/run_migration.py --input legacy_scans.jsonl --dry-run

    # Live execute (writes to DB):
    python scripts/run_migration.py --input legacy_scans.jsonl --execute \
        --executor-email admin@aurora.internal

    # Export a data room package for a single scan:
    python scripts/run_migration.py --export-data-room --scan-id <scan_id> \
        --executor-email admin@aurora.internal --output ./data_room_exports/

Outputs:
    migration_report_{timestamp}.json  — full MigrationRunReport
    data_room_{scan_id}_{ts}.zip       — data room archive (export mode)
    manifest_{scan_id}_{ts}.json       — DataRoomManifest (export mode)

CONSTITUTIONAL RULE: This script imports migration_pipeline and data_room only.
It does NOT import from core/*. No scientific logic is called here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline.migration_pipeline import execute_migration
from app.models.data_room_model import MigrationRunReport


# ---------------------------------------------------------------------------
# Stub adapters (replaced by real storage in production wiring)
# ---------------------------------------------------------------------------

class _StubCanonicalWrite:
    """Stub write adapter for dry-run mode."""
    _written: set = set()

    async def exists(self, scan_id: str) -> bool:
        return scan_id in self._written

    async def write_canonical(self, record: dict) -> None:
        self._written.add(record["scan_id"])
        # In production: calls CanonicalScanStore.write_canonical(record)


class _StubAuditWrite:
    """Stub audit adapter for dry-run mode."""
    async def append_migration_event(self, scan_id, migration_class, actor_email, notes):
        pass   # In production: calls AuditLogStore.append_audit_event(...)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path) as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {i+1}: JSON parse error — {e}", file=sys.stderr)
    return records


def _write_report(report: MigrationRunReport, output_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = output_dir / f"migration_report_{ts}.json"
    with open(out, "w") as fh:
        json.dump(report.model_dump(), fh, indent=2, default=str)
    return out


# ---------------------------------------------------------------------------
# Migration command
# ---------------------------------------------------------------------------

async def cmd_migrate(args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1

    legacy_records = _load_jsonl(input_path)
    print(f"Loaded {len(legacy_records)} legacy records from {input_path}")

    dry_run = not args.execute
    canonical_store = _StubCanonicalWrite()
    audit_store = _StubAuditWrite()

    report = await execute_migration(
        legacy_records=legacy_records,
        canonical_store=canonical_store,
        audit_store=audit_store,
        executed_by=args.executor_email or "cli@aurora.internal",
        dry_run=dry_run,
    )

    output_dir = Path(args.output or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = _write_report(report, output_dir)

    print(f"\nMigration {'DRY RUN' if dry_run else 'LIVE'} complete")
    print(f"  Class A (full):  {report.counts['A']}")
    print(f"  Class B (partial): {report.counts['B']}")
    print(f"  Class C (stub):  {report.counts['C']}")
    print(f"  Skipped:         {report.counts['skipped']}")
    print(f"  Errors:          {report.counts['error']}")
    print(f"  Fidelity passed: {report.proof_summary['fidelity_passed']}")
    if not report.proof_summary["fidelity_passed"]:
        print(f"  [WARN] Fidelity failures: {report.proof_summary['fidelity_class_a_failures']}")
    print(f"\nReport written: {report_path}")
    return 0 if report.proof_summary["fidelity_passed"] else 2


# ---------------------------------------------------------------------------
# Data room export command
# ---------------------------------------------------------------------------

async def cmd_export_data_room(args) -> int:
    from app.storage.data_room import export_data_room

    scan_id = args.scan_id
    if not scan_id:
        print("[ERROR] --scan-id required for --export-data-room", file=sys.stderr)
        return 1

    # Stub adapters — replace with real storage in production wiring
    class _StubCanonicalRead:
        async def get_canonical_scan(self, sid):
            raise NotImplementedError("Wire real CanonicalScanStore in production")
        async def list_scan_cells(self, sid):
            return []

    class _StubTwinRead:
        async def list_voxels(self, sid, version=None):
            return []

    class _StubAuditRead:
        async def list_events_for_scan(self, sid):
            return []

    zip_bytes, manifest = await export_data_room(
        scan_id=scan_id,
        canonical_store=_StubCanonicalRead(),
        twin_store=_StubTwinRead(),
        audit_store=_StubAuditRead(),
        exported_by_email=args.executor_email or "cli@aurora.internal",
    )

    output_dir = Path(args.output or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    zip_path = output_dir / f"data_room_{scan_id}_{ts}.zip"
    manifest_path = output_dir / f"manifest_{scan_id}_{ts}.json"

    zip_path.write_bytes(zip_bytes)
    with open(manifest_path, "w") as fh:
        json.dump(manifest.model_dump(), fh, indent=2, default=str)

    print(f"Data room package: {zip_path}  ({len(zip_bytes):,} bytes)")
    print(f"Manifest:          {manifest_path}")
    print(f"Package SHA-256:   {manifest.manifest_sha256}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Aurora Phase R migration + data room CLI")
    parser.add_argument("--input",            help="JSONL legacy records input file")
    parser.add_argument("--execute",          action="store_true", help="Live DB write (default: dry run)")
    parser.add_argument("--export-data-room", action="store_true", help="Export data room package")
    parser.add_argument("--scan-id",          help="scan_id for data room export")
    parser.add_argument("--executor-email",   default="cli@aurora.internal")
    parser.add_argument("--output",           default=".", help="Output directory")
    args = parser.parse_args()

    if args.export_data_room:
        sys.exit(asyncio.run(cmd_export_data_room(args)))
    elif args.input:
        sys.exit(asyncio.run(cmd_migrate(args)))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()