from pathlib import Path

from app.core.database import TaskRepository
from app.models.tasks import TaskInfo, TaskStatus, TaskType


def test_repository_marks_interrupted_motion_faulted(tmp_path: Path):
    repository = TaskRepository(tmp_path / "tasks.sqlite3")
    repository.save(
        TaskInfo(
            task_id="teleop-abcd1234",
            task_type=TaskType.TELEOPERATION,
            status=TaskStatus.RUNNING,
            cwd=str(tmp_path),
        )
    )
    recovered = repository.recover_interrupted()
    assert recovered[0].status is TaskStatus.FAULTED
    assert "verify hardware" in (recovered[0].message or "")
