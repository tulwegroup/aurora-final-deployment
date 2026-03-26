"""
Aurora OSI vNext — Async Event Bus & Webhook Dispatcher
Phase V §V.1

Provides:
  - EventBus: in-process async publish/subscribe for domain events
  - WebhookDispatcher: HTTP delivery of canonical event payloads to registered endpoints
  - Retry logic: exponential backoff, max 5 attempts, payload bytes immutable across retries

DOMAIN EVENTS:
  scan.completed    — emitted after canonical freeze; payload is verbatim CanonicalScan summary
  scan.failed       — emitted when pipeline stage raises unrecoverable error
  twin.built        — emitted after twin voxels are written to storage
  scan.reprocessing — emitted when reprocess is triggered

CONSTITUTIONAL RULES — Phase V:
  Rule 1: Webhook payloads are assembled from PayloadSchema objects defined in
          payload_schemas.py. PayloadSchema fields map VERBATIM from the
          frozen CanonicalScan record. No field is derived, normalised, or computed.
  Rule 2: Retry logic re-sends the SAME serialised payload bytes (stored at first
          delivery attempt). The payload is NEVER recomputed on retry.
          This ensures byte-stability: the same bytes are delivered regardless of
          how many retry attempts occur.
  Rule 3: HMAC-SHA256 signature is computed over the stored payload bytes.
          Scientific field values are not used as signing inputs separate from
          the full payload — the signature covers the full serialised JSON body.
  Rule 4: No import from core/*.
  Rule 5: EventBus subscribers are infrastructure callbacks (telemetry, cache
          invalidation, webhook dispatch). They must never call scientific functions.
          Subscriber validation is enforced by naming convention check at registration.
  Rule 6: scan.completed payload includes display_acif_score VERBATIM from the
          frozen canonical record. It does not recompute, re-normalise, or re-tier.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from app.config.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Event types — domain event name registry
# ---------------------------------------------------------------------------

class EventType:
    SCAN_COMPLETED    = "scan.completed"
    SCAN_FAILED       = "scan.failed"
    TWIN_BUILT        = "twin.built"
    SCAN_REPROCESSING = "scan.reprocessing"

    _ALL = {SCAN_COMPLETED, SCAN_FAILED, TWIN_BUILT, SCAN_REPROCESSING}

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        return event_type in cls._ALL


# ---------------------------------------------------------------------------
# Domain event envelope
# ---------------------------------------------------------------------------

@dataclass
class DomainEvent:
    """
    Immutable envelope wrapping a domain event payload.

    event_id:   UUID string — unique per emission, used for idempotency
    event_type: string from EventType registry
    occurred_at: Unix timestamp (float) — wall-clock time of emission
    payload:    dict — verbatim canonical fields (see payload_schemas.py)

    PROOF: payload is assembled by the caller from a PayloadSchema — this class
    does not transform any field. It wraps and seals the payload.
    """
    event_id:    str
    event_type:  str
    occurred_at: float
    payload:     dict[str, Any]
    _serialised: Optional[bytes] = field(default=None, repr=False)

    def serialise(self) -> bytes:
        """
        Serialise to canonical JSON bytes.
        Called once at emission — stored bytes reused for retries (Rule 2).

        sort_keys=True: deterministic byte output — same event always produces
        the same bytes regardless of dict insertion order.
        """
        if self._serialised is None:
            envelope = {
                "event_id":    self.event_id,
                "event_type":  self.event_type,
                "occurred_at": self.occurred_at,
                "payload":     self.payload,
            }
            object.__setattr__(
                self, "_serialised",
                json.dumps(envelope, default=str, sort_keys=True).encode("utf-8"),
            )
        return self._serialised

    def hmac_signature(self, secret: str) -> str:
        """
        HMAC-SHA256 over the full serialised payload bytes.
        secret is a webhook endpoint secret (infrastructure credential).
        PROOF: signs the full byte string — no scientific field used as a
        separate signing input.
        """
        return hmac.new(
            secret.encode("utf-8"),
            self.serialise(),
            hashlib.sha256,
        ).hexdigest()


# ---------------------------------------------------------------------------
# In-process event bus
# ---------------------------------------------------------------------------

AsyncHandler = Callable[[DomainEvent], Coroutine]

# Subscriber naming convention — permitted prefixes (Rule 5)
_PERMITTED_SUBSCRIBER_PREFIXES = (
    "on_",         # event handler functions
    "handle_",     # event handler functions
    "dispatch_",   # webhook dispatch
    "invalidate_", # cache invalidation
    "record_",     # telemetry recording
    "notify_",     # notification dispatch
)


class EventBus:
    """
    In-process async publish/subscribe event bus.

    Subscribers are registered per event_type. On publish(), all subscribers
    are invoked concurrently via asyncio.gather().

    PROOF: EventBus is a routing mechanism only. It does not inspect payload
    field values, compute derived values, or call scientific functions.
    Subscribers are infrastructure callbacks — validated by naming convention.
    """

    def __init__(self):
        self._subscribers: dict[str, list[AsyncHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: AsyncHandler) -> None:
        """
        Register a handler for an event type.

        handler name must start with a permitted prefix (Rule 5).
        This convention prevents accidental registration of scientific functions.
        """
        if not EventType.is_valid(event_type):
            raise ValueError(f"Unknown event type: {event_type!r}")
        name = getattr(handler, "__name__", "")
        if not any(name.startswith(p) for p in _PERMITTED_SUBSCRIBER_PREFIXES):
            raise ValueError(
                f"Handler '{name}' does not match permitted naming convention "
                f"(must start with one of {_PERMITTED_SUBSCRIBER_PREFIXES}). "
                f"Subscribers must be infrastructure callbacks, not scientific functions."
            )
        self._subscribers[event_type].append(handler)
        logger.info("event_bus_subscribe", extra={"event_type": event_type, "handler": name})

    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to all registered subscribers concurrently.
        Subscriber errors are logged but do not prevent other subscribers from running.
        """
        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            logger.info("event_bus_no_subscribers", extra={"event_type": event.event_type})
            return

        async def _safe_call(handler: AsyncHandler) -> None:
            try:
                await handler(event)
            except Exception as e:
                logger.info(
                    "event_bus_subscriber_error",
                    extra={
                        "event_type": event.event_type,
                        "handler":    handler.__name__,
                        "error":      str(e),
                    },
                )

        await asyncio.gather(*[_safe_call(h) for h in handlers])
        logger.info(
            "event_bus_published",
            extra={
                "event_id":    event.event_id,
                "event_type":  event.event_type,
                "subscribers": len(handlers),
            },
        )


