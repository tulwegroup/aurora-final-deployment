"""
Aurora OSI vNext — Auth, User, Token, and Audit Models
Phase F §F.7

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import AuditEventEnum, RoleEnum


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(BaseModel):
    """Registered Aurora platform user."""

    user_id: str = Field(min_length=1)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: RoleEnum = Field(default=RoleEnum.VIEWER)
    is_active: bool = Field(default=True)
    must_rotate_password: bool = Field(
        default=False,
        description="True for bootstrap admin and freshly invited users"
    )
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"frozen": True}


class UserCreate(BaseModel):
    """Request model for creating a new user (admin only)."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: RoleEnum = RoleEnum.VIEWER
    temporary_password: str = Field(min_length=12)


class UserUpdateRole(BaseModel):
    """Request model for role change (admin only)."""

    user_id: str
    new_role: RoleEnum
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# JWT Tokens
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """Claims extracted from a validated JWT access token."""

    sub: str = Field(description="Subject: user_id")
    email: str
    role: RoleEnum
    jti: str = Field(description="JWT ID — used for revocation checking")
    exp: int = Field(description="Expiry Unix timestamp")
    iat: int = Field(description="Issued-at Unix timestamp")

    model_config = {"frozen": True}


class TokenPair(BaseModel):
    """Access + refresh token pair returned on successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")

    model_config = {"frozen": True}


class RefreshToken(BaseModel):
    """Stored refresh token record (server-side)."""

    jti: str = Field(description="JWT ID for revocation")
    user_id: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
    revoked_at: Optional[datetime] = None

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Auth request/response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Audit records
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    """
    Immutable audit log entry.

    CONSTITUTIONAL RULE: Audit records are APPEND-ONLY.
    No UPDATE or DELETE is permitted at any role level.
    This is enforced at the database level via PostgreSQL row-level security.
    """

    audit_id: str = Field(min_length=1)
    event_type: AuditEventEnum
    actor_user_id: Optional[str] = Field(
        default=None,
        description="User who triggered the event. None for system events."
    )
    actor_email: Optional[str] = Field(default=None)
    actor_role: Optional[RoleEnum] = Field(default=None)
    scan_id: Optional[str] = Field(
        default=None,
        description="Scan ID if event is scan-related"
    )
    details: Optional[dict] = Field(
        default=None,
        description="Structured event-specific details"
    )
    ip_address: Optional[str] = Field(default=None)
    timestamp: datetime = Field(description="Event timestamp — set server-side, never client-side")

    model_config = {"frozen": True}