"""Aurora OSI vNext — Export API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{scan_id}/json")
async def export_scan_json(scan_id: str):
    return {"scan_id": scan_id, "format": "json"}

@router.get("/{scan_id}/geojson")
async def export_scan_geojson(scan_id: str):
    return {"type": "FeatureCollection", "features": []}

@router.get("/{scan_id}/csv")
async def export_scan_csv(scan_id: str):
    return {"scan_id": scan_id, "format": "csv"}
