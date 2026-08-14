from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

WORKERS = Path(__file__).resolve().parents[1] / "app" / "workers"
sys.path.insert(0, str(WORKERS))

def test_init_rerun_serves_browser_viewer_when_web_ports_are_provided(monkeypatch) -> None:
    from common import start_task_rerun

    fake_rerun = SimpleNamespace(
        init=Mock(),
        serve_grpc=Mock(return_value="rerun+http://127.0.0.1:19876/proxy"),
        serve_web_viewer=Mock(),
        spawn=Mock(),
        connect_grpc=Mock(),
    )
    monkeypatch.setitem(sys.modules, "rerun", fake_rerun)
    monkeypatch.setenv("A1Z_RERUN_WEB_PORT", "19090")
    monkeypatch.setenv("A1Z_RERUN_GRPC_PORT", "19876")

    assert start_task_rerun("teleoperation") is True

    fake_rerun.serve_grpc.assert_called_once_with(
        grpc_port=19876,
        server_memory_limit="10%",
    )
    fake_rerun.serve_web_viewer.assert_called_once_with(
        web_port=19090,
        open_browser=False,
        connect_to="rerun+http://127.0.0.1:19876/proxy",
    )
    fake_rerun.spawn.assert_not_called()
    fake_rerun.connect_grpc.assert_not_called()


def test_rerun_runtime_requires_display_and_an_enabled_camera() -> None:
    from app.services.task_manager import build_rerun_runtime

    ports = iter((19090, 19876))
    metadata = {
        "config": {
            "display_data": True,
            "cameras": {
                "top_rgb": {"enabled": True, "serial": "TOP"},
                "left_wrist_rgb": {"enabled": False, "serial": "LEFT"},
            },
        }
    }

    environment = build_rerun_runtime(metadata, allocate_port=lambda: next(ports))

    assert environment == {
        "A1Z_RERUN_WEB_PORT": "19090",
        "A1Z_RERUN_GRPC_PORT": "19876",
    }
    assert metadata["rerun"] == {
        "enabled": True,
        "web_port": 19090,
        "grpc_port": 19876,
        "url": "http://127.0.0.1:19090",
        "grpc_url": "rerun+http://127.0.0.1:19876/proxy",
        "cameras": ["top_rgb"],
    }

    disabled: dict = {"config": {"display_data": False, "cameras": {"top_rgb": {"enabled": True}}}}
    assert build_rerun_runtime(disabled, allocate_port=lambda: 1) == {}
    assert disabled["rerun"]["enabled"] is False


def test_dataset_compatibility_ignores_disabled_camera_keys(client) -> None:
    response = client.post(
        "/api/record/compatibility",
        json={
            "mode": "dual",
            "cameras": {
                "top_rgb": {"enabled": True, "serial": "TOP"},
                "left_wrist_rgb": {"enabled": False, "serial": "LEFT"},
                "right_wrist_rgb": {"enabled": True, "serial": "RIGHT"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["expected"]["camera_keys"] == ["right_wrist_rgb", "top_rgb"]
