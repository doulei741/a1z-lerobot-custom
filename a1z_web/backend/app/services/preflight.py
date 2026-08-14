from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.workflows import (
    CalibrationStartRequest,
    InferenceRequest,
    PairingReadRequest,
    RecordingRequest,
    TeleoperationRequest,
)

WorkflowPayload = (
    CalibrationStartRequest
    | PairingReadRequest
    | TeleoperationRequest
    | RecordingRequest
    | InferenceRequest
)
WorkflowName = Literal["calibration", "pairing", "teleoperation", "recording", "inference"]


class PreflightService:
    """Evaluate read-only device and configuration requirements before a workflow starts."""

    def __init__(
        self,
        settings: Settings,
        *,
        health: Any | None = None,
        calibration_root: Path | None = None,
    ) -> None:
        self.settings = settings
        self.health = health
        self.calibration_root = calibration_root or (
            Path.home()
            / ".cache"
            / "huggingface"
            / "lerobot"
            / "calibration"
            / "teleoperators"
            / "a1z_leader"
        )

    async def inspect(self, workflow: WorkflowName, payload: WorkflowPayload) -> dict[str, Any]:
        if self.settings.mock:
            inventory = {
                "mock": True,
                "can": [],
                "leaders": [],
                "cameras": [],
            }
        else:
            if self.health is None:
                raise RuntimeError("Real preflight requires HealthService")
            inventory = await self.health.discover_devices()
        return self.evaluate(workflow, payload, inventory)

    def evaluate(
        self,
        workflow: WorkflowName,
        payload: WorkflowPayload,
        inventory: dict[str, Any],
    ) -> dict[str, Any]:
        if self.settings.mock:
            return {
                "ready": True,
                "simulation": True,
                "workflow": workflow,
                "mode": "mock",
                "issues": [
                    self._issue(
                        "mock_simulation",
                        "web_mode",
                        "当前是 Mock 仿真模式",
                        "本次操作只会模拟状态和日志，不会连接或移动任何真实设备。",
                        "若要控制实机，请以 A1Z_WEB_MOCK=0 和 A1Z_WEB_ALLOW_HARDWARE=1 重启 Web。",
                        severity="warning",
                    )
                ],
                "inventory": inventory,
            }

        issues: list[dict[str, str]] = []
        if not self.settings.allow_hardware:
            issues.append(
                self._issue(
                    "hardware_motion_disabled",
                    "web_mode",
                    "实机动作被后端禁用",
                    "后端处于 Real 模式，但没有获得启动真实机器人任务的权限。",
                    "设置 A1Z_WEB_ALLOW_HARDWARE=1，并在确认现场安全后重启 Web。",
                )
            )

        if isinstance(payload, RecordingRequest):
            config_path = self.settings.project_root / payload.config_path
            if not config_path.is_file():
                issues.append(
                    self._issue(
                        "record_config_missing",
                        "config_path",
                        "录制配置文件不存在",
                        f"没有找到 {payload.config_path}。",
                        "选择项目内存在的 A1Z 录制 YAML 配置后重新检查。",
                    )
                )

        leader_requirements = self._leader_requirements(workflow, payload)
        available_ports = {item.get("port") for item in inventory.get("leaders", [])}
        for side, port, leader_id, needs_calibration in leader_requirements:
            if port not in available_ports:
                issues.append(
                    self._issue(
                        "leader_port_missing",
                        f"leader_{side}",
                        f"{side.title()} Leader 串口不可用",
                        f"配置要求 {port}，但设备发现结果中没有该端口。",
                        "打开顶部“设备准备中心”重新识别 Leader，并在当前页面选择发现的串口。",
                    )
                )
            if needs_calibration and not (self.calibration_root / f"{leader_id}.json").is_file():
                issues.append(
                    self._issue(
                        "leader_calibration_missing",
                        f"leader_{side}",
                        f"{side.title()} Leader 尚未校准",
                        f"没有找到校准文件 {leader_id}.json。",
                        f"先在“机械臂校准”页面完成 {leader_id} 的完整校准并保存。",
                    )
                )

        can_requirements = self._can_requirements(workflow, payload)
        can_devices = {item.get("name"): item for item in inventory.get("can", [])}
        for side, interface in can_requirements:
            device = can_devices.get(interface)
            if device is None:
                issues.append(
                    self._issue(
                        "can_missing",
                        interface,
                        f"{interface} 不存在",
                        f"{side.title()} Follower 需要 SocketCAN 接口 {interface}。",
                        f"打开顶部“设备准备中心”，点击“初始化 {interface}”，完成系统授权后重新检查。",
                    )
                )
                continue
            if device.get("state") != "healthy":
                issues.append(
                    self._issue(
                        "can_not_ready",
                        interface,
                        f"{interface} 未处于 UP 状态",
                        f"当前状态为 {device.get('state', 'unknown')}。",
                        f"打开顶部“设备准备中心”重新初始化 {interface}；页面会验证 UP 和 1 Mbps。",
                    )
                )
            bitrate = device.get("bitrate")
            if bitrate is None:
                issues.append(
                    self._issue(
                        "can_bitrate_unknown",
                        interface,
                        f"无法确认 {interface} 波特率",
                        "设备已出现，但系统未返回可验证的 SocketCAN 波特率。",
                        f"打开顶部“设备准备中心”重新初始化 {interface}，由后端读取并验证波特率。",
                    )
                )
            elif bitrate != 1_000_000:
                issues.append(
                    self._issue(
                        "can_bitrate_mismatch",
                        interface,
                        f"{interface} 波特率不正确",
                        f"当前为 {bitrate} bit/s，A1Z 要求 1000000 bit/s。",
                        f"打开顶部“设备准备中心”重新初始化 {interface}；产品固定使用 1000000 bit/s。",
                    )
                )

        available_serials = {str(item.get("serial")) for item in inventory.get("cameras", [])}
        for name, serial in self._camera_requirements(payload):
            if serial and serial not in available_serials:
                issues.append(
                    self._issue(
                        "camera_missing",
                        name,
                        f"相机 {name} 不可用",
                        f"配置要求序列号 {serial}，但当前没有发现该 RealSense。",
                        "检查相机 USB 3.x 连接和供电，打开顶部“设备准备中心”重新识别，再从页面填写发现的序列号。",
                    )
                )

        return {
            "ready": not any(issue["severity"] == "blocking" for issue in issues),
            "simulation": False,
            "workflow": workflow,
            "mode": "real",
            "issues": issues,
            "inventory": inventory,
        }

    @staticmethod
    def require_ready(report: dict[str, Any]) -> None:
        if not report["ready"]:
            raise ApiError(
                "hardware_preflight_failed",
                "设备或配置未满足当前工作流的启动要求",
                details=report,
                status_code=409,
            )

    @staticmethod
    def _leader_requirements(
        workflow: WorkflowName,
        payload: WorkflowPayload,
    ) -> list[tuple[str, str, str, bool]]:
        if isinstance(payload, CalibrationStartRequest):
            return [(payload.side, payload.port, payload.leader_id, False)]
        if isinstance(payload, PairingReadRequest):
            return [(payload.side, payload.leader_port, payload.leader_id, True)]
        if not isinstance(payload, (TeleoperationRequest, RecordingRequest)):
            return []
        requirements = [("left", payload.left_leader_port, payload.left_leader_id, True)]
        if payload.mode == "dual":
            requirements.append(("right", payload.right_leader_port, payload.right_leader_id, True))
        return requirements

    @staticmethod
    def _can_requirements(
        workflow: WorkflowName,
        payload: WorkflowPayload,
    ) -> list[tuple[str, str]]:
        if workflow == "calibration":
            return []
        if isinstance(payload, PairingReadRequest):
            return [(payload.side, payload.can_interface)]
        if not isinstance(payload, (TeleoperationRequest, RecordingRequest, InferenceRequest)):
            return []
        requirements = [("left", payload.left_can)]
        if payload.mode == "dual":
            requirements.append(("right", payload.right_can))
        return requirements

    def _camera_requirements(self, payload: WorkflowPayload) -> list[tuple[str, str]]:
        if not isinstance(payload, (TeleoperationRequest, RecordingRequest, InferenceRequest)):
            return []
        if payload.cameras:
            return [
                (name, camera.serial)
                for name, camera in payload.cameras.items()
                if camera.enabled
            ]
        if not isinstance(payload, RecordingRequest):
            return []
        config_path = self.settings.project_root / payload.config_path
        if not config_path.is_file():
            return []
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        cameras = (config.get("robot") or {}).get("cameras") or {}
        requirements = [
            (name, str(camera.get("serial_number_or_name", "")))
            for name, camera in cameras.items()
        ]
        if payload.mode == "dual" and payload.right_wrist_serial:
            requirements = [
                (name, payload.right_wrist_serial if name == "right_wrist_rgb" else serial)
                for name, serial in requirements
            ]
        return requirements

    @staticmethod
    def _issue(
        code: str,
        resource: str,
        title: str,
        message: str,
        action: str,
        *,
        severity: Literal["blocking", "warning"] = "blocking",
    ) -> dict[str, str]:
        return {
            "code": code,
            "resource": resource,
            "title": title,
            "message": message,
            "action": action,
            "severity": severity,
        }
