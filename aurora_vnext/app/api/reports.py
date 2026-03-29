"""Aurora OSI vNext — Reports API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{scan_id}")
async def list_reports(scan_id: str):
    return []

@router.post("/{scan_id}", status_code=201)
async def generate_report(scan_id: str):
    return {"report_id": "stub", "scan_id": scan_id, "status": "generated"}
