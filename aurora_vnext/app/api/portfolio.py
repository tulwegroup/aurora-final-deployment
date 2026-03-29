"""Aurora OSI vNext — Portfolio API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def list_entries():
    return []

@router.get("/snapshot")
async def portfolio_snapshot():
    return {"entries": [], "total_entries": 0}

@router.post("", status_code=201)
async def assemble_entry():
    return {"entry_id": "stub"}
