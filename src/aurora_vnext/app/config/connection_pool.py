"""
Aurora OSI vNext — Database & Redis Connection Pool Configuration
Phase T §T.3 — Connection Pool Management

Provides:
  - create_db_engine(): SQLAlchemy async engine with pool sizing
  - create_redis_client(): redis.asyncio client with connection pool
  - lifespan context manager for FastAPI startup/shutdown

CONSTITUTIONAL RULES — Phase T:
  Rule 1: Pool sizing parameters are infrastructure constants.
           They are NOT scientific constants. No relation to ACIF, tiers, or thresholds.
  Rule 2: This module performs no database reads at construction time.
           It configures connection parameters only.
  Rule 3: No import from core/*.
  Rule 4: All sizing constants are documented with their infrastructure rationale.
           None are physics-justified or patent-traceable (they don't need to be —
           they are not scientific parameters).

POOL SIZING RATIONALE (infrastructure, not science):
  DB pool_size=10:    Supports ~10 concurrent API workers each holding one connection.
  DB max_overflow=20: Allows burst to 30 total — covers scan submission spikes.
  DB pool_timeout=30: 30s wait before raising PoolTimeout — aligns with HTTP timeout.
  DB pool_recycle=3600: Recycle connections every 1h to avoid idle TCP drops (AWS RDS).
  Redis pool_size=20: One connection per async worker + headroom for pub/sub.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config.observability import get_logger
from app.config.settings import get_settings

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pool sizing — infrastructure constants (documented above, not scientific)
# ---------------------------------------------------------------------------

DB_POOL_SIZE     = 10
DB_MAX_OVERFLOW  = 20
DB_POOL_TIMEOUT  = 30     # seconds
DB_POOL_RECYCLE  = 3600   # seconds — 1 hour
DB_ECHO_SQL      = False   # Set True for query-level debug logging only

REDIS_POOL_SIZE  = 20
REDIS_SOCKET_TIMEOUT = 5  # seconds
REDIS_RETRY_ON_TIMEOUT = True


# ---------------------------------------------------------------------------
# DB engine factory
# ---------------------------------------------------------------------------

def create_db_engine(database_url: str = None):
    """
    Create SQLAlchemy async engine with connection pool.

    Args:
        database_url: Override URL (defaults to settings.database_url).

    Returns:
        sqlalchemy.ext.asyncio.AsyncEngine
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    s = get_settings()
    url = database_url or s.database_url

    engine = create_async_engine(
        url,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT,
        pool_recycle=DB_POOL_RECYCLE,
        pool_pre_ping=True,       # Verify connections before checkout (handles stale TCP)
        echo=DB_ECHO_SQL,
    )
    logger.info(
        "db_engine_created",
        extra={
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_recycle": DB_POOL_RECYCLE,
        },
    )
    return engine


# ---------------------------------------------------------------------------
# Redis client factory
# ---------------------------------------------------------------------------

def create_redis_client(redis_url: str = None):
    """
    Create async Redis client with connection pool.

    Args:
        redis_url: Override URL (defaults to settings.redis_url).

    Returns:
        redis.asyncio.Redis
    """
    import redis.asyncio as aioredis

    s = get_settings()
    url = redis_url or getattr(s, "redis_url", "redis://localhost:6379/0")

    client = aioredis.from_url(
        url,
        max_connections=REDIS_POOL_SIZE,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
        retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
        decode_responses=True,
    )
    logger.info("redis_client_created", extra={"pool_size": REDIS_POOL_SIZE})
    return client


# ---------------------------------------------------------------------------
# FastAPI lifespan — startup / shutdown connection management
# ---------------------------------------------------------------------------

@asynccontextmanager
async def aurora_lifespan(app) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Creates DB engine and Redis client at startup; disposes at shutdown.

    Usage in main.py:
        app = FastAPI(lifespan=aurora_lifespan)
    """
    engine = create_db_engine()
    redis  = create_redis_client()

    # Store on app.state for dependency injection
    app.state.db_engine   = engine
    app.state.redis_client = redis

    logger.info("aurora_startup_complete")

    yield   # Application runs here

    # Graceful shutdown
    await engine.dispose()
    await redis.aclose()
    logger.info("aurora_shutdown_complete")


# ---------------------------------------------------------------------------
# Dependency injection helpers (for FastAPI routes)
# ---------------------------------------------------------------------------

async def get_db_session(request):
    """
    FastAPI dependency: yields an AsyncSession from the engine pool.
    Usage: session: AsyncSession = Depends(get_db_session)
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = request.app.state.db_engine
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def get_cache(request) -> "CacheClient":
    """
    FastAPI dependency: returns the shared CacheClient.
    Usage: cache: CacheClient = Depends(get_cache)
    """
    from app.storage.cache import CacheClient
    return CacheClient(request.app.state.redis_client)


def get_redis(request):
    """FastAPI dependency: returns raw Redis client."""
    return request.app.state.redis_client