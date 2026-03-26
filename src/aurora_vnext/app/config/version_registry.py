"""
Aurora OSI vNext — Version Registry (FROZEN)
Phase AE §AE.1

SYSTEM FREEZE — PHASE AE
All version constants below are LOCKED. No functional changes to the modules
they describe are permitted after Phase AE certification.

FREEZE MANIFEST:
  score_version:       ACIF scoring formula (core/scoring.py)
  tier_version:        Tier assignment logic (core/tiering.py)
  gate_version:        Hard/soft gate evaluation (core/gates.py)
  calibration_version: Calibration mathematics (services/calibration_math.py)
  schema_version:      Canonical scan + cell schema
  pipeline_version:    Scan pipeline orchestration
  twin_version:        Digital twin construction logic
  report_version:      Report engine + prompt templates
  export_version:      KML/KMZ/GeoJSON export logic
  portfolio_version:   Portfolio aggregation + ranking

IMMUTABILITY RULE:
  These strings are written into every CanonicalScan record at creation time
  via VersionRegistrySnapshot. If any frozen module is patched, its version
  string MUST be bumped and Phase AE must be re-certified.

DETERMINISM RULE:
  All frozen modules are deterministic under IEEE 754 double precision.
  No random seeds, no UUID generation, no timestamp injection inside scoring.
  All aggregations are order-independent (commutative formulas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── Frozen version strings ────────────────────────────────────────────────────
# Phase AE lock date: 2026-03-26

SCORE_VERSION       = "acif-1.0.0"
TIER_VERSION        = "tier-1.0.0"
GATE_VERSION        = "gate-1.0.0"
CALIBRATION_VERSION = "cal-math-1.0.0"
SCHEMA_VERSION      = "schema-1.0.0"
PIPELINE_VERSION    = "pipeline-1.0.0"
TWIN_VERSION        = "twin-1.0.0"
REPORT_VERSION      = "report-1.0.0"
EXPORT_VERSION      = "export-1.0.0"
PORTFOLIO_VERSION   = "portfolio-1.0.0"

# Composite hash — SHA-256 of all version strings concatenated in sort order.
# Recomputed whenever any version string changes.
REGISTRY_HASH = "ae-freeze-2026-03-26-v1"


@dataclass(frozen=True)
class VersionRegistrySnapshot:
    """
    Immutable snapshot of all version strings at scan creation time.
    Written into every CanonicalScan record — never updated retroactively.
    Used by replay_scan() to verify identical logic versions.

    PROOF OF PROPAGATION:
      CanonicalScan.version_snapshot → frozen at scan creation
      DigitalTwin.twin_version       → TWIN_VERSION at build time
      GeologicalReport.audit_trail   → REPORT_VERSION + prompt_version
      MapExport.export_version       → EXPORT_VERSION at export time
      PortfolioEntry.score           → weight_config_version (separate versioning)
    """
    score_version:       str
    tier_version:        str
    gate_version:        str
    calibration_version: str
    schema_version:      str
    pipeline_version:    str
    twin_version:        str
    report_version:      str
    export_version:      str
    portfolio_version:   str
    registry_hash:       str
    locked_at:           str    # ISO 8601 UTC — when this snapshot was created

    @classmethod
    def current(cls) -> "VersionRegistrySnapshot":
        """Return a snapshot reflecting the current (frozen) version constants."""
        from datetime import datetime
        return cls(
            score_version       = SCORE_VERSION,
            tier_version        = TIER_VERSION,
            gate_version        = GATE_VERSION,
            calibration_version = CALIBRATION_VERSION,
            schema_version      = SCHEMA_VERSION,
            pipeline_version    = PIPELINE_VERSION,
            twin_version        = TWIN_VERSION,
            report_version      = REPORT_VERSION,
            export_version      = EXPORT_VERSION,
            portfolio_version   = PORTFOLIO_VERSION,
            registry_hash       = REGISTRY_HASH,
            locked_at           = datetime.utcnow().isoformat(),
        )

    def to_dict(self) -> dict:
        return {
            "score_version":       self.score_version,
            "tier_version":        self.tier_version,
            "gate_version":        self.gate_version,
            "calibration_version": self.calibration_version,
            "schema_version":      self.schema_version,
            "pipeline_version":    self.pipeline_version,
            "twin_version":        self.twin_version,
            "report_version":      self.report_version,
            "export_version":      self.export_version,
            "portfolio_version":   self.portfolio_version,
            "registry_hash":       self.registry_hash,
            "locked_at":           self.locked_at,
        }

    def assert_compatible(self, other: "VersionRegistrySnapshot") -> None:
        """
        Assert that two snapshots are compatible for replay.
        All scientific versions must match exactly.
        Raises IncompatibleVersionError if any frozen version differs.
        """
        frozen = ["score_version", "tier_version", "gate_version",
                  "calibration_version", "schema_version", "pipeline_version"]
        mismatches = []
        for field in frozen:
            v1 = getattr(self, field)
            v2 = getattr(other, field)
            if v1 != v2:
                mismatches.append(f"{field}: {v1!r} ≠ {v2!r}")
        if mismatches:
            raise IncompatibleVersionError(
                "Version mismatch — replay would not produce identical output:\n"
                + "\n".join(f"  {m}" for m in mismatches)
            )


class IncompatibleVersionError(ValueError):
    """Raised when replay_scan encounters a version mismatch."""


def registry_version() -> str:
    """Return the registry hash (used in report audit trails)."""
    return REGISTRY_HASH


def assert_version_frozen() -> None:
    """
    Called by tests to verify no version string has been changed from
    the Phase AE freeze values.
    Raises AssertionError if any version has drifted.
    """
    assert SCORE_VERSION       == "acif-1.0.0",       f"score_version drifted: {SCORE_VERSION!r}"
    assert TIER_VERSION        == "tier-1.0.0",       f"tier_version drifted: {TIER_VERSION!r}"
    assert GATE_VERSION        == "gate-1.0.0",       f"gate_version drifted: {GATE_VERSION!r}"
    assert CALIBRATION_VERSION == "cal-math-1.0.0",   f"calibration_version drifted: {CALIBRATION_VERSION!r}"
    assert SCHEMA_VERSION      == "schema-1.0.0",     f"schema_version drifted: {SCHEMA_VERSION!r}"
    assert PIPELINE_VERSION    == "pipeline-1.0.0",   f"pipeline_version drifted: {PIPELINE_VERSION!r}"
    assert REGISTRY_HASH       == "ae-freeze-2026-03-26-v1", f"registry_hash drifted: {REGISTRY_HASH!r}"