"""Aurora OSI vNext — Scan API (stub)"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/active")
async def list_active_scans():
    return {"active_scans": [], "total": 0}

@router.get("/status/{scan_id}")
async def get_scan_status(scan_id: str):
    return {"scan_id": scan_id, "status": "NOT_FOUND"}

@router.post("/grid", status_code=202)
async def submit_grid_scan():
    return {"status": "accepted"}

@router.post("/polygon", status_code=202)
async def submit_polygon_scan():
    return {"status": "accepted"}
