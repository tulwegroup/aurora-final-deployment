"""Aurora OSI vNext — Map Exports API (stub)"""
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

@router.get("/layers")
async def list_layers():
    return []

@router.post("/{scan_id}/kml")
async def export_kml(scan_id: str):
    return Response(content=b"", media_type="application/vnd.google-earth.kml+xml")

@router.post("/{scan_id}/geojson")
async def export_geojson(scan_id: str):
    return {"type": "FeatureCollection", "features": []}
