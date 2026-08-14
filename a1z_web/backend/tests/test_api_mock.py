from __future__ import annotations

import time
from unittest.mock import AsyncMock

from app.models.tasks import TaskStatus


def wait_ready(client, task_id: str) -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        payload = client.get(f"/api/tasks/{task_id}").json()
        if payload["status"] in {"ready", "running"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("mock task did not become ready")


def test_preflight_discloses_mock_mode_and_is_authoritative_for_start(client):
    response = client.post("/api/teleop/preflight", json={"mode": "dual"})
    assert response.status_code == 200
    assert response.json()["simulation"] is True
    assert response.json()["issues"][0]["code"] == "mock_simulation"

    blocked_report = {
        "ready": False,
        "simulation": False,
        "workflow": "teleoperation",
        "mode": "real",
        "issues": [{
            "code": "can_missing",
            "resource": "can0",
            "title": "can0 不存在",
            "message": "missing",
            "action": "setup can0",
            "severity": "blocking",
        }],
        "inventory": {},
    }
    client.app.state.services.preflight.inspect = AsyncMock(return_value=blocked_report)
    blocked = client.post("/api/teleop/start", json={"mode": "dual", "safety_confirmed": True})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "hardware_preflight_failed"
    assert blocked.json()["error"]["details"]["issues"][0]["resource"] == "can0"


def test_mock_teleop_hardware_lock_and_idempotent_stop(client):
    response = client.post("/api/teleop/start", json={"mode": "dual", "safety_confirmed": True})
    assert response.status_code == 201
    task = wait_ready(client, response.json()["task_id"])
    assert task["mock"] is True

    conflict = client.post("/api/inference/start", json={
        "mode": "dual",
        "policy_path": "outputs/mock-model",
        "compatibility_token": "mock-compatible",
        "safety_confirmed": True,
    })
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "hardware_resource_busy"

    first = client.post(f"/api/tasks/{task['task_id']}/stop")
    second = client.post(f"/api/tasks/{task['task_id']}/stop")
    assert first.status_code == second.status_code == 200


def test_camera_preview_owns_only_cameras_and_never_robot_resources(client):
    response = client.post(
        "/api/camera-preview/start",
        json={
            "cameras": {
                "top_rgb": {"serial": "MOCK-TOP"},
                "left_wrist_rgb": {"serial": "MOCK-LEFT"},
                "right_wrist_rgb": {"serial": "MOCK-RIGHT"},
            }
        },
    )

    assert response.status_code == 201
    task = response.json()
    assert task["task_type"] == "camera_preview"
    assert task["resources"] == ["left_wrist_rgb", "right_wrist_rgb", "top_rgb"]
    assert not ({"can0", "can1", "a1z_left", "a1z_right", "leader_left", "leader_right"} & set(task["resources"]))
    client.post(f"/api/tasks/{task['task_id']}/stop")


def test_recording_domain_api_and_zero_frame_guard(client):
    started = client.post("/api/record/start", json={"safety_confirmed": True})
    assert started.status_code == 201
    task_id = started.json()["task_id"]
    wait_ready(client, task_id)

    assert client.post(f"/api/record/{task_id}/start-episode", json={"client_action_id": "x", "episode_index": 0}).status_code == 200
    stale = client.post(
        f"/api/record/{task_id}/finish-episode",
        json={"client_action_id": "stale", "episode_index": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_episode_action"
    empty = client.post(f"/api/record/{task_id}/finish-episode", json={"client_action_id": "y", "episode_index": 0})
    assert empty.status_code == 409
    assert empty.json()["error"]["code"] == "episode_has_no_frames"

    assert client.post(f"/api/mock/{task_id}/frame").status_code == 200
    finished = client.post(f"/api/record/{task_id}/finish-episode", json={"client_action_id": "y", "episode_index": 0})
    assert finished.status_code == 200
    assert finished.json()["record_phase"] == "saving"


def test_record_command_is_rejected_until_worker_ready(client):
    started = client.post("/api/record/start", json={"safety_confirmed": True})
    assert started.status_code == 201
    task_id = started.json()["task_id"]
    runtime = client.app.state.services.tasks.get(task_id)
    runtime.info.status = TaskStatus.STARTING

    response = client.post(
        f"/api/record/{task_id}/start-episode",
        json={"client_action_id": "too-early", "episode_index": 0},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_not_ready"


def test_inference_requires_compatibility_gate(client):
    blocked = client.post("/api/inference/start", json={
        "policy_path": "outputs/mock-model",
        "safety_confirmed": True,
    })
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "compatibility_required"

    inspected = client.post("/api/inference/inspect-policy", json={"policy_path": "outputs/mock-model", "mode": "dual"})
    assert inspected.status_code == 200
    report = inspected.json()
    assert report["compatible"] is True
    assert report["action_dim"] == 14
    assert report["hardware_connected"] is False


def test_logs_support_incremental_recovery(client):
    started = client.post("/api/teleop/start", json={"safety_confirmed": True})
    task_id = started.json()["task_id"]
    wait_ready(client, task_id)
    logs = client.get(f"/api/tasks/{task_id}/logs?after=0").json()
    assert logs["items"]
    last = logs["items"][-1]["seq"]
    assert client.get(f"/api/tasks/{task_id}/logs?after={last}").json()["items"] == []


def test_calibration_and_pairing_mock_workflows(client):
    started = client.post("/api/calibration/start", json={
        "side": "left", "port": "/dev/ttyACM0", "leader_id": "a1z_left_leader"
    })
    assert started.status_code == 201
    task_id = started.json()["task_id"]
    wait_ready(client, task_id)
    assert client.post(f"/api/calibration/{task_id}/middle", json={"client_action_id": "m"}).status_code == 200
    ranged = client.post(f"/api/calibration/{task_id}/record-range", json={"client_action_id": "r"})
    assert ranged.status_code == 200
    assert set(ranged.json()["ranges"]) == {"arm_0", "arm_1", "arm_2", "arm_3", "arm_4", "arm_5", "gripper"}
    assert client.post(f"/api/calibration/{task_id}/stop-range", json={"client_action_id": "s"}).status_code == 200
    saved = client.post(f"/api/calibration/{task_id}/save", json={"client_action_id": "save"})
    assert saved.status_code == 200
    assert saved.json()["calibration_status"] == "saved"

    calculated = client.post("/api/pairing/calculate", json={
        "side": "left",
        "leader_rad": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "follower_rad": [0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
        "signs": [-1, -1, 1, 1, 1, -1],
        "scales": [1, 1, 1, 1, 1, 1],
    })
    assert calculated.status_code == 200
    assert calculated.json()["offsets_rad"] == [0.3, 0.6, 0.3, 0.4, 0.5, 1.8]
    verified = client.post(
        "/api/pairing/verify",
        json={
            "side": "left",
            "leader_rad": [0, 0, 0, 0, 0, 0],
            "follower_rad": [0.2, 0, 0, 0, 0, 0],
            "signs": [1, 1, 1, 1, 1, 1],
            "scales": [1, 1, 1, 1, 1, 1],
            "offsets_rad": [0, 0, 0, 0, 0, 0],
            "tolerance_rad": 0.05,
        },
    )
    assert verified.json()["verified"] is False


def test_mock_fault_stops_record_progression(client):
    started = client.post("/api/record/start", json={"safety_confirmed": True})
    task_id = started.json()["task_id"]
    wait_ready(client, task_id)
    client.post(f"/api/record/{task_id}/start-episode", json={"client_action_id": "start", "episode_index": 0})
    client.post(f"/api/mock/{task_id}/frame")
    faulted = client.post(f"/api/mock/{task_id}/fault", json={"reason": "CAN interface can1 is DOWN"})
    assert faulted.status_code == 200
    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["record_phase"] == "fault"
    assert task["current_episode_invalid"] is True
    assert client.post(f"/api/record/{task_id}/quick-next", json={"client_action_id": "next", "episode_index": 0}).status_code == 409
