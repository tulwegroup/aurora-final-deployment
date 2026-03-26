"""
Aurora OSI vNext — Storage Layer
Phase G

Exports all store classes for use by pipeline, API, and service layers.

IMPORT RULE: Storage layer imports models only.
  Stores do NOT import from core/, services/, api/, or pipeline/.
  Stores receive Pydantic models as arguments and return them as results.

LAYER TOPOLOGY:
  Layer 1 (Storage) ← Layer 4 (Pipeline) calls stores
  Layer 1 (Storage) ← Layer 5 (API) calls stores for read-only responses
  Layer 1 (Storage) does NOT call Layer 2+ modules
"""

from app.storage.audit import AuditLogStore
from app.storage.base import (
    AuroraStorageError,
    BaseStore,
    PaginatedResult,
    PaginationParams,
    StorageAuditViolationError,
    StorageConstraintError,
    StorageError,
    StorageImmutabilityError,
    StorageNotFoundError,
    StorageOffshoreGateError,
    StorageReplayError,
    get_db_session,
    get_engine,
    get_session_factory,
)
from app.storage.commodity_library import CommodityLibraryStore
from app.storage.history import HistoryIndexStore
from app.storage.observables import HarmonisedTensorStore, RawObservableStore
from app.storage.province_priors import ProvincePriorStore
from app.storage.scan_jobs import ScanJobStore
from app.storage.scans import CanonicalScanStore
from app.storage.twin import DigitalTwinStore

__all__ = [
    # Base
    "StorageError", "StorageImmutabilityError", "StorageNotFoundError",
    "StorageAuditViolationError", "StorageConstraintError",
    "StorageOffshoreGateError", "StorageReplayError",
    "BaseStore", "PaginationParams", "PaginatedResult",
    "get_db_session", "get_engine", "get_session_factory",
    # Stores
    "CanonicalScanStore", "ScanJobStore", "RawObservableStore",
    "HarmonisedTensorStore", "HistoryIndexStore", "DigitalTwinStore",
    "AuditLogStore", "CommodityLibraryStore", "ProvincePriorStore",
]