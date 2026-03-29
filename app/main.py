"""
Aurora OSI vNext — Standalone API Bootstrap
Self-contained: no imports from app.config or app.api submodules.
All routers are imported with safe_include to allow partial failures.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_include(app, router, **kwargs):
    """Mount a router, logging errors without crashing startup."""
    try:
        app.include_router(router, **kwargs)
        logger.info(f"router_mounted prefix={kwargs.get('prefix', '/')}")
    except Exception as exc:
        logger.error(f"router_mount_failed prefix={kwargs.get('prefix', '/')} error={exc}")


def create_application() -> FastAPI:
    application = FastAPI(
        title="Aurora OSI API",
        description="Aurora subsurface intelligence platform",
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    async def on_startup():
        logger.info("aurora_startup env=production version=0.1.0")
        _mount_routers(application)

    @application.get("/", tags=["System"])
    async def root():
        return JSONResponse({"status": "alive", "service": "aurora-api"})

    @application.get("/health", tags=["System"])
    @application.get("/health/live", tags=["System"])
    async def health():
        return JSONResponse({"status": "alive", "version": "0.1.0"})

    @application.get("/version", tags=["System"])
    async def version():
        return JSONResponse({"version": "0.1.0", "service": "aurora-api"})

    return application


def _mount_routers(application):
    """Dynamically import and mount all API routers."""
    router_specs = [
        ("app.api.scan",           "/api/v1/scan",       ["Scan"]),
        ("app.api.history",        "/api/v1/history",    ["History"]),
        ("app.api.datasets",       "/api/v1/datasets",   ["Datasets"]),
        ("app.api.twin",           "/api/v1/twin",       ["Twin"]),
        ("app.api.admin",          "/api/v1/admin",      ["Admin"]),
        ("app.api.auth",           "/auth",              ["Auth"]),
        ("app.api.scan_aoi",       "/api/v1/aoi",        ["AOI"]),
        ("app.api.export",         "/api/v1/exports",    ["Exports"]),
        ("app.api.reports",        "/api/v1/reports",    ["Reports"]),
        ("app.api.portfolio",      "/api/v1/portfolio",  ["Portfolio"]),
        ("app.api.ground_truth_admin", "/api/v1/gt",     ["Ground Truth"]),
        ("app.api.map_exports",    "/api/v1/map-exports",["Map Exports"]),
        ("app.api.data_room",      "/api/v1/data-room",  ["Data Room"]),
        ("app.api.webhooks",       "/api/v1/webhooks",   ["Webhooks"]),
    ]
    for module_path, prefix, tags in router_specs:
        try:
            import importlib
            module = importlib.import_module(module_path)
            router = module.router
            safe_include(application, router, prefix=prefix, tags=tags)
        except Exception as exc:
            logger.error(f"router_import_failed module={module_path} error={exc}")


app = create_application()
