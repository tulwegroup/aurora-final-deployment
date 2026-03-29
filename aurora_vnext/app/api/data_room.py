"""Aurora OSI vNext — Data Room API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/packages")
async def list_packages():
    return {"packages": [], "total": 0}

@router.post("/packages", status_code=201)
async def create_package():
    return {"package": {"package_id": "stub"}, "link": {}}

@router.get("/links")
async def list_links():
    return {"links": [], "total": 0}
