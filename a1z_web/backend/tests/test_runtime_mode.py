from __future__ import annotations

from unittest.mock import AsyncMock


def test_real_mode_requires_explicit_hardware_confirmation(client) -> None:
    rejected = client.post(
        "/api/system/mode",
        json={"mode": "real", "hardware_confirmation": False},
    )

    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "hardware_confirmation_required"


def test_runtime_mode_switch_changes_authoritative_backend_settings(client) -> None:
    enabled = client.post(
        "/api/system/mode",
        json={"mode": "real", "hardware_confirmation": True},
    )
    health = client.get("/api/system/health")

    assert enabled.status_code == 200
    assert enabled.json()["mode"] == "real"
    assert enabled.json()["hardware_motion_enabled"] is True
    assert health.json()["mode"] == "real"
    assert health.json()["hardware_motion_enabled"] is True

    disabled = client.post(
        "/api/system/mode",
        json={"mode": "mock", "hardware_confirmation": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["mode"] == "mock"
    assert disabled.json()["hardware_motion_enabled"] is False


def test_system_health_is_degraded_when_can_interface_is_down(client) -> None:
    services = client.app.state.services
    services.settings.mock = False
    services.health.discover_devices = AsyncMock(return_value={
        "mock": False,
        "can": [
            {"name": "can0", "state": "healthy", "bitrate": 1_000_000},
            {"name": "can1", "state": "down"},
        ],
        "leaders": [{"port": "/dev/ttyACM0", "state": "available"}],
        "cameras": [{"name": "D435", "serial": "TOP", "state": "available"}],
    })

    health = client.get("/api/system/health")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
