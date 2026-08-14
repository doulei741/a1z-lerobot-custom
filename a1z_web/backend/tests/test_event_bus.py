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


@pytest.mark.asyncio
async def test_reconnect_can_replay_more_than_one_thousand_buffered_events():
    bus = EventBus(max_events=1500)
    for index in range(1200):
        await bus.publish("log", {"message": str(index)}, "task-1")

    queue = await bus.subscribe(after=0)

    assert queue.qsize() == 1200
    assert (await queue.get()).seq == 1
    await bus.unsubscribe(queue)


@pytest.mark.asyncio
async def test_reconnect_resets_a_sequence_from_an_older_backend_process():
    bus = EventBus()
    first = await bus.publish("task", {"status": "running"}, "task-1")

    queue = await bus.subscribe(after=10_000)

    assert (await queue.get()).seq == first.seq
    await bus.unsubscribe(queue)
