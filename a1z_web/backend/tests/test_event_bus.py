import pytest

from app.services.event_bus import EventBus


@pytest.mark.asyncio
async def test_reconnect_replays_only_events_after_last_sequence():
    bus = EventBus()
    first = await bus.publish("log", {"message": "one"}, "task-1")
    second = await bus.publish("health", {"can0": "healthy"}, "task-1")
    queue = await bus.subscribe(after=first.seq)
    replayed = await queue.get()
    assert replayed.seq == second.seq
    assert queue.empty()
    await bus.unsubscribe(queue)
