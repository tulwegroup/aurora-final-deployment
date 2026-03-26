"""
Aurora OSI vNext — Task Queue Management
Phase L §L.2

Manages async scan job dispatch.
Production implementation uses SQS FIFO queue (Phase M infrastructure).
Development/test implementation uses an in-memory queue.

LAYER RULE: Task queue sits in the pipeline layer (Layer 3).
  Does NOT import from api/ or storage/ directly.
  Accepts storage interactions via injected callables.

CONSTITUTIONAL: Task queue carries ONLY scan_id and job_id.
  No score fields, no threshold data, no component scores transit this queue.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol


# ---------------------------------------------------------------------------
# Queue item — minimal: scan_id + job_id only
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QueueItem:
    scan_id: str
    scan_job_id: str
    enqueued_at: str
    priority: int = 0    # Higher = more urgent (PREMIUM > SMART > BOOTSTRAP)


# ---------------------------------------------------------------------------
# Queue adapter protocol (injected; SQS in production)
# ---------------------------------------------------------------------------

class QueueAdapter(Protocol):
    def enqueue(self, item: QueueItem) -> None: ...
    def dequeue(self) -> Optional[QueueItem]: ...
    def size(self) -> int: ...


# ---------------------------------------------------------------------------
# In-memory queue (development / testing)
# ---------------------------------------------------------------------------

class InMemoryQueue:
    """Thread-unsafe in-memory queue for testing and single-process dev."""

    def __init__(self) -> None:
        self._queue: deque[QueueItem] = deque()

    def enqueue(self, item: QueueItem) -> None:
        # Higher priority at front
        items = list(self._queue)
        insert_at = len(items)
        for i, existing in enumerate(items):
            if item.priority > existing.priority:
                insert_at = i
                break
        items.insert(insert_at, item)
        self._queue = deque(items)

    def dequeue(self) -> Optional[QueueItem]:
        return self._queue.popleft() if self._queue else None

    def size(self) -> int:
        return len(self._queue)


# ---------------------------------------------------------------------------
# Queue manager — public API
# ---------------------------------------------------------------------------

def enqueue_scan(
    scan_id: str,
    queue: QueueAdapter,
    priority: int = 0,
) -> str:
    """
    Submit a scan to the execution queue.

    Args:
        scan_id:  Canonical scan identifier.
        queue:    Injected QueueAdapter.
        priority: 0 = BOOTSTRAP, 1 = SMART, 2 = PREMIUM.

    Returns:
        scan_job_id (UUID string).
    """
    scan_job_id = str(uuid.uuid4())
    item = QueueItem(
        scan_id=scan_id,
        scan_job_id=scan_job_id,
        enqueued_at=datetime.now(timezone.utc).isoformat(),
        priority=priority,
    )
    queue.enqueue(item)
    return scan_job_id


def dequeue_scan(queue: QueueAdapter) -> Optional[QueueItem]:
    """
    Pull the next scan job from the queue.
    Returns None if the queue is empty.
    """
    return queue.dequeue()


def scan_tier_to_priority(scan_tier: str) -> int:
    """Map scan tier string to integer queue priority."""
    return {"BOOTSTRAP": 0, "SMART": 1, "PREMIUM": 2}.get(scan_tier, 0)