"""Aurora OSI vNext — Webhooks API (stub)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/consumers")
async def list_consumers():
    return []

@router.post("/consumers", status_code=201)
async def register_consumer():
    return {"consumer_id": "stub"}
