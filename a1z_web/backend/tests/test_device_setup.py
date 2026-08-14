from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.workflows import CanInitializeRequest
from app.services.device_setup import DeviceSetupService


def make_settings(tmp_path: Path, *, mock: bool = False, allow_hardware: bool = True) -> Settings:
    return Settings(
        A1Z_PROJECT_ROOT=tmp_path,
        A1Z_WEB_DATA_DIR=tmp_path / "runtime",
        A1Z_WEB_MOCK=mock,
        A1Z_WEB_ALLOW_HARDWARE=allow_hardware,
    )


def test_can_initialize_request_only_accepts_product_interfaces() -> None:
    assert CanInitializeRequest(interface="can0").interface == "can0"
    assert CanInitializeRequest(interface="can1").interface == "can1"
    with pytest.raises(ValidationError):
        CanInitializeRequest(interface="can2")
    with pytest.raises(ValidationError):
        CanInitializeRequest(interface="eth0")


def test_privileged_command_has_fixed_program_and_positional_interface(tmp_path: Path) -> None:
    service = DeviceSetupService(make_settings(tmp_path), health=AsyncMock())

    command = service.privileged_command("can1")

    assert command[:3] == ["/usr/bin/pkexec", "/bin/bash", "-c"]
    assert command[-2:] == ["--", "can1"]
    assert "1000000" in command[3]
    assert "$1" in command[3]
    assert "can1" not in command[3]


@pytest.mark.asyncio
async def test_mock_initialization_is_explicit_and_runs_no_command(tmp_path: Path) -> None:
    runner = AsyncMock()
    service = DeviceSetupService(
        make_settings(tmp_path, mock=True, allow_hardware=False),
        health=AsyncMock(),
        runner=runner,
    )

    result = await service.initialize_can("can0")

    assert result["simulation"] is True
    assert result["state"] == "ready"
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_initialization_verifies_interface_after_privileged_command(tmp_path: Path) -> None:
    health = AsyncMock()
    health.discover_devices.side_effect = [
        {"mock": False, "can": [], "leaders": [], "cameras": []},
        {"mock": False, "can": [{"name": "can0", "state": "healthy", "bitrate": 1_000_000}], "leaders": [], "cameras": []},
    ]
    runner = AsyncMock(return_value=subprocess.CompletedProcess([], 0, "configured", ""))
    service = DeviceSetupService(make_settings(tmp_path), health=health, runner=runner)

    result = await service.initialize_can("can0")

    assert result["state"] == "ready"
    assert result["interface"]["bitrate"] == 1_000_000
    runner.assert_awaited_once()


@pytest.mark.asyncio
async def test_privilege_failure_returns_actionable_error(tmp_path: Path) -> None:
    health = AsyncMock()
    health.discover_devices.return_value = {"mock": False, "can": [], "leaders": [], "cameras": []}
    runner = AsyncMock(return_value=subprocess.CompletedProcess([], 126, "", "Authorization dismissed"))
    service = DeviceSetupService(make_settings(tmp_path), health=health, runner=runner)

    with pytest.raises(ApiError) as raised:
        await service.initialize_can("can0")

    assert raised.value.code == "can_authorization_failed"
    assert raised.value.details["interface"] == "can0"
    assert "系统授权" in raised.value.details["action"]


def test_usb_can_discovery_reports_supported_adapter(tmp_path: Path) -> None:
    device = tmp_path / "1-2.2"
    device.mkdir()
    (device / "idVendor").write_text("a8fa\n", encoding="utf-8")
    (device / "idProduct").write_text("8598\n", encoding="utf-8")
    (device / "serial").write_text("F080203F338E5531\n", encoding="utf-8")
    (device / "product").write_text("HHS CANFD Pro-II\n", encoding="utf-8")

    adapters = DeviceSetupService.discover_usb_can(tmp_path)

    assert adapters == [{
        "usb_path": "1-2.2",
        "vendor_id": "a8fa",
        "product_id": "8598",
        "serial": "F080203F338E5531",
        "product": "HHS CANFD Pro-II",
        "supported": True,
    }]


def test_mock_device_api_initializes_can_and_exposes_usb_inventory(client) -> None:
    devices = client.get("/api/devices")
    initialized = client.post("/api/devices/can/initialize", json={"interface": "can0"})

    assert devices.status_code == 200
    assert "usb_can" in devices.json()
    assert initialized.status_code == 200
    assert initialized.json()["simulation"] is True
