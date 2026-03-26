"""
Aurora OSI vNext — Admin Bootstrap
Phase O §O.3

Bootstrap admin flow:
  1. Read AURORA_ADMIN_USER (email) and AURORA_ADMIN_PASS from environment.
  2. Validate password meets minimum complexity.
  3. Check no admin user already exists (idempotent — safe to call on every startup).
  4. Write audit event BEFORE creating the user record.
  5. Create admin user with must_rotate_password=True.
  6. Log bootstrap completion.

CONSTITUTIONAL RULES:
  - Credentials ONLY from environment variables — never from config files or DB seeds.
  - must_rotate_password=True on creation — admin must change password on first login.
  - AURORA_ADMIN_PASS minimum: 12 characters (enforced by settings validation).
  - Bootstrap is IDEMPOTENT: calling it when admin already exists is a no-op.
  - Bootstrap audit event is written BEFORE user creation (pre-flight audit).
  - This module never imports from core/*, services/* (scientific modules).

ROTATION REQUIREMENT:
  After first login the user is directed to POST /auth/rotate-password.
  Until rotation completes, all non-auth endpoints return HTTP 428 Precondition Required.
  (HTTP 428 chosen over 403 so clients can distinguish rotation-required from permission-denied.)

SECURITY: AURORA_ADMIN_PASS from env is NEVER logged, never stored in plaintext.
Only the bcrypt hash is persisted.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config.settings import get_settings
from app.models.auth_model import AuditRecord, User
from app.models.enums import AuditEventEnum, RoleEnum
from app.security.auth import hash_password

settings = get_settings()

# Minimum password entropy
_MIN_PASSWORD_LENGTH = 12


class BootstrapError(ValueError):
    """Raised when bootstrap preconditions are not met."""


def validate_bootstrap_credentials(email: str, password: str) -> None:
    """
    Validate bootstrap credentials before writing anything.

    Raises BootstrapError if:
      - email is empty or not a valid format
      - password is shorter than _MIN_PASSWORD_LENGTH
      - password equals the email (obvious credential reuse)
    """
    if not email or "@" not in email:
        raise BootstrapError(
            "AURORA_ADMIN_USER must be a valid email address."
        )
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise BootstrapError(
            f"AURORA_ADMIN_PASS must be at least {_MIN_PASSWORD_LENGTH} characters. "
            f"Current length: {len(password)}."
        )
    if password.lower() == email.lower():
        raise BootstrapError(
            "AURORA_ADMIN_PASS must not equal AURORA_ADMIN_USER."
        )


def build_bootstrap_user(email: str, password: str) -> dict:
    """
    Build the admin user dict from bootstrap credentials.

    Returns a dict suitable for DB insertion.
    Password is hashed with bcrypt before return.
    Plaintext password is never stored.
    """
    validate_bootstrap_credentials(email, password)
    return {
        "user_id":               str(uuid.uuid4()),
        "email":                 email,
        "full_name":             "Bootstrap Admin",
        "role":                  RoleEnum.ADMIN.value,
        "password_hash":         hash_password(password),
        "is_active":             True,
        "must_rotate_password":  True,    # ROTATION REQUIRED
        "created_at":            datetime.now(timezone.utc).isoformat(),
        "last_login_at":         None,
    }


class UserStoreAdapter:
    """Protocol for user store — injected; not imported from storage/ here."""
    async def admin_exists(self) -> bool: ...
    async def create_user(self, user_dict: dict) -> str: ...


class AuditStoreAdapter:
    """Protocol for audit store — injected."""
    async def append_audit_event(self, event_type, **kwargs) -> None: ...


async def run_bootstrap(
    user_store: UserStoreAdapter,
    audit_store: AuditStoreAdapter,
) -> Optional[str]:
    """
    Execute the admin bootstrap flow.

    IDEMPOTENT: if an admin user already exists, returns None immediately.

    FLOW:
      1. Validate env vars exist and meet complexity requirements.
      2. Check admin_exists() — abort (no-op) if True.
      3. Write ADMIN_BOOTSTRAPPED audit event (pre-flight).
      4. Create admin user with must_rotate_password=True.
      5. Return new user_id.

    Returns:
        user_id of created admin, or None if bootstrap already done.

    Raises:
        BootstrapError: if credentials are invalid.
        EnvironmentError: if AURORA_ADMIN_USER or AURORA_ADMIN_PASS are not set.
    """
    admin_email = os.environ.get("AURORA_ADMIN_USER") or settings.aurora_admin_user
    admin_pass  = os.environ.get("AURORA_ADMIN_PASS") or settings.aurora_admin_pass

    if not admin_email or not admin_pass:
        raise EnvironmentError(
            "Bootstrap requires AURORA_ADMIN_USER and AURORA_ADMIN_PASS "
            "to be set in environment variables."
        )

    # Step 1: Validate before any write
    validate_bootstrap_credentials(admin_email, admin_pass)

    # Step 2: Idempotency check
    if await user_store.admin_exists():
        return None   # Bootstrap already done — safe no-op

    # Step 3: Pre-flight audit (written BEFORE user creation)
    await audit_store.append_audit_event(
        event_type=AuditEventEnum.ADMIN_BOOTSTRAPPED,
        actor_email=admin_email,
        actor_role=RoleEnum.ADMIN,
        details={"must_rotate": True, "source": "environment_variable"},
    )

    # Step 4: Create admin user (password hash only — plaintext discarded)
    user_dict = build_bootstrap_user(admin_email, admin_pass)
    user_id = await user_store.create_user(user_dict)

    return user_id