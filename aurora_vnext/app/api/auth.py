"""
Aurora OSI vNext — Auth API
Phase O §O.5
"""

from __future__ import annotations
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_model import LoginRequest, RefreshRequest, TokenPair, User
from app.models.enums import AuditEventEnum, RoleEnum
from app.security.auth import (
    decode_access_token,
    get_current_user,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    revoke_token_jti,
    verify_password,
)
from app.storage.base import get_db_session
from app.storage.audit import AuditLogStore

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else request.client.host if request.client else None


_USERS: dict[str, dict] = {}


def _seed_test_users() -> None:
    from datetime import datetime, timezone
    import uuid
    if not _USERS:
        admin_email = os.environ.get("AURORA_ADMIN_USER", "admin@aurora-osi.com")
        admin_pass  = os.environ.get("AURORA_ADMIN_PASS", "admin_pass_rotate_required")
        for email, role, pw in [
            (admin_email,               RoleEnum.ADMIN,    admin_pass),
            ("operator@aurora-osi.com", RoleEnum.OPERATOR, "operator_pass_12chars"),
            ("viewer@aurora-osi.com",   RoleEnum.VIEWER,   "viewer_pass_12chars"),
        ]:
            uid = str(uuid.uuid4())
            _USERS[email] = {
                "user_id":              uid,
                "email":                email,
                "full_name":            role.value.title(),
                "role":                 role,
                "password_hash":        hash_password(pw),
                "is_active":            True,
                "must_rotate_password": role == RoleEnum.ADMIN,
                "created_at":           datetime.now(timezone.utc),
            }


_seed_test_users()


def _lookup_user(email: str) -> Optional[dict]:
    return _USERS.get(email)


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    audit = AuditLogStore(db)
    ip = _get_ip(request)
    user_dict = _lookup_user(body.email)

    if user_dict is None:
        await audit.append_audit_event(
            event_type=AuditEventEnum.LOGIN_FAILURE,
            actor_email=body.email,
            details={"reason": "unknown_user"},
            ip_address=ip,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not verify_password(body.password, user_dict["password_hash"]):
        await audit.append_audit_event(
            event_type=AuditEventEnum.LOGIN_FAILURE,
            actor_email=body.email,
            details={"reason": "wrong_password"},
            ip_address=ip,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not user_dict["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    from datetime import datetime, timezone
    user = User(
        user_id=user_dict["user_id"],
        email=user_dict["email"],
        full_name=user_dict["full_name"],
        role=user_dict["role"],
        is_active=True,
        must_rotate_password=user_dict.get("must_rotate_password", False),
        created_at=user_dict["created_at"],
    )

    token_str, jti = issue_access_token(user)
    refresh_tok = issue_refresh_token(user.user_id)

    await audit.append_audit_event(
        event_type=AuditEventEnum.LOGIN_SUCCESS,
        actor_user_id=user.user_id,
        actor_email=user.email,
        actor_role=user.role,
        details={"jti": jti, "must_rotate": user.must_rotate_password},
        ip_address=ip,
    )

    from app.config.settings import get_settings
    s = get_settings()
    return TokenPair(
        access_token=token_str,
        refresh_token=refresh_tok,
        expires_in=s.aurora_jwt_access_expiry_min * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    payload=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    revoke_token_jti(payload.jti)
    audit = AuditLogStore(db)
    await audit.append_audit_event(
        event_type=AuditEventEnum.LOGOUT,
        actor_user_id=payload.sub,
        actor_email=payload.email,
        actor_role=payload.role,
        details={"revoked_jti": payload.jti},
        ip_address=_get_ip(request),
    )
    return {"logged_out": True, "jti_revoked": payload.jti}


@router.get("/me")
async def get_me(payload=Depends(get_current_user)) -> dict:
    return {"user_id": payload.sub, "email": payload.email, "role": payload.role.value}


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Refresh token store not yet implemented (Phase P). Please log in again.",
    )
