"""Aurora OSI vNext — History API (stub)"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("")
async def list_scan_history():
    return {"scans": [], "total": 0, "page": 1, "page_size": 50, "total_pages": 0}

@router.get("/{scan_id}")
async def get_scan_record(scan_id: str):
    return {"scan_id": scan_id, "status": "NOT_FOUND"}
