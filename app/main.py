"""
Aurora OSI vNext — Application Bootstrap
"""
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.constants import APP_DESCRIPTION, APP_NAME
from app.config.feature_flags import FLAGS
from app.config.settings import get_settings
from app.config.versions import get_version_registry_dict

logger = structlog.get_logger(__name__)
settings = get_settings()


def create_application() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://preview-sandbox--69c4c3161cd352e36ff3ede7.base44.app",
        "https://69c4c3161cd352e36ff3ede7.base44.app",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("aurora_startup", env=settings.aurora_env.value, version="0.1.0")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("aurora_shutdown")

    @app.get("/", tags=["System"])
    async def root() -> JSONResponse:
        return JSONResponse(status_code=200, content={"status": "alive", "service": "aurora-api"})

    @app.get("/health", tags=["System"])
    @app.get("/health/live", tags=["System"])
    async def health() -> JSONResponse:
        return JSONResponse(status_code=200, content={
            "status": "alive",
            "app": APP_NAME,
            "env": settings.aurora_env.value,
        })

    @app.get("/version", tags=["System"])
    async def version() -> JSONResponse:
        registry = get_version_registry_dict(overrides={
            "score_version": settings.aurora_score_version,
            "tier_version": settings.aurora_tier_version,
            "causal_graph_version": settings.aurora_causal_graph_version,
            "physics_model_version": settings.aurora_physics_model_version,
            "temporal_model_version": settings.aurora_temporal_model_version,
            "province_prior_version": settings.aurora_province_prior_version,
            "commodity_library_version": settings.aurora_commodity_library_version,
            "scan_pipeline_version": settings.aurora_scan_pipeline_version,
        })
        return JSONResponse(status_code=200, content={"app": APP_NAME, "version": "0.1.0", "registry": registry})

    # Mount all routers with try/except so a broken module doesn't kill everything
    def safe_include(import_fn, prefix=""):
        try:
            router = import_fn()
            if prefix:
                app.include_router(router, prefix=prefix)
            else:
                app.include_router(router)
            return True
        except Exception as e:
            logger.error("router_mount_failed", error=str(e))
            return False

    safe_include(lambda: __import__('app.api.scan', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.history', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.datasets', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.twin', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.auth', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.admin', fromlist=['router']).router, "/api/v1")
    safe_include(lambda: __import__('app.api.scan_aoi', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.map_exports', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.reports', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.portfolio', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.export', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.ground_truth_admin', fromlist=['router']).router)
    safe_include(lambda: __import__('app.api.data_room', fromlist=['router']).router)

    return app


app = create_application()
