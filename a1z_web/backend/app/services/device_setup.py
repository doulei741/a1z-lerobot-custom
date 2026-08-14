from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import ApiError

CommandRunner = Callable[[list[str]], Awaitable[subprocess.CompletedProcess[str]]]

SOCKETCAN_SETUP = r"""
set -eu
/usr/sbin/modprobe gs_usb
if [ -e /sys/bus/usb/drivers/gs_usb/new_id ]; then
  printf '%s\n' 'a8fa 8598' > /sys/bus/usb/drivers/gs_usb/new_id 2>/dev/null || true
fi
/usr/sbin/ip link set "$1" down 2>/dev/null || true
/usr/sbin/ip link set "$1" type can bitrate 1000000
/usr/sbin/ip link set "$1" txqueuelen 1000
/usr/sbin/ip link set "$1" up
""".strip()


class DeviceSetupService:
    """Performs the narrow privileged setup needed by the supported USB-CAN adapter."""

    def __init__(self, settings: Settings, *, health: Any, runner: CommandRunner | None = None) -> None:
        self.settings = settings
        self.health = health
        self.runner = runner or self._run

    @staticmethod
    def privileged_command(interface: str) -> list[str]:
        return ["/usr/bin/pkexec", "/bin/bash", "-c", SOCKETCAN_SETUP, "--", interface]

    @staticmethod
    async def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment.pop("LD_LIBRARY_PATH", None)
        return await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )

    async def initialize_can(self, interface: str) -> dict[str, Any]:
        if self.settings.mock:
            return {
                "state": "ready",
                "interface": {"name": interface, "state": "healthy", "bitrate": 1_000_000},
                "simulation": True,
                "message": f"Mock initialized {interface}",
            }
        if not self.settings.allow_hardware:
            raise ApiError(
                "hardware_motion_disabled",
                "实机设备配置被后端禁用",
                status_code=409,
                details={"action": "以 A1Z_WEB_ALLOW_HARDWARE=1 重启 Web 后端。"},
            )

        inventory = await self.health.discover_devices()
        existing = next((item for item in inventory.get("can", []) if item.get("name") == interface), None)
        if existing and existing.get("state") == "healthy" and existing.get("bitrate") == 1_000_000:
            return {"state": "ready", "interface": existing, "simulation": False, "message": f"{interface} 已完成初始化"}

        try:
            result = await self.runner(self.privileged_command(interface))
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise ApiError(
                "can_authorization_unavailable",
                "无法启动系统授权程序",
                status_code=503,
                details={"interface": interface, "action": "确认桌面 Polkit 授权代理正在运行，然后重试。", "reason": str(exc)},
            ) from exc
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "authorization or setup failed").strip()
            raise ApiError(
                "can_authorization_failed",
                f"{interface} 初始化未获授权或执行失败",
                status_code=409,
                details={"interface": interface, "action": "在系统授权弹窗中完成授权；若没有弹窗，检查 Polkit 桌面代理。", "reason": reason[-1000:]},
            )

        refreshed = await self.health.discover_devices()
        configured = next((item for item in refreshed.get("can", []) if item.get("name") == interface), None)
        if not configured or configured.get("state") != "healthy" or configured.get("bitrate") != 1_000_000:
            raise ApiError(
                "can_verification_failed",
                f"{interface} 命令已执行，但接口验证未通过",
                status_code=409,
                details={"interface": interface, "action": "检查 USB-CAN 是否重新枚举，并在设备中心刷新后重试。", "inventory": refreshed},
            )
        return {"state": "ready", "interface": configured, "simulation": False, "message": f"{interface} 已初始化为 1 Mbps"}

    @staticmethod
    def discover_usb_can(root: Path = Path("/sys/bus/usb/devices")) -> list[dict[str, Any]]:
        adapters: list[dict[str, Any]] = []
        if not root.exists():
            return adapters
        for vendor_path in sorted(root.glob("*/idVendor")):
            device = vendor_path.parent
            vendor = vendor_path.read_text(encoding="utf-8").strip().lower()
            product_path = device / "idProduct"
            product_id = product_path.read_text(encoding="utf-8").strip().lower() if product_path.exists() else ""
            if (vendor, product_id) != ("a8fa", "8598"):
                continue
            def read(name: str, fallback: str, device_root: Path = device) -> str:
                path = device_root / name
                return path.read_text(encoding="utf-8").strip() if path.exists() else fallback
            adapters.append({
                "usb_path": device.name,
                "vendor_id": vendor,
                "product_id": product_id,
                "serial": read("serial", "unknown"),
                "product": read("product", "HHS CANFD Pro-II"),
                "supported": True,
            })
        return adapters
