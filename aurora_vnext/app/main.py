"""Aurora OSI vNext API — Main Entry Point"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config.feature_flags import FLAGS
from app.api import auth, scan, scan_aoi, history, datasets, twin, admin, reports, portfolio, map_exports, data_room, ground_truth_admin, export, health_and_discovery

app = FastAPI(
  title="Aurora OSI API",
  version="0.1.0",
  description="Mineral prospectivity platform"
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Mount all API routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(scan.router, prefix="/api/v1", tags=["scan"])
app.include_router(scan_aoi.router, prefix="/api/v1", tags=["aoi"])
app.include_router(history.router, prefix="/api/v1", tags=["history"])
app.include_router(datasets.router, prefix="/api/v1", tags=["datasets"])
app.include_router(twin.router, prefix="/api/v1", tags=["twin"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(map_exports.router, prefix="/api/v1", tags=["exports"])
app.include_router(data_room.router, prefix="/api/v1", tags=["data-room"])
app.include_router(ground_truth_admin.router, prefix="/api/v1", tags=["ground-truth"])
app.include_router(export.router, prefix="/api/v1", tags=["canonical-export"])
app.include_router(health_and_discovery.router, prefix="/api/v1", tags=["system"])

@app.get("/")
async def root():
  return {"status": "alive", "app": "Aurora OSI vNext"}

@app.get("/health")
async def health():
  return {"status": "alive", "version": "0.1.0"}