from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.models.tasks import TaskInfo, TaskStatus, utc_now


class TaskRepository:
    """Small SQLite repository for task metadata and restart recovery."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, task: TaskInfo) -> None:
        payload = task.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO tasks(task_id, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (task.task_id, payload, utc_now().isoformat()),
            )

    def load(self) -> list[TaskInfo]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT payload FROM tasks ORDER BY updated_at DESC").fetchall()
        return [TaskInfo.model_validate_json(row[0]) for row in rows]

    def recover_interrupted(self) -> list[TaskInfo]:
        tasks = self.load()
        active = {
            TaskStatus.CREATED,
            TaskStatus.STARTING,
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOPPING,
        }
        for task in tasks:
            if task.status in active:
                task.status = TaskStatus.FAULTED
                task.phase = "fault"
                task.message = "Backend restarted while this task was active; verify hardware manually"
                task.end_time = utc_now()
                self.save(task)
        return tasks

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection
