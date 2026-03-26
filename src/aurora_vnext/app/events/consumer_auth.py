"""
Aurora OSI vNext — Webhook Consumer API Key Authentication
Phase W §W.1

Provides:
  - generate_api_key(): cryptographically random 32-byte token
  - hash_api_key(): BLAKE2b hash for storage (never store plaintext)
  - verify_api_key(): constant-time comparison against stored hash
  - ConsumerScope: subscription scope — event_type strings ONLY
  - verify_webhook_signature(): HMAC-SHA256 payload verification helper

CONSTITUTIONAL RULES — Phase W:
  Rule 1: API keys are cryptographically random tokens — no scientific metadata,
          no embedded claims, no scan_tier or ACIF score information.
  Rule 2: ConsumerScope.event_types is a set of EventType strings only.
          No field-level filter (e.g. filter_by_tier, filter_by_acif_threshold)
          is permitted. Scope is by event type only — not by scientific value.
  Rule 3: Signature verification operates on raw payload bytes only.
          It does not deserialise, inspect, or act on scientific field values.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from typing import Optional

from app.events.event_bus import EventType


# ---------------------------------------------------------------------------
# API key generation and storage
# ---------------------------------------------------------------------------

# Key format: 32 random bytes → base64url → "aur_" prefix for identification
_KEY_BYTES    = 32
_KEY_PREFIX   = "aur_"

# BLAKE2b parameters for key storage hash
_HASH_DIGEST_SIZE = 32   # 256-bit hash


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new webhook consumer API key.

    Returns:
        (plaintext_key, stored_hash)
        plaintext_key: shown to consumer ONCE — never stored by Aurora
        stored_hash:   BLAKE2b hash — stored in DB, used for verification

    RULE 1: Key is 32 random bytes — no scientific metadata, no embedded claims.
    """
    raw = secrets.token_bytes(_KEY_BYTES)
    plaintext = _KEY_PREFIX + raw.hex()
    stored_hash = _hash_key(plaintext)
    return plaintext, stored_hash


def _hash_key(plaintext: str) -> str:
    """
    BLAKE2b hash of the plaintext key.
    Used for storage — plaintext is never stored.
    """
    return hashlib.blake2b(
        plaintext.encode("utf-8"),
        digest_size=_HASH_DIGEST_SIZE,
    ).hexdigest()


def hash_api_key(plaintext: str) -> str:
    """Public interface for hashing a key (e.g. at verification time)."""
    return _hash_key(plaintext)


def verify_api_key(plaintext: str, stored_hash: str) -> bool:
    """
    Constant-time comparison of plaintext key against stored hash.
    Returns True if key is valid.

    RULE 3: operates on token strings only — no scientific field inspection.
    """
    candidate_hash = _hash_key(plaintext)
    return hmac.compare_digest(candidate_hash, stored_hash)


# ---------------------------------------------------------------------------
# Consumer subscription scope
# ---------------------------------------------------------------------------

@dataclass
class ConsumerScope:
    """
    Subscription scope for a webhook consumer endpoint.

    event_types: set of EventType strings the consumer subscribes to.
                 RULE 2: Contains only event type strings — never scientific
                 field values, tier filters, or score thresholds.

    Examples:
        ConsumerScope(event_types={"scan.completed", "twin.built"})
        ConsumerScope(event_types={"scan.completed"})

    NOT PERMITTED:
        ConsumerScope(filter_by_tier="TIER_1")       ← scientific filter
        ConsumerScope(min_acif_score=0.7)            ← scientific threshold
    """
    event_types: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        invalid = self.event_types - EventType._ALL
        if invalid:
            raise ValueError(
                f"Unknown event types in scope: {invalid}. "
                f"Permitted: {EventType._ALL}"
            )

    def matches(self, event_type: str) -> bool:
        """Returns True if this scope subscribes to the given event type."""
        return event_type in self.event_types

    @classmethod
    def all_events(cls) -> "ConsumerScope":
        return cls(event_types=set(EventType._ALL))

    @classmethod
    def scan_events_only(cls) -> "ConsumerScope":
        return cls(event_types={EventType.SCAN_COMPLETED, EventType.SCAN_FAILED,
                                EventType.SCAN_REPROCESSING})


# ---------------------------------------------------------------------------
# Consumer endpoint registration record
# ---------------------------------------------------------------------------

@dataclass
class RegisteredConsumer:
    """
    A registered webhook consumer.

    consumer_id:   UUID string — unique identifier
    name:          Human-readable name (e.g. "Downstream Pipeline A")
    endpoint_url:  HTTPS URL for delivery
    key_hash:      BLAKE2b hash of API key — for authentication
    signing_secret: HMAC secret used to sign webhook payloads
    scope:         ConsumerScope — event types only (Rule 2)
    active:        Whether deliveries should be attempted
    created_at:    ISO timestamp — infrastructure metadata
    """
    consumer_id:    str
    name:           str
    endpoint_url:   str
    key_hash:       str          # stored hash — plaintext never stored
    signing_secret: str          # random secret for HMAC signing
    scope:          ConsumerScope
    active:         bool = True
    created_at:     Optional[str] = None

    def to_public_dict(self) -> dict:
        """
        Return safe public representation.
        PROOF: key_hash and signing_secret are NOT included in public API responses.
        """
        return {
            "consumer_id":   self.consumer_id,
            "name":          self.name,
            "endpoint_url":  self.endpoint_url,
            "event_types":   sorted(self.scope.event_types),
            "active":        self.active,
            "created_at":    self.created_at,
        }


def generate_consumer_registration(
    name: str,
    endpoint_url: str,
    event_types: Optional[set[str]] = None,
) -> tuple[RegisteredConsumer, str]:
    """
    Create a new consumer registration with a fresh API key and signing secret.

    Returns:
        (consumer, plaintext_api_key)
        consumer:          RegisteredConsumer — store this in DB
        plaintext_api_key: show to consumer once — never store or log
    """
    import uuid
    import datetime

    plaintext_key, key_hash = generate_api_key()
    signing_secret = secrets.token_hex(32)   # 64-char hex HMAC secret
    scope = ConsumerScope(event_types=event_types or set(EventType._ALL))

    consumer = RegisteredConsumer(
        consumer_id    = str(uuid.uuid4()),
        name           = name,
        endpoint_url   = endpoint_url,
        key_hash       = key_hash,
        signing_secret = signing_secret,
        scope          = scope,
        created_at     = datetime.datetime.utcnow().isoformat(),
    )
    return consumer, plaintext_key


# ---------------------------------------------------------------------------
# Signature verification helper (for consumer-side use)
# ---------------------------------------------------------------------------

def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,   # "sha256=<hex>"
    signing_secret: str,
) -> bool:
    """
    Verify the HMAC-SHA256 signature on an incoming webhook payload.

    For use by webhook consumers to verify Aurora-signed payloads.

    RULE 3: operates on raw payload bytes only. Does not deserialise,
    inspect, or act on scientific field values within the payload.

    Args:
        payload_bytes:     Raw request body bytes
        signature_header:  X-Aurora-Signature header value ("sha256=<hex>")
        signing_secret:    The secret shared at registration

    Returns:
        True if signature is valid
    """
    if not signature_header.startswith("sha256="):
        return False
    received_sig = signature_header[len("sha256="):]
    expected_sig = hmac.new(
        signing_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(received_sig, expected_sig)