from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.database import TaskRepository
from app.models.tasks import TaskStatus, TaskType
from app.services.event_bus import EventBus
from app.services.hardware_manager import HardwareResourceManager
from app.services.task_manager import TaskManager


def manager(tmp_path: Path) -> TaskManager:
    settings = Settings(
        A1Z_PROJECT_ROOT=tmp_path,
        A1Z_WEB_DATA_DIR=tmp_path / "runtime",
        A1Z_WEB_MOCK=False,
        A1Z_WEB_ALLOW_HARDWARE=True,
        graceful_stop_timeout_s=1,
        term_timeout_s=1,
    )
    settings.prepare()
    return TaskManager(
        settings,
        HardwareResourceManager(),
        EventBus(),
        TaskRepository(settings.database_path),
    )


@pytest.mark.asyncio
async def test_process_group_gracefully_stops_and_releases_resource(tmp_path: Path):
    tasks = manager(tmp_path)
    script = (
        "import json,time; "
        "print('A1Z_EVENT '+json.dumps({'type':'ready','data':{'phase':'ready'}}),flush=True); "
        "time.sleep(30)"
    )
    info = await tasks.start(TaskType.TELEOPERATION, {"can0"}, argv=[sys.executable, "-u", "-c", script])
    for _ in range(100):
        if tasks.get(info.task_id).info.status is TaskStatus.READY:
            break
        await asyncio.sleep(0.01)
    await tasks.stop(info.task_id)
    for _ in range(100):
        if tasks.get(info.task_id).info.status in {TaskStatus.STOPPED, TaskStatus.FAILED}:
            break
        await asyncio.sleep(0.01)
    assert tasks.get(info.task_id).process.returncode is not None
    assert await tasks.hardware.snapshot() == {}


@pytest.mark.asyncio
async def test_immediate_child_crash_is_failed(tmp_path: Path):
    tasks = manager(tmp_path)
    info = await tasks.start(
        TaskType.INFERENCE,
        {"can0"},
        argv=[sys.executable, "-u", "-c", "raise RuntimeError('boom')"],
    )
    assert tasks.get(info.task_id).monitor is not None
    await tasks.get(info.task_id).monitor
    assert tasks.get(info.task_id).info.status is TaskStatus.FAILED
    assert await tasks.hardware.snapshot() == {}


@pytest.mark.asyncio
async def test_structured_fault_terminates_child_and_releases_hardware(tmp_path: Path):
    tasks = manager(tmp_path)
    script = (
        "import json,time; "
        "print('A1Z_EVENT '+json.dumps({'type':'fault','data':{'reason':'can1 Network is down'}}),flush=True); "
        "time.sleep(30)"
    )
    info = await tasks.start(TaskType.RECORDING, {"can1"}, argv=[sys.executable, "-u", "-c", script])
    assert tasks.get(info.task_id).monitor is not None
    await tasks.get(info.task_id).monitor
    assert tasks.get(info.task_id).info.status is TaskStatus.FAULTED
    assert tasks.get(info.task_id).process.returncode is not None
    assert await tasks.hardware.snapshot() == {}
