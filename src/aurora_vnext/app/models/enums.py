"""
Aurora OSI vNext — Enumeration Types
Phase F §F.1

All system enumerations. No scientific logic. No scoring.
No imports from core/, services/, storage/, api/, or pipeline/.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Scan lifecycle
# ---------------------------------------------------------------------------

class ScanStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REPROCESSING = "REPROCESSING"
    MIGRATION_STUB = "MIGRATION_STUB"  # Phase R — legacy Class C records


class ScanEnvironment(str, Enum):
    ONSHORE = "ONSHORE"
    OFFSHORE = "OFFSHORE"
    COMBINED = "COMBINED"


class ScanTier(str, Enum):
    """Three-tier planetary scan funnel — Patent Breakthrough 11."""
    BOOTSTRAP = "BOOTSTRAP"    # Low-cost global screening
    SMART = "SMART"            # Regional refinement with full causal-physics AI
    PREMIUM = "PREMIUM"        # Drill-target scale derisking


# ---------------------------------------------------------------------------
# Tier assignment labels
# ---------------------------------------------------------------------------

class TierLabel(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    BELOW = "BELOW"


# ---------------------------------------------------------------------------
# System status (§14.3 Phase B)
# Derived exclusively by core/gates.py — never by API or frontend.
# ---------------------------------------------------------------------------

class SystemStatusEnum(str, Enum):
    PASS_CONFIRMED = "PASS_CONFIRMED"
    PARTIAL_SIGNAL = "PARTIAL_SIGNAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    OVERRIDE_CONFIRMED = "OVERRIDE_CONFIRMED"


# ---------------------------------------------------------------------------
# Threshold source provenance (§13.3 Phase B)
# Every completed scan must persist the provenance of its thresholds.
# ---------------------------------------------------------------------------

class ThresholdSourceEnum(str, Enum):
    AOI_PERCENTILE = "aoi_percentile"
    COMMODITY_FROZEN_DEFAULT = "commodity_frozen_default"
    GROUND_TRUTH_CALIBRATED = "ground_truth_calibrated"
    REPROCESSED = "reprocessed_vX"


# ---------------------------------------------------------------------------
# Deployment environment
# ---------------------------------------------------------------------------

class DeploymentEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

class RoleEnum(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Audit event types
# ---------------------------------------------------------------------------

class AuditEventEnum(str, Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SCAN_SUBMITTED = "scan_submitted"
    SCAN_DELETED = "scan_deleted"
    SCAN_REPROCESSED = "scan_reprocessed"
    THRESHOLD_POLICY_CHANGED = "threshold_policy_changed"
    CONFIG_CHANGED = "config_changed"
    VERSION_REGISTRY_BUMPED = "version_registry_bumped"
    DATA_EXPORTED = "data_exported"
    ROLE_CHANGED = "role_changed"
    ADMIN_BOOTSTRAPPED = "admin_bootstrapped"
    TWIN_GENERATED = "twin_generated"


# ---------------------------------------------------------------------------
# Pipeline stage labels (for ScanJob progress tracking)
# ---------------------------------------------------------------------------

class PipelineStageEnum(str, Enum):
    INITIALISED = "INITIALISED"
    SENSOR_ACQUISITION = "SENSOR_ACQUISITION"
    OFFSHORE_GATE = "OFFSHORE_GATE"
    HARMONIZATION = "HARMONIZATION"
    GRAVITY_DECOMPOSITION = "GRAVITY_DECOMPOSITION"
    OBSERVABLE_EXTRACTION = "OBSERVABLE_EXTRACTION"
    EVIDENCE_SCORING = "EVIDENCE_SCORING"
    CAUSAL_SCORING = "CAUSAL_SCORING"
    PHYSICS_SCORING = "PHYSICS_SCORING"
    TEMPORAL_SCORING = "TEMPORAL_SCORING"
    PROVINCE_PRIORS = "PROVINCE_PRIORS"
    UNCERTAINTY_PROPAGATION = "UNCERTAINTY_PROPAGATION"
    ACIF_ASSEMBLY = "ACIF_ASSEMBLY"
    TIERING = "TIERING"
    GATE_EVALUATION = "GATE_EVALUATION"
    TWIN_CONSTRUCTION = "TWIN_CONSTRUCTION"
    CANONICAL_FREEZE = "CANONICAL_FREEZE"
    POST_FREEZE_INDEX = "POST_FREEZE_INDEX"
    COMPLETED = "COMPLETED"


# ---------------------------------------------------------------------------
# Migration classification (Phase R)
# ---------------------------------------------------------------------------

class MigrationClassEnum(str, Enum):
    A = "A"   # Fully canonicalisable
    B = "B"   # Partial — missing fields, marked null
    C = "C"   # Incompatible — requires human review