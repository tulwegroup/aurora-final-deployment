"""Aurora OSI vNext — Datasets API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/summary/{scan_id}")
async def get_dataset_summary(scan_id: str):
    return {"scan_id": scan_id}

@router.get("/geojson/{scan_id}")
async def get_scan_geojson(scan_id: str):
    return {"type": "FeatureCollection", "features": []}

@router.get("/package/{scan_id}")
async def get_data_package(scan_id: str):
    return {"scan_id": scan_id}
