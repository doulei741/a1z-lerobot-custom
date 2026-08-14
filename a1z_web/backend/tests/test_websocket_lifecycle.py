from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.api.routes import websocket_events
from app.services.event_bus import EventBus


class DisconnectingWebSocket:
    def __init__(self, events: EventBus) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(services=SimpleNamespace(events=events)))
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self) -> dict[str, str]:
        return {"type": "websocket.disconnect"}

    async def send_json(self, _payload: object) -> None:
        raise AssertionError("No event should be sent after the client disconnects")


@pytest.mark.asyncio
async def test_idle_websocket_disconnects_without_waiting_for_an_event() -> None:
    events = EventBus()
    websocket = DisconnectingWebSocket(events)

    await asyncio.wait_for(websocket_events(websocket, 0), timeout=0.2)  # type: ignore[arg-type]

    assert websocket.accepted is True
    assert not events._subscribers
