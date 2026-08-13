from __future__ import annotations

import asyncio
import json
import os
import signal
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.core.database import TaskRepository
from app.core.errors import ApiError
from app.models.tasks import LogEntry, TaskInfo, TaskStatus, TaskType, utc_now
from app.services.event_bus import EventBus
from app.services.hardware_manager import HardwareResourceManager

TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.FAULTED, TaskStatus.STOPPED}


@dataclass
class TaskRuntime:
    info: TaskInfo
    logs: deque[LogEntry]
    log_path: Path
    process: asyncio.subprocess.Process | None = None
    monitor: asyncio.Task[None] | None = None
    terminator: asyncio.Task[None] | None = None
    log_seq: int = 0
    record: Any = None
    calibration: Any = None
    command_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class TaskManager:
    """Owns task metadata, subprocess groups, durable logs, and graceful shutdown."""

    def __init__(self, settings: Settings, hardware: HardwareResourceManager, events: EventBus, repository: TaskRepository) -> None:
        self.settings = settings
        self.hardware = hardware
        self.events = events
        self.repository = repository
        self._tasks: dict[str, TaskRuntime] = {}
        self._lock = asyncio.Lock()
        for info in repository.load():
            assert settings.log_dir is not None
            self._tasks[info.task_id] = TaskRuntime(
                info=info,
                logs=deque(maxlen=settings.log_ring_size),
                log_path=settings.log_dir / f"{info.task_id}.jsonl",
            )

    async def start(
        self,
        task_type: TaskType,
        resources: set[str],
        *,
        argv: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskInfo:
        prefix = {
            TaskType.CALIBRATION: "calibrate",
            TaskType.PAIRING: "pair",
            TaskType.TELEOPERATION: "teleop",
            TaskType.RECORDING: "record",
            TaskType.INFERENCE: "inference",
        }[task_type]
        task_id = f"{prefix}-{uuid4().hex[:8]}"
        await self.hardware.acquire(task_id, resources)
        info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.STARTING,
            phase="starting",
            argv=argv or [],
            cwd=str(self.settings.project_root),
            resources=sorted(resources),
            mock=self.settings.mock,
            metadata=metadata or {},
        )
        assert self.settings.log_dir is not None
        runtime = TaskRuntime(
            info=info,
            logs=deque(maxlen=self.settings.log_ring_size),
            log_path=self.settings.log_dir / f"{task_id}.jsonl",
        )
        async with self._lock:
            self._tasks[task_id] = runtime
        self.repository.save(info)
        await self.log(task_id, "INFO", "task_manager", f"Starting {task_type.value} task")
        await self.events.publish("task", info.model_dump(mode="json"), task_id)

        try:
            if self.settings.mock:
                runtime.monitor = asyncio.create_task(self._mock_ready(runtime))
            else:
                if not self.settings.allow_hardware:
                    raise ApiError(
                        "hardware_motion_disabled",
                        "Real hardware tasks require A1Z_WEB_ALLOW_HARDWARE=1",
                        status_code=403,
                        recoverable=True,
                    )
                if not argv:
                    raise ApiError("missing_command", "No worker command was provided")
                runtime.process = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=self.settings.project_root,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    start_new_session=True,
                    env={**os.environ, "A1Z_WEB_EVENTS": "1"},
                )
                info.pid = runtime.process.pid
                runtime.monitor = asyncio.create_task(self._monitor_process(runtime))
        except Exception:
            await self.hardware.release(task_id)
            async with self._lock:
                self._tasks.pop(task_id, None)
            raise
        return info

    async def _mock_ready(self, runtime: TaskRuntime) -> None:
        await asyncio.sleep(0.02)
        if runtime.info.status is TaskStatus.STARTING:
            runtime.info.status = TaskStatus.READY
            runtime.info.phase = "ready"
            from app.models.tasks import HealthState

            runtime.info.health = {resource: HealthState.HEALTHY for resource in runtime.info.resources}
            await self.log(runtime.info.task_id, "INFO", "mock", "MOCK workflow ready; no hardware opened")
            await self.events.publish("task", runtime.info.model_dump(mode="json"), runtime.info.task_id)
            self.repository.save(runtime.info)

    async def _monitor_process(self, runtime: TaskRuntime) -> None:
        assert runtime.process is not None and runtime.process.stdout is not None
        while line := await runtime.process.stdout.readline():
            text = line.decode(errors="replace").rstrip()
            if text.startswith("A1Z_EVENT "):
                await self._handle_structured(runtime, text.removeprefix("A1Z_EVENT "))
            else:
                level = "ERROR" if "ERROR" in text or "Traceback" in text else "WARN" if "WARNING" in text else "INFO"
                await self.log(runtime.info.task_id, level, "worker", text)
        exit_code = await runtime.process.wait()
        runtime.info.exit_code = exit_code
        runtime.info.end_time = utc_now()
        if runtime.info.status is TaskStatus.STOPPING:
            runtime.info.status = TaskStatus.STOPPED
        elif runtime.info.status not in TERMINAL:
            runtime.info.status = TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
        runtime.info.phase = runtime.info.status.value
        self.repository.save(runtime.info)
        await self.hardware.release(runtime.info.task_id)
        await self.events.publish("task", runtime.info.model_dump(mode="json"), runtime.info.task_id)

    async def _handle_structured(self, runtime: TaskRuntime, payload: str) -> None:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            await self.log(runtime.info.task_id, "WARN", "event_parser", payload)
            return
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        if event_type == "ready":
            runtime.info.status = TaskStatus.READY
            runtime.info.phase = data.get("phase", "ready")
            from app.models.tasks import HealthState

            runtime.info.health = {
                resource: HealthState.HEALTHY for resource in runtime.info.resources
            }
        elif event_type == "phase":
            runtime.info.phase = data.get("phase", runtime.info.phase)
        elif event_type == "health":
            runtime.info.health.update(data)
        elif event_type == "record_frame" and runtime.record is not None:
            if runtime.record.frames == 0:
                runtime.record.note_frame()
        elif event_type == "saving_complete" and runtime.record is not None:
            runtime.record.apply_system("saving_complete")
        elif event_type == "calibration_ranges" and runtime.calibration is not None:
            runtime.calibration.ranges = data.get("ranges", runtime.calibration.ranges)
        elif event_type == "calibration_saved" and runtime.calibration is not None:
            runtime.calibration.phase = "completed"
            runtime.calibration.calibration_status = "saved"
            runtime.info.status = TaskStatus.COMPLETED
            runtime.info.phase = "completed"
        elif event_type == "pairing_read":
            runtime.info.metadata["pairing_result"] = data
        elif event_type == "fault":
            runtime.info.status = TaskStatus.FAULTED
            runtime.info.phase = "fault"
            runtime.info.message = data.get("reason", "Worker reported a fault")
            from app.models.tasks import HealthState

            reason = runtime.info.message.lower()
            for resource in runtime.info.resources:
                if resource in reason or (resource.startswith("can") and "network is down" in reason):
                    runtime.info.health[resource] = HealthState.FAULT
            if runtime.record is not None:
                runtime.record.fault(runtime.info.message)
            if runtime.process is not None and runtime.process.returncode is None:
                if runtime.terminator is None:
                    runtime.terminator = asyncio.create_task(self._terminate_faulted_process(runtime))
        await self.events.publish(event_type, data, runtime.info.task_id)
        self.repository.save(runtime.info)
        await self.log(runtime.info.task_id, "INFO", "a1z_event", json.dumps(event, ensure_ascii=False))

    async def _terminate_faulted_process(self, runtime: TaskRuntime) -> None:
        """Faults are terminal: stop frame collection and unwind the A1Z finally blocks."""
        assert runtime.process is not None
        await self.log(runtime.info.task_id, "ERROR", "task_manager", "Fault propagated; initiating safe process shutdown")
        await self._signal_and_wait(runtime, signal.SIGINT, self.settings.graceful_stop_timeout_s)
        if runtime.process.returncode is None:
            await self._signal_and_wait(runtime, signal.SIGTERM, self.settings.term_timeout_s)
        if runtime.process.returncode is None:
            os.killpg(runtime.process.pid, signal.SIGKILL)
            await runtime.process.wait()

    async def log(self, task_id: str, level: str, source: str, message: str) -> LogEntry:
        runtime = self._require(task_id)
        runtime.log_seq += 1
        entry = LogEntry(seq=runtime.log_seq, level=level, source=source, task_id=task_id, message=message)
        runtime.logs.append(entry)
        with runtime.log_path.open("a", encoding="utf-8") as stream:
            stream.write(entry.model_dump_json() + "\n")
        await self.events.publish("log", entry.model_dump(mode="json"), task_id)
        return entry

    def get(self, task_id: str) -> TaskRuntime:
        return self._require(task_id)

    def list(self) -> list[TaskInfo]:
        return sorted((runtime.info for runtime in self._tasks.values()), key=lambda item: item.start_time, reverse=True)

    def logs_after(self, task_id: str, after: int) -> list[LogEntry]:
        runtime = self._require(task_id)
        if runtime.logs and after >= runtime.logs[0].seq - 1:
            return [entry for entry in runtime.logs if entry.seq > after]
        entries: list[LogEntry] = []
        if runtime.log_path.exists():
            with runtime.log_path.open(encoding="utf-8") as stream:
                for line in stream:
                    entry = LogEntry.model_validate_json(line)
                    if entry.seq > after:
                        entries.append(entry)
        return entries

    async def send_command(self, task_id: str, payload: dict[str, Any]) -> None:
        runtime = self._require(task_id)
        if runtime.info.mock:
            return
        if runtime.process is None or runtime.process.stdin is None or runtime.process.returncode is not None:
            raise ApiError("task_not_running", "Task command channel is unavailable", status_code=409)
        runtime.process.stdin.write((json.dumps(payload) + "\n").encode())
        await runtime.process.stdin.drain()

    async def stop(self, task_id: str, reason: str = "operator_requested") -> TaskInfo:
        runtime = self._require(task_id)
        async with runtime.command_lock:
            if runtime.info.status in TERMINAL:
                return runtime.info
            runtime.info.status = TaskStatus.STOPPING
            runtime.info.phase = "stopping"
            await self.log(task_id, "WARN", "task_manager", f"Safe stop requested: {reason}")
            await self.events.publish("task", runtime.info.model_dump(mode="json"), task_id)
            self.repository.save(runtime.info)
            if runtime.info.mock:
                runtime.info.status = TaskStatus.STOPPED
                runtime.info.phase = "stopped"
                runtime.info.end_time = utc_now()
                self.repository.save(runtime.info)
                await self.hardware.release(task_id)
                await self.events.publish("task", runtime.info.model_dump(mode="json"), task_id)
                return runtime.info

            assert runtime.process is not None
            await self._signal_and_wait(runtime, signal.SIGINT, self.settings.graceful_stop_timeout_s)
            if runtime.process.returncode is None:
                await self._signal_and_wait(runtime, signal.SIGTERM, self.settings.term_timeout_s)
            if runtime.process.returncode is None:
                os.killpg(runtime.process.pid, signal.SIGKILL)
                await runtime.process.wait()
                await self.log(task_id, "ERROR", "task_manager", "Worker required final SIGKILL escalation")
            return runtime.info

    async def complete_mock(self, task_id: str, phase: str = "completed") -> TaskInfo:
        """Finish a finite mock workflow and release its simulated resources."""
        runtime = self._require(task_id)
        if not runtime.info.mock:
            raise ApiError("mock_only", "Only mock workflows can be completed by the backend")
        if runtime.monitor is not None:
            runtime.monitor.cancel()
        runtime.info.status = TaskStatus.COMPLETED
        runtime.info.phase = phase
        runtime.info.end_time = utc_now()
        self.repository.save(runtime.info)
        await self.hardware.release(task_id)
        await self.events.publish("task", runtime.info.model_dump(mode="json"), task_id)
        return runtime.info

    async def _signal_and_wait(self, runtime: TaskRuntime, sig: signal.Signals, wait_seconds: float) -> None:
        assert runtime.process is not None
        os.killpg(runtime.process.pid, sig)
        try:
            await asyncio.wait_for(runtime.process.wait(), wait_seconds)
        except TimeoutError:
            await self.log(runtime.info.task_id, "WARN", "task_manager", f"No exit after {sig.name}")

    async def shutdown(self) -> None:
        for runtime in tuple(self._tasks.values()):
            if runtime.terminator is not None:
                await runtime.terminator
            elif runtime.info.status not in TERMINAL:
                await self.stop(runtime.info.task_id, "backend_shutdown")

    def _require(self, task_id: str) -> TaskRuntime:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ApiError("task_not_found", f"Unknown task: {task_id}", status_code=404) from exc
