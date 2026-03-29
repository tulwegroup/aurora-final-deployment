"""
Aurora OSI vNext — Standalone API Bootstrap (self-contained)
No imports from app.config or app.api — mounts routers dynamically via importlib.
"""
import logging
import importlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_include(application, router, **kwargs):
    try:
        application.include_router(router, **kwargs)
        logger.info("router_mounted prefix=%s", kwargs.get('prefix', '/'))
    except Exception as exc:
        logger.error("router_mount_failed prefix=%s error=%s", kwargs.get('prefix', '/'), exc)


app = FastAPI(title="Aurora OSI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    logger.info("aurora_startup version=0.1.0")
    router_specs = [
        ("app.api.scan",               "/api/v1/scan",        ["Scan"]),
        ("app.api.history",            "/api/v1/history",     ["History"]),
        ("app.api.datasets",           "/api/v1/datasets",    ["Datasets"]),
        ("app.api.twin",               "/api/v1/twin",        ["Twin"]),
        ("app.api.admin",              "/api/v1/admin",       ["Admin"]),
        ("app.api.auth",               "/auth",               ["Auth"]),
        ("app.api.scan_aoi",           "/api/v1/aoi",         ["AOI"]),
        ("app.api.export",             "/api/v1/exports",     ["Exports"]),
        ("app.api.reports",            "/api/v1/reports",     ["Reports"]),
        ("app.api.portfolio",          "/api/v1/portfolio",   ["Portfolio"]),
        ("app.api.ground_truth_admin", "/api/v1/gt",          ["Ground Truth"]),
        ("app.api.map_exports",        "/api/v1/map-exports", ["Map Exports"]),
        ("app.api.data_room",          "/api/v1/data-room",   ["Data Room"]),
        ("app.api.webhooks",           "/api/v1/webhooks",    ["Webhooks"]),
        ("app.api.health_and_discovery", "",                  ["System"]),
    ]
    for module_path, prefix, tags in router_specs:
        try:
            module = importlib.import_module(module_path)
            router = module.router
            kwargs = {"tags": tags}
            if prefix:
                kwargs["prefix"] = prefix
            safe_include(app, router, **kwargs)
        except Exception as exc:
            logger.error("router_import_failed module=%s error=%s", module_path, exc)


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
