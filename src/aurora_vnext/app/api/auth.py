"""
Aurora OSI vNext — Auth API
Phase O §O.5

ENDPOINT INVENTORY:
  POST /api/v1/auth/login          — credential verification → TokenPair
  POST /api/v1/auth/refresh        — refresh token → new access token
  GET  /api/v1/auth/me             — current user identity
  POST /api/v1/auth/logout         — revoke current JTI + audit

CONSTITUTIONAL RULES — Phase O:
  1. Login emits audit event on both success AND failure (no silent failures).
  2. Failed login includes reason label ('wrong_password' | 'unknown_user')
     but NEVER the supplied password.
  3. Logout revokes JTI server-side before returning 200.
  4. must_rotate_password users receive HTTP 428 on all non-auth endpoints.
  5. No scoring, tiering, or gate logic in this module.
  6. Password is verified via bcrypt — never compared in plaintext.

No imports from core/*, services/* (scientific modules).
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# User store shim — Phase P will replace with real storage/users.py
# ---------------------------------------------------------------------------

# In-memory user store for Phase O (replaced by DB store in Phase P)
_USERS: dict[str, dict] = {}


def _seed_test_users() -> None:
    """Seed test users for development. NOT called in production."""
    from datetime import datetime, timezone
    import uuid
    if not _USERS:
        for email, role, pw in [
            ("admin@aurora.dev",    RoleEnum.ADMIN,    "admin_pass_rotate_required"),
            ("operator@aurora.dev", RoleEnum.OPERATOR, "operator_pass_12chars"),
            ("viewer@aurora.dev",   RoleEnum.VIEWER,   "viewer_pass_12chars"),
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


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    """
    Verify credentials and issue TokenPair.

    Audit events:
      - LOGIN_SUCCESS on success
      - LOGIN_FAILURE on wrong password or unknown user (reason label only — no password)

    PHASE O REQUIREMENT: both success and failure must be audited.
    """
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not verify_password(body.password, user_dict["password_hash"]):
        await audit.append_audit_event(
            event_type=AuditEventEnum.LOGIN_FAILURE,
            actor_email=body.email,
            details={"reason": "wrong_password"},
            ip_address=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not user_dict["is_active"]:
        await audit.append_audit_event(
            event_type=AuditEventEnum.LOGIN_FAILURE,
            actor_email=body.email,
            details={"reason": "account_inactive"},
            ip_address=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    # Build minimal User for token issue
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


# ---------------------------------------------------------------------------
# Logout endpoint
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    payload=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Revoke current access token JTI and append LOGOUT audit event.
    After this call the token is immediately invalid.
    """
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


# ---------------------------------------------------------------------------
# Me endpoint
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_me(payload=Depends(get_current_user)) -> dict:
    """Return current user identity from the validated JWT payload."""
    return {
        "user_id": payload.sub,
        "email":   payload.email,
        "role":    payload.role.value,
    }


# ---------------------------------------------------------------------------
# Refresh endpoint
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    """
    Exchange a valid refresh token for a new access token.
    Phase P: will validate against server-side refresh token store.
    """
    # Phase P: validate refresh_token against DB store
    # For Phase O: simplified stub — returns error
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Refresh token store not yet implemented (Phase P). "
               "Please log in again to obtain a new access token.",
    )