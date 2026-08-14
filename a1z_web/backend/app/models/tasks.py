from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    CAMERA_PREVIEW = "camera_preview"
    CALIBRATION = "calibration"
    PAIRING = "pairing"
    TELEOPERATION = "teleoperation"
    RECORDING = "recording"
    INFERENCE = "inference"


class TaskStatus(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    FAULTED = "faulted"
    STOPPED = "stopped"


class RecordPhase(StrEnum):
    READY = "ready"
    RECORDING = "recording"
    SAVING = "saving"
    RESETTING = "resetting"
    FINISHED = "finished"
    FAULT = "fault"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAULT = "fault"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskInfo(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.CREATED
    phase: str = "created"
    pid: int | None = None
    argv: list[str] = Field(default_factory=list)
    cwd: str
    resources: list[str] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=utc_now)
    end_time: datetime | None = None
    exit_code: int | None = None
    health: dict[str, HealthState] = Field(default_factory=dict)
    message: str | None = None
    mock: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogEntry(BaseModel):
    seq: int
    timestamp: datetime = Field(default_factory=utc_now)
    level: str
    source: str
    task_id: str
    message: str


class EventEnvelope(BaseModel):
    seq: int
    task_id: str | None
    type: str
    timestamp: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)
