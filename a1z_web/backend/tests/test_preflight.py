from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.workflows import (
    CalibrationStartRequest,
    InferenceRequest,
    RecordingRequest,
    TeleoperationRequest,
)
from app.services.preflight import PreflightService
from app.services.workflows import HealthService


def settings(tmp_path: Path, *, mock: bool, allow_hardware: bool) -> Settings:
    return Settings(
        A1Z_PROJECT_ROOT=tmp_path,
        A1Z_WEB_DATA_DIR=tmp_path / "runtime",
        A1Z_WEB_MOCK=mock,
        A1Z_WEB_ALLOW_HARDWARE=allow_hardware,
    )


def dual_inventory() -> dict:
    return {
        "mock": False,
        "can": [
            {"name": "can0", "state": "healthy", "bitrate": 1_000_000},
            {"name": "can1", "state": "healthy", "bitrate": 1_000_000},
        ],
        "leaders": [
            {"port": "/dev/ttyACM0", "state": "available"},
            {"port": "/dev/ttyACM1", "state": "available"},
        ],
        "cameras": [
            {"name": "Intel RealSense D435", "serial": "TOP", "state": "available"},
            {"name": "Intel RealSense D405", "serial": "LEFT", "state": "available"},
            {"name": "Intel RealSense D405", "serial": "RIGHT", "state": "available"},
        ],
    }


def write_dual_calibrations(root: Path) -> None:
    (root / "a1z_left_leader.json").write_text("{}", encoding="utf-8")
    (root / "a1z_right_leader.json").write_text("{}", encoding="utf-8")


def test_mock_preflight_discloses_simulation_without_blocking(tmp_path: Path) -> None:
    service = PreflightService(settings(tmp_path, mock=True, allow_hardware=False), calibration_root=tmp_path)

    report = service.evaluate("teleoperation", TeleoperationRequest(), dual_inventory())

    assert report["ready"] is True
    assert report["simulation"] is True
    assert report["issues"][0]["code"] == "mock_simulation"
    assert report["issues"][0]["severity"] == "warning"


def test_real_dual_teleop_reports_each_missing_can_and_calibration(tmp_path: Path) -> None:
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    inventory = {**dual_inventory(), "can": []}

    report = service.evaluate("teleoperation", TeleoperationRequest(), inventory)

    codes = [issue["code"] for issue in report["issues"]]
    assert report["ready"] is False
    assert codes.count("can_missing") == 2
    assert codes.count("leader_calibration_missing") == 2
    assert any("setup.sh can0" in issue["action"] for issue in report["issues"])


def test_real_dual_teleop_accepts_up_1mbit_can_ports_and_calibrations(tmp_path: Path) -> None:
    write_dual_calibrations(tmp_path)
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)

    report = service.evaluate("teleoperation", TeleoperationRequest(), dual_inventory())

    assert report["ready"] is True
    assert report["issues"] == []


def test_wrong_can_state_or_bitrate_is_blocking(tmp_path: Path) -> None:
    write_dual_calibrations(tmp_path)
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    inventory = dual_inventory()
    inventory["can"] = [
        {"name": "can0", "state": "down", "bitrate": 1_000_000},
        {"name": "can1", "state": "healthy", "bitrate": 500_000},
    ]

    report = service.evaluate("teleoperation", TeleoperationRequest(), inventory)

    assert {issue["code"] for issue in report["issues"]} == {"can_not_ready", "can_bitrate_mismatch"}


def test_unknown_can_bitrate_is_blocking(tmp_path: Path) -> None:
    write_dual_calibrations(tmp_path)
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    inventory = dual_inventory()
    inventory["can"][0]["bitrate"] = None

    report = service.evaluate("teleoperation", TeleoperationRequest(), inventory)

    assert report["ready"] is False
    assert [issue["code"] for issue in report["issues"]] == ["can_bitrate_unknown"]


def test_inference_reports_exact_missing_camera_serial(tmp_path: Path) -> None:
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    payload = InferenceRequest(
        policy_path="outputs/model",
        cameras={
            "top_rgb": {"serial": "TOP"},
            "left_wrist_rgb": {"serial": "LEFT"},
            "right_wrist_rgb": {"serial": "MISSING"},
        },
    )

    report = service.evaluate("inference", payload, dual_inventory())

    assert report["ready"] is False
    issue = next(issue for issue in report["issues"] if issue["code"] == "camera_missing")
    assert issue["resource"] == "right_wrist_rgb"
    assert "MISSING" in issue["message"]


def test_calibration_requires_selected_port_but_not_can(tmp_path: Path) -> None:
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    payload = CalibrationStartRequest(side="left", port="/dev/ttyACM9", leader_id="new_leader")

    report = service.evaluate("calibration", payload, dual_inventory())

    assert [issue["code"] for issue in report["issues"]] == ["leader_port_missing"]


def test_real_preflight_blocks_when_hardware_motion_is_disabled(tmp_path: Path) -> None:
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=False), calibration_root=tmp_path)

    report = service.evaluate("calibration", CalibrationStartRequest(side="left", port="/dev/ttyACM0", leader_id="new"), dual_inventory())

    assert report["ready"] is False
    assert report["issues"][0]["code"] == "hardware_motion_disabled"
    with pytest.raises(ApiError) as raised:
        service.require_ready(report)
    assert "A1Z_WEB_ALLOW_HARDWARE=1" in raised.value.details["issues"][0]["action"]


def test_recording_uses_yaml_camera_serials_and_right_wrist_override(tmp_path: Path) -> None:
    write_dual_calibrations(tmp_path)
    config = tmp_path / "a1z_lerobot/configs/record_a1z_dual_realsense.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        """
robot:
  cameras:
    top_rgb: {serial_number_or_name: TOP}
    left_wrist_rgb: {serial_number_or_name: LEFT}
    right_wrist_rgb: {serial_number_or_name: CONFIGURE_RIGHT_D405_SERIAL}
""".strip(),
        encoding="utf-8",
    )
    service = PreflightService(settings(tmp_path, mock=False, allow_hardware=True), calibration_root=tmp_path)
    payload = RecordingRequest(right_wrist_serial="RIGHT-NEW")

    report = service.evaluate("recording", payload, dual_inventory())

    issue = next(issue for issue in report["issues"] if issue["code"] == "camera_missing")
    assert issue["resource"] == "right_wrist_rgb"
    assert "RIGHT-NEW" in issue["message"]


def test_can_discovery_treats_up_can_with_unknown_operstate_as_healthy() -> None:
    links = [
        {
            "ifname": "can0",
            "flags": ["NOARP", "UP", "LOWER_UP"],
            "operstate": "UNKNOWN",
            "linkinfo": {"info_kind": "can", "info_data": {"bitrate": 1_000_000}},
        },
        {"ifname": "wlo1", "flags": ["UP"], "link_type": "ether"},
    ]

    assert HealthService._parse_can_links(links) == [
        {"name": "can0", "state": "healthy", "bitrate": 1_000_000}
    ]
