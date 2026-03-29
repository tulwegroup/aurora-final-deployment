"""Aurora OSI vNext — Auth API (stub)"""
from fastapi import APIRouter

router = APIRouter()

_USERS = {}

@router.post("/login")
async def login():
    return {"error": "auth not configured"}

@router.get("/me")
async def get_me():
    return {"user_id": "anonymous"}
