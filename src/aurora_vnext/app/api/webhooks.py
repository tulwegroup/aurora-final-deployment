"""
Aurora OSI vNext — Webhook Consumer Management API
Phase W §W.2

REST endpoints for webhook consumer registration and management.

Endpoints:
  POST   /api/v1/webhooks/consumers         — register new consumer
  GET    /api/v1/webhooks/consumers         — list consumers (admin only)
  GET    /api/v1/webhooks/consumers/{id}    — get consumer (admin only)
  PATCH  /api/v1/webhooks/consumers/{id}    — update endpoint/scope/active
  DELETE /api/v1/webhooks/consumers/{id}    — deregister consumer
  POST   /api/v1/webhooks/consumers/{id}/rotate-key  — rotate API key

CONSTITUTIONAL RULES — Phase W:
  Rule 1: Request and response bodies contain only infrastructure metadata.
          No scientific field (ACIF, tier, score) is accepted or returned.
  Rule 2: Scope filtering is by event_type string only. Requests that attempt
          to include `filter_by_tier`, `min_acif_score`, or any scientific
          filter field are rejected with HTTP 422.
  Rule 3: No import from core/*.
  Rule 4: Plaintext API key is returned ONLY in the registration response
          and key-rotation response. It is never logged.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl, validator

from app.events.consumer_auth import (
    ConsumerScope,
    RegisteredConsumer,
    generate_api_key,
    generate_consumer_registration,
    hash_api_key,
    verify_api_key,
)
from app.events.event_bus import EventType
from app.config.observability import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RegisterConsumerRequest(BaseModel):
    """
    RULE 1: Only infrastructure fields accepted.
    RULE 2: event_types must be EventType strings only — validated below.
    Forbidden fields: filter_by_tier, min_acif_score, max_acif_score,
                      tier_filter, score_threshold — any such field is rejected.
    """
    name:         str
    endpoint_url: HttpUrl
    event_types:  Optional[list[str]] = None   # None = subscribe to all

    @validator("name")
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Consumer name must not be empty")
        return v.strip()

    @validator("event_types", each_item=True, pre=True)
    def validate_event_type(cls, v):
        if not EventType.is_valid(v):
            raise ValueError(
                f"Unknown event type: {v!r}. "
                f"Permitted: {sorted(EventType._ALL)}"
            )
        return v

    class Config:
        # Reject any extra fields — RULE 2: no scientific filter fields accepted
        extra = "forbid"


class UpdateConsumerRequest(BaseModel):
    endpoint_url: Optional[HttpUrl] = None
    event_types:  Optional[list[str]] = None
    active:       Optional[bool] = None

    @validator("event_types", each_item=True, pre=True)
    def validate_event_type(cls, v):
        if not EventType.is_valid(v):
            raise ValueError(f"Unknown event type: {v!r}")
        return v

    class Config:
        extra = "forbid"   # RULE 2: reject scientific filter fields


class ConsumerRegistrationResponse(BaseModel):
    """
    Registration response — includes plaintext API key (shown ONCE).
    signing_secret included so consumer can verify incoming payloads.
    No scientific fields.
    """
    consumer_id:   str
    name:          str
    endpoint_url:  str
    event_types:   list[str]
    active:        bool
    created_at:    Optional[str]
    api_key:       str    # plaintext — shown once, never stored
    signing_secret: str   # for consumer-side HMAC verification


class ConsumerPublicResponse(BaseModel):
    """Public consumer view — no secrets."""
    consumer_id:  str
    name:         str
    endpoint_url: str
    event_types:  list[str]
    active:       bool
    created_at:   Optional[str]


class KeyRotationResponse(BaseModel):
    consumer_id: str
    api_key:     str   # new plaintext key — shown once


# ---------------------------------------------------------------------------
# In-memory consumer store (replace with DB-backed store in production)
# ---------------------------------------------------------------------------

_consumer_store: dict[str, RegisteredConsumer] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/consumers", response_model=ConsumerRegistrationResponse, status_code=201)
async def register_consumer(request: RegisterConsumerRequest):
    """
    Register a new webhook consumer endpoint.

    Returns plaintext API key (shown ONCE) and signing secret.
    RULE 1: Response contains only infrastructure metadata.
    """
    event_types = set(request.event_types) if request.event_types else None
    consumer, plaintext_key = generate_consumer_registration(
        name          = request.name,
        endpoint_url  = str(request.endpoint_url),
        event_types   = event_types,
    )
    _consumer_store[consumer.consumer_id] = consumer
    logger.info(
        "webhook_consumer_registered",
        extra={"consumer_id": consumer.consumer_id, "name": consumer.name},
    )
    return ConsumerRegistrationResponse(
        consumer_id    = consumer.consumer_id,
        name           = consumer.name,
        endpoint_url   = consumer.endpoint_url,
        event_types    = sorted(consumer.scope.event_types),
        active         = consumer.active,
        created_at     = consumer.created_at,
        api_key        = plaintext_key,   # shown once
        signing_secret = consumer.signing_secret,
    )


@router.get("/consumers", response_model=list[ConsumerPublicResponse])
async def list_consumers():
    """List all registered consumers (admin only in production)."""
    return [
        ConsumerPublicResponse(**c.to_public_dict())
        for c in _consumer_store.values()
    ]


@router.get("/consumers/{consumer_id}", response_model=ConsumerPublicResponse)
async def get_consumer(consumer_id: str):
    """Get a single consumer by ID."""
    consumer = _consumer_store.get(consumer_id)
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    return ConsumerPublicResponse(**consumer.to_public_dict())


@router.patch("/consumers/{consumer_id}", response_model=ConsumerPublicResponse)
async def update_consumer(consumer_id: str, body: UpdateConsumerRequest):
    """
    Update consumer endpoint URL, event scope, or active status.
    RULE 2: event_types validated — no scientific filter fields accepted.
    """
    consumer = _consumer_store.get(consumer_id)
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")

    new_url    = str(body.endpoint_url) if body.endpoint_url else consumer.endpoint_url
    new_scope  = (ConsumerScope(event_types=set(body.event_types))
                  if body.event_types is not None else consumer.scope)
    new_active = body.active if body.active is not None else consumer.active

    from dataclasses import replace
    updated = replace(
        consumer,
        endpoint_url = new_url,
        scope        = new_scope,
        active       = new_active,
    )
    _consumer_store[consumer_id] = updated
    logger.info("webhook_consumer_updated", extra={"consumer_id": consumer_id})
    return ConsumerPublicResponse(**updated.to_public_dict())


@router.delete("/consumers/{consumer_id}", status_code=204)
async def deregister_consumer(consumer_id: str):
    """Remove a consumer registration and stop deliveries."""
    if consumer_id not in _consumer_store:
        raise HTTPException(status_code=404, detail="Consumer not found")
    del _consumer_store[consumer_id]
    logger.info("webhook_consumer_deregistered", extra={"consumer_id": consumer_id})


@router.post("/consumers/{consumer_id}/rotate-key", response_model=KeyRotationResponse)
async def rotate_api_key(consumer_id: str):
    """
    Rotate the API key for a consumer.
    Returns new plaintext key (shown ONCE).
    Old key is immediately invalidated.
    RULE 1: No scientific fields in request or response.
    """
    consumer = _consumer_store.get(consumer_id)
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")

    plaintext_key, new_hash = generate_api_key()
    from dataclasses import replace
    updated = replace(consumer, key_hash=new_hash)
    _consumer_store[consumer_id] = updated
    logger.info("webhook_key_rotated", extra={"consumer_id": consumer_id})
    return KeyRotationResponse(consumer_id=consumer_id, api_key=plaintext_key)