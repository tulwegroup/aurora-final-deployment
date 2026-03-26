"""
Aurora OSI vNext — Data Model Registry
Phase F

Exports all canonical model types for import by pipeline, API, and storage layers.

IMPORT RULE: Model imports are one-way.
  Models import from: enums only (within models/)
  Models do NOT import from: core/, services/, storage/, api/, pipeline/

Any import of a model from a module outside models/ is fine.
Any import INTO a model from outside models/ (except enums) is a violation.
"""

from app.models.auth_model import (
    AuditRecord,
    LoginRequest,
    RefreshRequest,
    RefreshToken,
    TokenPair,
    TokenPayload,
    User,
    UserCreate,
    UserUpdateRole,
)
from app.models.canonical_scan import CanonicalScan, CanonicalScanSummary
from app.models.digital_twin_model import (
    DigitalTwinVoxel,
    TwinMetadata,
    TwinQuery,
    TwinQueryResult,
    TwinVersion,
)
from app.models.enums import (
    AuditEventEnum,
    DeploymentEnvironment,
    MigrationClassEnum,
    PipelineStageEnum,
    RoleEnum,
    ScanEnvironment,
    ScanStatus,
    ScanTier,
    SystemStatusEnum,
    ThresholdSourceEnum,
    TierLabel,
)
from app.models.gate_results import (
    ConfirmationReason,
    GateResult,
    GateResults,
    SystemStatus,
)
from app.models.observable_vector import NormalisedFloat, ObservableVector
from app.models.scan_cell import ScanCell
from app.models.scan_job import ScanJob
from app.models.scan_request import (
    ScanGrid,
    ScanJobStatusResponse,
    ScanPolygon,
    ScanRequest,
    ScanStatusResponse,
    ScanSubmitResponse,
)
from app.models.threshold_policy import ThresholdPolicy, ThresholdSet
from app.models.tier_counts import TierCounts
from app.models.version_registry import VersionRegistry

__all__ = [
    # Enums
    "AuditEventEnum", "DeploymentEnvironment", "MigrationClassEnum",
    "PipelineStageEnum", "RoleEnum", "ScanEnvironment", "ScanStatus",
    "ScanTier", "SystemStatusEnum", "ThresholdSourceEnum", "TierLabel",
    # Observable + Version
    "NormalisedFloat", "ObservableVector", "VersionRegistry",
    # Threshold + Tier
    "ThresholdPolicy", "ThresholdSet", "TierCounts",
    # Gate + Status
    "ConfirmationReason", "GateResult", "GateResults", "SystemStatus",
    # Scan records
    "ScanCell", "ScanJob", "CanonicalScan", "CanonicalScanSummary",
    # Digital twin
    "DigitalTwinVoxel", "TwinMetadata", "TwinQuery", "TwinQueryResult", "TwinVersion",
    # Auth
    "AuditRecord", "LoginRequest", "RefreshRequest", "RefreshToken",
    "TokenPair", "TokenPayload", "User", "UserCreate", "UserUpdateRole",
    # Scan request/response
    "ScanGrid", "ScanPolygon", "ScanRequest", "ScanSubmitResponse",
    "ScanJobStatusResponse", "ScanStatusResponse",
]