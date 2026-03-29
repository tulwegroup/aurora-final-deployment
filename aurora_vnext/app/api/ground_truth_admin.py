"""Aurora OSI vNext — Ground Truth Admin API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/records")
async def list_records():
    return []

@router.post("/records", status_code=201)
async def submit_record():
    return {"record_id": "stub", "status": "pending"}

@router.get("/audit")
async def full_audit_log():
    return []

@router.get("/calibration/versions")
async def list_calibration_versions():
    return []
