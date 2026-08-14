from __future__ import annotations


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
