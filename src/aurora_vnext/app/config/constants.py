"""
Aurora OSI vNext — System-Wide Constants
Fixed values that do not change at runtime.
No scientific logic. No scoring formulas. No thresholds.
"""

# Application identity
APP_NAME = "Aurora OSI vNext"
APP_DESCRIPTION = (
    "Planetary-scale physics-causal sovereign subsurface intelligence platform. "
    "Clean-room rebuild governed by Aurora Patent Specification."
)

# API versioning
API_V1_PREFIX = "/api/v1"

# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

# Scan job constraints
MAX_CONCURRENT_SCANS_PER_USER = 3
SCAN_JOB_TIMEOUT_SECONDS = 3600          # 1 hour hard timeout for pipeline execution
SCAN_JOB_HEARTBEAT_INTERVAL_SECONDS = 30

# Observable vector dimension
OBSERVABLE_VECTOR_DIM = 42               # Defined in Phase A observable registry
                                          # Must match ObservableVector field count

# Tier labels (display only — tiering logic lives exclusively in core/tiering.py)
TIER_LABEL_1 = "TIER_1"
TIER_LABEL_2 = "TIER_2"
TIER_LABEL_3 = "TIER_3"
TIER_LABEL_BELOW = "BELOW"

# Scan environment labels
ENV_ONSHORE = "ONSHORE"
ENV_OFFSHORE = "OFFSHORE"
ENV_COMBINED = "COMBINED"

# Scan tier labels (three-tier planetary scan funnel — Patent Breakthrough 11)
SCAN_TIER_BOOTSTRAP = "BOOTSTRAP"        # Low-cost global screening
SCAN_TIER_SMART = "SMART"               # Regional refinement with full causal-physics AI
SCAN_TIER_PREMIUM = "PREMIUM"           # Drill-target scale derisking

# Scan status labels
STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_REPROCESSING = "REPROCESSING"
STATUS_MIGRATION_STUB = "MIGRATION_STUB"  # Legacy migration class C records

# Threshold source labels (§13.3 Phase B — stored with every scan)
THRESHOLD_SOURCE_AOI_PERCENTILE = "aoi_percentile"
THRESHOLD_SOURCE_COMMODITY_DEFAULT = "commodity_frozen_default"
THRESHOLD_SOURCE_GROUND_TRUTH = "ground_truth_calibrated"
THRESHOLD_SOURCE_REPROCESSED = "reprocessed_vX"

# System status labels (§14.3 Phase B)
SYSTEM_STATUS_PASS_CONFIRMED = "PASS_CONFIRMED"
SYSTEM_STATUS_PARTIAL_SIGNAL = "PARTIAL_SIGNAL"
SYSTEM_STATUS_INCONCLUSIVE = "INCONCLUSIVE"
SYSTEM_STATUS_REJECTED = "REJECTED"
SYSTEM_STATUS_OVERRIDE_CONFIRMED = "OVERRIDE_CONFIRMED"

# Role labels
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

# Audit event types
AUDIT_LOGIN_SUCCESS = "login_success"
AUDIT_LOGIN_FAILURE = "login_failure"
AUDIT_SCAN_SUBMITTED = "scan_submitted"
AUDIT_SCAN_DELETED = "scan_deleted"
AUDIT_SCAN_REPROCESSED = "scan_reprocessed"
AUDIT_THRESHOLD_CHANGED = "threshold_policy_changed"
AUDIT_CONFIG_CHANGED = "config_changed"
AUDIT_VERSION_BUMPED = "version_registry_bumped"
AUDIT_EXPORT = "data_exported"
AUDIT_ROLE_CHANGED = "role_changed"
AUDIT_BOOTSTRAP = "admin_bootstrapped"

# Migration classification labels (Phase R)
MIGRATION_CLASS_A = "A"     # Fully canonicalizable
MIGRATION_CLASS_B = "B"     # Partial — missing some fields
MIGRATION_CLASS_C = "C"     # Incompatible — requires human review