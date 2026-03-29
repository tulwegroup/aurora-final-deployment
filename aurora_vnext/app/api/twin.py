"""Aurora OSI vNext — Digital Twin API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{scan_id}")
async def get_twin_metadata(scan_id: str):
    return {"scan_id": scan_id, "status": "no_twin"}

@router.post("/{scan_id}/query")
async def query_twin_voxels(scan_id: str):
    return {"scan_id": scan_id, "voxels": []}

@router.get("/{scan_id}/slice")
async def get_twin_depth_slice(scan_id: str):
    return {"scan_id": scan_id, "voxels": []}