# ---------------------------------------------------------------------------
# Webhook registration record
# ---------------------------------------------------------------------------

@dataclass
class WebhookEndpoint:
    """
    A registered external webhook endpoint.

    endpoint_id:  unique identifier
    url:          HTTPS URL to deliver events to
    secret:       HMAC secret for payload signing
    event_types:  set of EventType strings this endpoint subscribes to
    active:       whether delivery should be attempted
    """
    endpoint_id:  str
    url:          str
    secret:       str
    event_types:  set[str]
    active:       bool = True


# ---------------------------------------------------------------------------
# Webhook dispatcher
# ---------------------------------------------------------------------------

# Retry configuration — infrastructure constants (not scientific)
MAX_RETRY_ATTEMPTS = 5
RETRY_BASE_DELAY_S = 1.0    # seconds — first retry delay
RETRY_MAX_DELAY_S  = 60.0   # seconds — cap on backoff


class WebhookDispatcher:
    """
    Delivers DomainEvent payloads to registered external endpoints via HTTP POST.

    RULE 2 (byte-stability across retries):
      serialised_bytes = event.serialise()  ← called ONCE before first attempt
      All retry attempts send the IDENTICAL bytes.
      The payload is never re-serialised, re-assembled, or recomputed on retry.

    RULE 3 (HMAC):
      signature = hmac.new(secret, serialised_bytes, sha256).hexdigest()
      Sent as X-Aurora-Signature header.
      Scientific field values are not used as separate signing inputs.
    """

    def __init__(self, http_session=None):
        """
        Args:
            http_session: aiohttp.ClientSession (injected).
                          If None, creates one on first use.
        """
        self._session = http_session
        self._endpoints: dict[str, WebhookEndpoint] = {}

    def register(self, endpoint: WebhookEndpoint) -> None:
        self._endpoints[endpoint.endpoint_id] = endpoint
        logger.info(
            "webhook_registered",
            extra={
                "endpoint_id": endpoint.endpoint_id,
                "event_types": list(endpoint.event_types),
            },
        )

    def deregister(self, endpoint_id: str) -> None:
        self._endpoints.pop(endpoint_id, None)

    async def dispatch(self, event: DomainEvent) -> None:
        """
        Dispatch a DomainEvent to all matching active endpoints.

        Serialises the event ONCE (Rule 2), then delivers to all matching
        endpoints. Each delivery runs independently with its own retry loop.
        """
        # Serialise once — all deliveries share these bytes (Rule 2)
        payload_bytes = event.serialise()

        targets = [
            ep for ep in self._endpoints.values()
            if ep.active and event.event_type in ep.event_types
        ]

        if not targets:
            return

        await asyncio.gather(*[
            self._deliver_with_retry(event, ep, payload_bytes)
            for ep in targets
        ])

    async def _deliver_with_retry(
        self,
        event: DomainEvent,
        endpoint: WebhookEndpoint,
        payload_bytes: bytes,   # RULE 2: same bytes for every attempt
    ) -> None:
        """
        Deliver payload_bytes to endpoint.url with exponential backoff retry.

        payload_bytes is the caller-provided immutable bytes — not recomputed here.
        """
        signature = event.hmac_signature(endpoint.secret)
        headers = {
            "Content-Type":      "application/json",
            "X-Aurora-Signature": f"sha256={signature}",
            "X-Aurora-Event":    event.event_type,
            "X-Aurora-EventID":  event.event_id,
        }

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                session = await self._get_session()
                async with session.post(
                    endpoint.url,
                    data=payload_bytes,     # RULE 2: immutable bytes, every attempt
                    headers=headers,
                    timeout=10,
                ) as resp:
                    if resp.status < 300:
                        logger.info(
                            "webhook_delivered",
                            extra={
                                "endpoint_id": endpoint.endpoint_id,
                                "event_id":    event.event_id,
                                "status":      resp.status,
                                "attempt":     attempt,
                            },
                        )
                        return
                    else:
                        logger.info(
                            "webhook_delivery_failed",
                            extra={
                                "endpoint_id": endpoint.endpoint_id,
                                "event_id":    event.event_id,
                                "status":      resp.status,
                                "attempt":     attempt,
                            },
                        )
            except Exception as e:
                logger.info(
                    "webhook_delivery_error",
                    extra={
                        "endpoint_id": endpoint.endpoint_id,
                        "event_id":    event.event_id,
                        "error":       str(e),
                        "attempt":     attempt,
                    },
                )

            if attempt < MAX_RETRY_ATTEMPTS:
                # Exponential backoff — infrastructure timing, not scientific
                delay = min(RETRY_BASE_DELAY_S * (2 ** (attempt - 1)), RETRY_MAX_DELAY_S)
                await asyncio.sleep(delay)

        logger.info(
            "webhook_delivery_exhausted",
            extra={"endpoint_id": endpoint.endpoint_id, "event_id": event.event_id},
        )

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()


# ---------------------------------------------------------------------------
# Module-level singleton EventBus
# ---------------------------------------------------------------------------

_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus