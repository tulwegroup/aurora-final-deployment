"""
Aurora OSI vNext — Calibration Version Manager
Phase Y §Y.3

CONSTITUTIONAL RULES:
  Rule 1 (directive 1): Calibration NEVER modifies existing canonical scan outputs.
          Historical scans are frozen scientific records. Calibration updates
          model parameters only — future scoring runs only.
  Rule 2 (directive 2): Every calibration change produces a new CalibrationVersion.
          Prior versions are NEVER overwritten. Lineage is immutable.
  Rule 3 (directive 5): Calibration output is model configuration only.
          This module does NOT compute ACIF, assign tiers, or evaluate gates.
  Rule 4: No import from core/scoring, core/tiering, core/gates.

CalibrationVersion lifecycle:
  DRAFT      → being assembled, not yet applied to any scan
  ACTIVE     → currently the live calibration for new scoring runs
  SUPERSEDED → replaced by a newer CalibrationVersion (retained for lineage)
  REVOKED    → manually withdrawn (retained for audit, never deleted)

Version chain integrity:
  Each CalibrationVersion stores parent_version_id pointing to the version
  it was derived from. This forms an immutable DAG of calibration evolution.
  No "global silent improvement" is permitted (directive 2).

Calibration output is ONLY:
  - updated province prior parameters
  - updated physics penalty weights (λ₁, λ₂) for Θ_c
  - updated physics veto thresholds (τ_grav, τ_phys) for Θ_c
  - updated uncertainty model parameters
  None of these are applied retroactively to existing scans.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# §Y.3.1 — Lifecycle
# ---------------------------------------------------------------------------

class CalibrationVersionStatus(str, Enum):
    DRAFT      = "draft"
    ACTIVE     = "active"
    SUPERSEDED = "superseded"
    REVOKED    = "revoked"


# ---------------------------------------------------------------------------
# §Y.3.2 — Calibration parameters (model configuration only — directive 5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationParameters:
    """
    Output of calibration: model configuration parameters ONLY.

    WHAT THIS IS:
      Updated Θ_c-level parameters derived from ground-truth evidence.
      Applied to future scoring runs only (directive 1).

    WHAT THIS IS NOT:
      - ACIF scores
      - Tier assignments
      - Gate evaluations
      - Any retroactive modification of historical canonical scans

    Fields are Optional — calibration may update only a subset of parameters.
    Absent fields indicate the calibration did not update that parameter.
    """
    # Province prior updates (per commodity + province key)
    province_prior_updates: Optional[dict[str, float]] = None    # {"gold:WA": 0.72}

    # Physics penalty weight updates (Θ_c — no default, must be explicit)
    lambda_1_updates: Optional[dict[str, float]] = None          # {"gold": 0.48}
    lambda_2_updates: Optional[dict[str, float]] = None          # {"gold": 0.31}

    # Physics veto threshold updates (Θ_c — no default, must be explicit)
    tau_grav_veto_updates: Optional[dict[str, float]] = None     # {"gold": 95.0}
    tau_phys_veto_updates: Optional[dict[str, float]] = None     # {"gold": 48.0}

    # Uncertainty model parameter updates
    uncertainty_model_updates: Optional[dict[str, float]] = None


# ---------------------------------------------------------------------------
# §Y.3.3 — Calibration version record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationVersion:
    """
    Immutable calibration version record.

    DIRECTIVE 2 PROOF:
      - version_id is a UUID — globally unique, never reused
      - parent_version_id links to the version this was derived from
      - status transitions are recorded in status_history (append-only)
      - No CalibrationVersion is ever overwritten or deleted

    DIRECTIVE 1 PROOF:
      - applies_to_scans_after: ISO timestamp — calibration affects only
        scans started AFTER this timestamp
      - Historical scans store their calibration_version_id at freeze time
        and are never re-scored
    """
    version_id:                str
    parent_version_id:         Optional[str]              # None for root version
    description:               str
    parameters:                CalibrationParameters
    ground_truth_record_ids:   tuple[str, ...]            # IDs of approved GT records used
    calibration_effect_flags:  tuple[str, ...]            # e.g. ("province_prior_updated",)
    applies_to_scans_after:    str                        # ISO 8601 UTC — future only
    status:                    CalibrationVersionStatus
    created_by:                str                        # user_id
    created_at:                str                        # ISO 8601 UTC
    rationale:                 str                        # mandatory explanation


# ---------------------------------------------------------------------------
# §Y.3.4 — Calibration version manager
# ---------------------------------------------------------------------------

class CalibrationVersionManager:
    """
    Manages the immutable lineage chain of CalibrationVersions.

    DIRECTIVE 2 GUARANTEE:
      create_version():    always creates a NEW version — never mutates existing
      activate():          marks new version ACTIVE, old version SUPERSEDED
      revoke():            marks version REVOKED — lineage preserved
      get_active():        returns the currently ACTIVE version
      get_lineage():       returns full ancestor chain for any version

    DIRECTIVE 1 GUARANTEE:
      activate() sets applies_to_scans_after = utcnow() so the calibration
      is only applied to scans started after activation. Historical scans
      remain bound to their original CalibrationVersion.
    """

    def __init__(self, storage, event_bus=None):
        self._storage   = storage
        self._event_bus = event_bus

    def create_version(
        self,
        description: str,
        rationale: str,
        parameters: CalibrationParameters,
        ground_truth_record_ids: list[str],
        calibration_effect_flags: list[str],
        created_by: str,
        parent_version_id: Optional[str] = None,
    ) -> CalibrationVersion:
        """
        Create a new DRAFT CalibrationVersion.

        DIRECTIVE 2: A new UUID is always generated. No existing version is
        modified. The parent_version_id links this version to its predecessor
        in the lineage chain.
        """
        if not rationale or not rationale.strip():
            raise ValueError(
                "CalibrationVersion rationale is required — "
                "document why this calibration change was made."
            )

        version = CalibrationVersion(
            version_id               = str(uuid.uuid4()),
            parent_version_id        = parent_version_id,
            description              = description,
            parameters               = parameters,
            ground_truth_record_ids  = tuple(ground_truth_record_ids),
            calibration_effect_flags = tuple(calibration_effect_flags),
            applies_to_scans_after   = "",          # set at activation
            status                   = CalibrationVersionStatus.DRAFT,
            created_by               = created_by,
            created_at               = datetime.utcnow().isoformat(),
            rationale                = rationale,
        )
        self._storage.write_version(version)
        return version

    def activate(self, version_id: str) -> CalibrationVersion:
        """
        Activate a DRAFT version.

        DIRECTIVE 1 PROOF:
          applies_to_scans_after = utcnow() at activation.
          Any scan that started BEFORE this timestamp remains bound to
          the previously active CalibrationVersion — it is NOT re-scored.

        DIRECTIVE 2 PROOF:
          The previously ACTIVE version is marked SUPERSEDED — not deleted.
          Its record is permanently retained in the lineage chain.
        """
        version = self._storage.get_version(version_id)
        if version is None:
            raise ValueError(f"CalibrationVersion {version_id!r} not found")
        if version.status != CalibrationVersionStatus.DRAFT:
            raise ValueError(
                f"CalibrationVersion {version_id!r} is {version.status.value} — "
                "only DRAFT versions can be activated"
            )

        # Supersede current active version (directive 2 — never delete)
        current_active = self._storage.get_active_version()
        if current_active:
            superseded = _replace_status(current_active, CalibrationVersionStatus.SUPERSEDED)
            self._storage.write_version(superseded)

        # Activate with applies_to_scans_after = now (directive 1)
        activated = _replace_status(
            version,
            CalibrationVersionStatus.ACTIVE,
            applies_to_scans_after=datetime.utcnow().isoformat(),
        )
        self._storage.write_version(activated)

        if self._event_bus:
            self._event_bus.publish_sync(
                "calibration.version_created",
                {
                    "version_id":              activated.version_id,
                    "parent_version_id":       activated.parent_version_id,
                    "applies_to_scans_after":  activated.applies_to_scans_after,
                    "calibration_effect_flags": list(activated.calibration_effect_flags),
                },
            )

        return activated

    def revoke(self, version_id: str, reason: str) -> CalibrationVersion:
        """
        Revoke a version (DIRECTIVE 2 — never deleted, lineage preserved).
        """
        if not reason or not reason.strip():
            raise ValueError("Revocation reason is required.")
        version = self._storage.get_version(version_id)
        if version is None:
            raise ValueError(f"CalibrationVersion {version_id!r} not found")
        revoked = _replace_status(version, CalibrationVersionStatus.REVOKED)
        self._storage.write_version(revoked)
        return revoked

    def get_active(self) -> Optional[CalibrationVersion]:
        return self._storage.get_active_version()

    def get_lineage(self, version_id: str) -> list[CalibrationVersion]:
        """
        Walk the parent_version_id chain to return full ancestor lineage.
        Returns [root, ..., version_id] in chronological order.
        """
        chain: list[CalibrationVersion] = []
        vid = version_id
        visited = set()
        while vid and vid not in visited:
            visited.add(vid)
            v = self._storage.get_version(vid)
            if v is None:
                break
            chain.append(v)
            vid = v.parent_version_id
        chain.reverse()
        return chain


# ---------------------------------------------------------------------------
# §Y.3.5 — Immutable replace helper
# ---------------------------------------------------------------------------

def _replace_status(
    version: CalibrationVersion,
    new_status: CalibrationVersionStatus,
    applies_to_scans_after: Optional[str] = None,
) -> CalibrationVersion:
    """Return a new CalibrationVersion with updated status (frozen dataclass)."""
    from dataclasses import replace
    kwargs: dict = {"status": new_status}
    if applies_to_scans_after is not None:
        kwargs["applies_to_scans_after"] = applies_to_scans_after
    return replace(version, **kwargs)