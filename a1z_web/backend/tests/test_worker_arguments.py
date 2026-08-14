from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

WORKERS = Path(__file__).resolve().parents[1] / "app" / "workers"
sys.path.insert(0, str(WORKERS))

from teleoperation import build_command  # noqa: E402


def test_teleoperation_worker_forwards_optional_runtime_and_rerun_flags() -> None:
    command = build_command(
        {
            "mode": "dual",
            "left_can": "can0",
            "right_can": "can1",
            "left_leader_id": "left",
            "right_leader_id": "right",
            "left_leader_port": "/dev/ttyACM0",
            "right_leader_port": "/dev/ttyACM1",
            "left_mapping": {"signs": [-1] * 6, "scales": [1] * 6, "offsets_rad": [0] * 6},
            "right_mapping": {"signs": [-1] * 6, "scales": [1] * 6, "offsets_rad": [0] * 6},
            "cameras": {},
            "ema_alpha": 0.3,
            "max_joint_delta": 0.01,
            "gripper_start_hold": False,
            "return_home_on_disconnect": False,
            "open_grippers_on_disconnect": False,
            "fps": 30,
            "display_data": True,
            "display_compressed_images": True,
            "teleop_time_s": 12,
        }
    )

    assert "--robot.gripper_start_hold=false" in command
    assert "--teleop.left_arm_config.auto_use_calibration=true" in command
    assert "--teleop.right_arm_config.auto_use_calibration=true" in command
    assert "--display_compressed_images=true" in command
    assert "--teleop_time_s=12" in command


def test_recording_worker_initializes_and_shuts_down_rerun() -> None:
    source = (WORKERS / "recording.py").read_text(encoding="utf-8")

    assert 'init_rerun(session_name="recording")' in source
    assert "shutdown_rerun()" in source
    assert 'arm["auto_use_calibration"] = True' in source
    assert '"auto_use_calibration": True' in source


def test_recording_worker_reads_frame_count_from_dataset_writer() -> None:
    """Exercise only the dependency-free helper from the real worker source."""

    source = (WORKERS / "recording.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "buffer_frames"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace: dict[str, object] = {"Any": object}
    exec(compile(module, str(WORKERS / "recording.py"), "exec"), namespace)

    @dataclass
    class Writer:
        episode_buffer: dict[str, int]

    @dataclass
    class Dataset:
        writer: Writer | None

    count = namespace["buffer_frames"]
    assert callable(count)
    assert count(Dataset(writer=Writer(episode_buffer={"size": 37}))) == 37
    assert count(Dataset(writer=None)) == 0


def test_recording_worker_saves_video_without_forking_from_control_threads() -> None:
    """Video encoding must not fork a process already running hardware threads."""

    source = (WORKERS / "recording.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "save_episode_without_fork"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace: dict[str, object] = {"Any": object}
    exec(compile(module, str(WORKERS / "recording.py"), "exec"), namespace)

    class Dataset:
        parallel_encoding: bool | None = None

        def save_episode(self, *, parallel_encoding: bool = True) -> None:
            self.parallel_encoding = parallel_encoding

    dataset = Dataset()
    namespace["save_episode_without_fork"](dataset)

    assert dataset.parallel_encoding is False
    assert "save_episode_without_fork(dataset)" in source


def test_recording_worker_finishes_when_requested_episode_count_is_reached() -> None:
    source = (WORKERS / "recording.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session_is_complete"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace: dict[str, object] = {}
    exec(compile(module, str(WORKERS / "recording.py"), "exec"), namespace)

    complete = namespace["session_is_complete"]
    assert complete(initial_episodes=25, current_episodes=25, requested_additions=2) is False
    assert complete(initial_episodes=25, current_episodes=26, requested_additions=2) is False
    assert complete(initial_episodes=25, current_episodes=27, requested_additions=2) is True
    assert "if session_is_complete(" in source


def test_teleoperation_connects_existing_cli_to_task_rerun(monkeypatch) -> None:
    monkeypatch.setenv("A1Z_RERUN_WEB_PORT", "19090")
    monkeypatch.setenv("A1Z_RERUN_GRPC_PORT", "19876")
    command = build_command(
        {
            "mode": "single",
            "left_can": "can0",
            "left_leader_id": "left",
            "left_leader_port": "/dev/ttyACM0",
            "left_mapping": {"signs": [-1] * 6, "scales": [1] * 6, "offsets_rad": [0] * 6},
            "cameras": {"top_rgb": {"enabled": True, "serial": "TOP"}},
            "ema_alpha": 0.3,
            "max_joint_delta": 0.01,
            "gripper_start_hold": False,
            "return_home_on_disconnect": False,
            "fps": 30,
            "display_data": True,
            "display_compressed_images": True,
        }
    )

    assert "--display_ip=127.0.0.1" in command
    assert "--display_port=19876" in command
    assert "--teleop.auto_use_calibration=true" in command
