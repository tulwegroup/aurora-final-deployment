"""Aurora OSI vNext — Scan AOI API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.post("/validate")
async def validate_geometry():
    return {"valid": True, "errors": []}

@router.post("", status_code=201)
async def save_aoi():
    return {"aoi_id": "stub"}

@router.get("/{aoi_id}")
async def get_aoi(aoi_id: str):
    return {"aoi_id": aoi_id}
