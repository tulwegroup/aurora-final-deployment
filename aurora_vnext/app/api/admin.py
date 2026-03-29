"""Aurora OSI vNext — Admin API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/bootstrap-status")
async def bootstrap_status():
    return {"bootstrap_done": True, "admin_count": 1, "rotation_pending": False}

@router.get("/users")
async def list_users():
    return {"users": [], "total": 0}

@router.get("/audit")
async def query_audit_log():
    return {"events": [], "total": 0}
