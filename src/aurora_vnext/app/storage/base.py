"""
Aurora OSI vNext — Storage Layer Base Classes and Exceptions
Phase G

Defines shared abstractions, connection management, and the exception
hierarchy for all storage modules.

CONSTITUTIONAL RULES enforced at this layer:
  - StorageImmutabilityError: raised when a write is attempted against a
    COMPLETED canonical scan. Enforced by DB trigger AND application layer.
  - StorageAuditViolationError: raised when UPDATE/DELETE is attempted
    against the audit log. Enforced by PostgreSQL RLS AND application layer.
  - No scientific logic. No scoring. No imports from core/ or services/.
"""

from __future__ import annotations

from abc import ABC
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class StorageError(Exception):
    """Base class for all Aurora storage errors."""

# alias for backwards-compat imports
AuroraStorageError = StorageError


class StorageImmutabilityError(StorageError):
    """
    Raised when an attempt is made to modify a COMPLETED CanonicalScan record.

    Sources:
      1. PostgreSQL trigger (trg_canonical_scan_immutability) — database level
      2. storage/scans.py freeze guard — application level
    """


class StorageNotFoundError(StorageError):
    """Raised when a requested record does not exist."""


class StorageAuditViolationError(StorageError):
    """
    Raised when UPDATE or DELETE is attempted against the audit_log table.
    Enforced by PostgreSQL RLS and mirrored in storage/audit.py.
    """


class StorageConstraintError(StorageError):
    """Raised when a database constraint is violated."""


class StorageOffshoreGateError(StorageError):
    """
    Raised when an offshore ScanCell is written without offshore_corrected=True.
    Enforces that offshore cells cannot enter the canonical store uncorrected.
    """


class StorageReplayError(StorageError):
    """Raised when a replay/reprocess request violates lineage constraints."""


# ---------------------------------------------------------------------------
# Database engine + session factory
# ---------------------------------------------------------------------------

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.aurora_env.value == "development",
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session():
    """FastAPI dependency: yields a scoped async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Abstract base store
# ---------------------------------------------------------------------------

class BaseStore:
    """
    Base for all Aurora storage modules.
    Each store operates on a single primary entity type.
    Stores do not call each other — composed by pipeline and API layers.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

class PaginationParams:
    def __init__(self, page: int = 1, page_size: int = 50):
        if page < 1:
            raise ValueError("page must be >= 1")
        if not (1 <= page_size <= 500):
            raise ValueError("page_size must be between 1 and 500")
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

    @classmethod
    def default(cls) -> "PaginationParams":
        return cls(page=1, page_size=50)


class PaginatedResult:
    def __init__(self, items: list, total: int, params: PaginationParams):
        self.items = items
        self.total = total
        self.page = params.page
        self.page_size = params.page_size
        self.total_pages = max(1, -(-total // params.page_size))