"""
Aurora OSI vNext — Standalone main.py
Mounts routers dynamically via importlib to avoid import-time failures.
Auth router has its own prefix="/auth" baked in, so it is mounted with NO extra prefix.
Login endpoint: POST /auth/login
"""
import logging
import importlib
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aurora OSI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def safe_include(application, router, **kwargs):
    try:
        application.include_router(router, **kwargs)
        logger.info("router_mounted prefix=%s", kwargs.get("prefix", "(router default)"))
    except Exception as exc:
        logger.error("router_mount_failed prefix=%s error=%s", kwargs.get("prefix", "(router default)"), exc)


@app.on_event("startup")
async def on_startup():
    logger.info("aurora_startup version=0.1.0")

    # Routers that carry their own prefix inside the module
    self_prefixed = [
        ("app.api.auth",              None,                ["Auth"]),
        ("app.api.scan_aoi",          None,                ["AOI"]),
        ("app.api.map_exports",       None,                ["Map Exports"]),
        ("app.api.reports",           None,                ["Reports"]),
        ("app.api.portfolio",         None,                ["Portfolio"]),
        ("app.api.ground_truth_admin",None,                ["Ground Truth"]),
        ("app.api.data_room",         None,                ["Data Room"]),
        ("app.api.webhooks",          None,                ["Webhooks"]),
    ]

    # Routers that need an explicit prefix
    explicit_prefix = [
        ("app.api.scan",     "/api/v1",          ["Scan"]),
        ("app.api.history",  "/api/v1",          ["History"]),
        ("app.api.datasets", "/api/v1/datasets", ["Datasets"]),
        ("app.api.twin",     "/api/v1",          ["Twin"]),
        ("app.api.admin",    "/api/v1",          ["Admin"]),
        ("app.api.export",   "/api/v1/exports",  ["Exports"]),
    ]

    for module_path, prefix, tags in self_prefixed:
        try:
            module = importlib.import_module(module_path)
            if prefix is None:
                safe_include(app, module.router, tags=tags)
            else:
                safe_include(app, module.router, prefix=prefix, tags=tags)
        except Exception as exc:
            logger.error(
                "router_import_failed module=%s error=%s trace=%s",
                module_path, exc, traceback.format_exc()
            )

    for module_path, prefix, tags in explicit_prefix:
        try:
            module = importlib.import_module(module_path)
            safe_include(app, module.router, prefix=prefix, tags=tags)
        except Exception as exc:
            logger.error(
                "router_import_failed module=%s error=%s trace=%s",
                module_path, exc, traceback.format_exc()
            )


@app.get("/", tags=["System"])
async def root():
    return JSONResponse({"status": "alive", "service": "aurora-api"})


@app.get("/health", tags=["System"])
@app.get("/health/live", tags=["System"])
async def health():
    return JSONResponse({"status": "alive", "version": "0.1.0"})


@app.get("/version", tags=["System"])
async def version():
    return JSONResponse({"version": "0.1.0", "service": "aurora-api"})
