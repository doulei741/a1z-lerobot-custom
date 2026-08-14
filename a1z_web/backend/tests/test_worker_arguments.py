from __future__ import annotations

import sys
from pathlib import Path

WORKERS = Path(__file__).resolve().parents[1] / "app" / "workers"
sys.path.insert(0, str(WORKERS))

from teleoperation import build_command  # noqa: E402


def test_teleoperation_worker_forwards_optional_runtime_and_rerun_flags() -> None:
    command = build_command({
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
    })

    assert "--robot.gripper_start_hold=false" in command
    assert "--display_compressed_images=true" in command
    assert "--teleop_time_s=12" in command
