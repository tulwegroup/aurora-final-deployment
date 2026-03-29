"""Health check endpoints"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health", tags=["System"])
@router.get("/health/live", tags=["System"])
async def health():
    return JSONResponse({"status": "alive", "version": "0.1.0"})

@router.get("/version", tags=["System"])
async def version():
    return JSONResponse({"version": "0.1.0", "service": "aurora-api"})

@router.get("/", tags=["System"])
async def root():
    return JSONResponse({"status": "alive", "service": "aurora-api"})
