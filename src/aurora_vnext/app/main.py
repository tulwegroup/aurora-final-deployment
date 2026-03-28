"""
Aurora OSI vNext — Application Bootstrap
Responsibilities (ONLY):
  - Create FastAPI application instance
  - Load settings and initialize logging
  - Mount API routers (stubbed until implementation phases complete)
  - Register startup/shutdown lifecycle hooks
  - Expose /health and /version endpoints

CONSTITUTIONAL RULE: This file must never contain:
  - Scoring equations or ACIF logic
  - Threshold values or tier logic
  - Commodity-specific heuristics
  - Dataset rendering transforms
  - Scientific module imports
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


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_application() -> FastAPI:
    """
    Create and configure the Aurora vNext FastAPI application.
    Routers are mounted here as phases complete.
    """
    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS — allow base44 preview/production origins in all environments
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        # base44 app origins
        "https://preview-sandbox--69c4c3161cd352e36ff3ede7.base44.app",
        "https://69c4c3161cd352e36ff3ede7.base44.app",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS if settings.is_production else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Lifecycle hooks
    # -------------------------------------------------------------------------

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "aurora_startup",
            env=settings.aurora_env.value,
            version="0.1.0",
            flags={k: v for k, v in FLAGS.__dict__.items()},
        )
        # Phase O: security bootstrap will be registered here
        # Phase G: database connection pool will be initialized here

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("aurora_shutdown")

    # -------------------------------------------------------------------------
    # Built-in endpoints (always available — no phase gate)
    # -------------------------------------------------------------------------

    @app.get("/", tags=["System"], summary="Root redirect")
    async def root() -> JSONResponse:
        """Redirect root to health endpoint."""
        return JSONResponse(
            status_code=200,
            content={"status": "alive", "redirect": "/health/live"},
        )

    @app.get("/health", tags=["System"], summary="Health check")
    @app.get("/health/live", tags=["System"], summary="Health check")
    async def health() -> JSONResponse:
        """Returns application health status.
        Always available regardless of feature flags.
        No authentication required."""
        return JSONResponse(
            status_code=200,
            content={
                "status": "alive",
                "app": APP_NAME,
                "env": settings.aurora_env.value,
                "flags": {
                    "storage": FLAGS.storage_layer_enabled,
                    "scientific_core": FLAGS.scientific_core_enabled,
                    "scoring_engine": FLAGS.scoring_engine_enabled,
                    "scan_pipeline": FLAGS.scan_pipeline_enabled,
                    "auth_enforced": FLAGS.auth_enforced,
                },
            },
        )

    @app.get("/version", tags=["System"], summary="Version registry")
    async def version() -> JSONResponse:
        """
        Returns the locked version registry for this deployment.
        All version fields are sourced from environment configuration.
        No authentication required.
        """
        registry = get_version_registry_dict(
            overrides={
                "score_version": settings.aurora_score_version,
                "tier_version": settings.aurora_tier_version,
                "causal_graph_version": settings.aurora_causal_graph_version,
                "physics_model_version": settings.aurora_physics_model_version,
                "temporal_model_version": settings.aurora_temporal_model_version,
                "province_prior_version": settings.aurora_province_prior_version,
                "commodity_library_version": settings.aurora_commodity_library_version,
                "scan_pipeline_version": settings.aurora_scan_pipeline_version,
            }
        )
        return JSONResponse(
            status_code=200,
            content={
                "app": APP_NAME,
                "version": "0.1.0",
                "registry": registry,
            },
        )

    # -------------------------------------------------------------------------
    # API routers — all phases mounted
    # -------------------------------------------------------------------------

    # Phase M — Scan execution, history, datasets, digital twin
    from app.api.scan import router as scan_router
    from app.api.history import router as history_router
    from app.api.datasets import router as datasets_router
    from app.api.twin import router as twin_router
    app.include_router(scan_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(datasets_router, prefix="/api/v1")
    app.include_router(twin_router, prefix="/api/v1")

    # Phase O — Auth and admin
    from app.api.auth import router as auth_router
    from app.api.admin import router as admin_router
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    # Phase AA — AOI management and map exports
    from app.api.scan_aoi import router as aoi_router
    from app.api.map_exports import router as map_exports_router
    app.include_router(aoi_router)        # already has /api/v1/aoi prefix
    app.include_router(map_exports_router)  # already has /api/v1/exports prefix

    # Phase AB — Reports
    from app.api.reports import router as reports_router
    app.include_router(reports_router)    # already has /api/v1/reports prefix

    # Phase AD — Portfolio
    from app.api.portfolio import router as portfolio_router
    app.include_router(portfolio_router)  # already has /api/v1/portfolio prefix

    # Phase X — Canonical data export
    from app.api.export import router as export_router
    app.include_router(export_router)     # already has /api/v1/export prefix

    # Phase Z — Ground truth admin
    from app.api.ground_truth_admin import router as gt_router
    app.include_router(gt_router)         # already has /api/v1/gt prefix

    return app


app = create_application()