from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from app.models.tasks import EventEnvelope


class EventBus:
    def __init__(self, max_events: int = 5000) -> None:
        self._seq = 0
        self._events: deque[EventEnvelope] = deque(maxlen=max_events)
        self._subscribers: set[asyncio.Queue[EventEnvelope]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, data: dict[str, Any], task_id: str | None = None) -> EventEnvelope:
        async with self._lock:
            self._seq += 1
            event = EventEnvelope(seq=self._seq, task_id=task_id, type=event_type, data=data)
            self._events.append(event)
            for queue in tuple(self._subscribers):
                if not queue.full():
                    queue.put_nowait(event)
            return event

    async def subscribe(self, after: int = 0) -> asyncio.Queue[EventEnvelope]:
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            for event in self._events:
                if event.seq > after:
                    queue.put_nowait(event)
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[EventEnvelope]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)
