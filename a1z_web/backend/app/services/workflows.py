from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.workflows import (
    CalibrationStartRequest,
    InferenceRequest,
    PairingReadRequest,
    PolicyInspectRequest,
    RecordingRequest,
    TeleoperationRequest,
)
from app.services.calibration import PairingProfiles

if TYPE_CHECKING:
    from app.services.device_setup import DeviceSetupService
    from app.services.preflight import PreflightService


class CommandBuilder:
    """Converts validated models to fixed argv arrays; never invokes a shell."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _worker(self, workflow: str, payload: Any) -> list[str]:
        worker = Path(__file__).resolve().parents[1] / "workers" / f"{workflow}.py"
        return [
            "conda", "run", "-n", self.settings.conda_env, "--no-capture-output",
            "python", str(worker), "--request-json", json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
        ]

    def teleoperation(self, payload: TeleoperationRequest) -> list[str]:
        return self._worker("teleoperation", payload)

    def recording(self, payload: RecordingRequest) -> list[str]:
        return self._worker("recording", payload)

    def inference(self, payload: InferenceRequest) -> list[str]:
        return self._worker("inference", payload)

    def calibration(self, payload: CalibrationStartRequest) -> list[str]:
        return self._worker("calibration", payload)

    def pairing(self, payload: PairingReadRequest) -> list[str]:
        return self._worker("pairing", payload)


class PolicyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tokens: dict[str, tuple[str, str]] = {}

    def inspect(self, payload: PolicyInspectRequest) -> dict[str, Any]:
        expected_dim = 14 if payload.mode == "dual" else 7
        if self.settings.mock:
            report = {
                "policy_path": payload.policy_path,
                "policy_type": "act",
                "state_dim": expected_dim,
                "action_dim": expected_dim,
                "camera_keys": ["top_rgb", "left_wrist_rgb", "right_wrist_rgb"] if payload.mode == "dual" else ["top_rgb", "wrist_rgb"],
                "image_shape": [3, 480, 640],
                "fps": 30,
                "processor": "mock-normalizer",
                "device": "cuda",
                "checks": {"state": True, "action": True, "feature_names": True, "resolution": True, "cameras": True},
                "compatible": True,
                "hardware_connected": False,
                "mock": True,
            }
        else:
            model_dir = self._resolve_policy(payload.policy_path)
            config_path = model_dir / "config.json"
            if not config_path.exists():
                raise ApiError("policy_config_missing", f"Missing {config_path}", status_code=404)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            inputs = config.get("input_features", {})
            outputs = config.get("output_features", {})
            state_dim = self._feature_dim(inputs, "observation.state")
            action_dim = self._feature_dim(outputs, "action")
            camera_keys = sorted(key.removeprefix("observation.images.") for key in inputs if "images." in key)
            expected_cameras = (
                {"top_rgb", "left_wrist_rgb", "right_wrist_rgb"}
                if payload.mode == "dual"
                else {"top_rgb", "wrist_rgb"}
            )
            processors_present = (model_dir / "policy_preprocessor.json").exists() and (
                model_dir / "policy_postprocessor.json"
            ).exists()
            checks = {
                "state": state_dim == expected_dim,
                "action": action_dim == expected_dim,
                "feature_names": "observation.state" in inputs and "action" in outputs,
                "resolution": all(self._image_shape(feature)[-2:] == [480, 640] for key, feature in inputs.items() if "images." in key),
                "cameras": set(camera_keys) == expected_cameras,
                "processors": processors_present,
            }
            report = {
                "policy_path": str(model_dir.relative_to(self.settings.project_root)),
                "policy_type": config.get("type", config.get("policy_type", "unknown")),
                "state_dim": state_dim,
                "action_dim": action_dim,
                "camera_keys": camera_keys,
                "image_shape": next((self._image_shape(v) for k, v in inputs.items() if "images." in k), None),
                "fps": config.get("fps"),
                "processor": "present" if processors_present else "missing",
                "device": config.get("device", "cuda"),
                "checks": checks,
                "compatible": all(checks.values()),
                "hardware_connected": False,
                "mock": False,
            }
        token = hashlib.sha256(f"{payload.policy_path}:{payload.mode}:{json.dumps(report, sort_keys=True)}".encode()).hexdigest()[:24]
        if report["compatible"]:
            self._tokens[token] = (payload.policy_path, payload.mode)
        report["compatibility_token"] = token if report["compatible"] else None
        return report

    def validate_token(self, token: str, path: str, mode: str) -> None:
        if self.settings.mock and token == "mock-compatible":
            return
        if self._tokens.get(token) != (path, mode):
            raise ApiError("compatibility_token_invalid", "Policy compatibility result is missing or stale", status_code=409)

    def _resolve_policy(self, relative: str) -> Path:
        candidate = (self.settings.project_root / relative).resolve()
        if self.settings.project_root.resolve() not in candidate.parents:
            raise ApiError("policy_path_outside_project", "Policy must be inside the configured project", status_code=400)
        if candidate.is_symlink():
            candidate = candidate.resolve()
        if (candidate / "pretrained_model").is_dir():
            candidate /= "pretrained_model"
        return candidate

    @staticmethod
    def _feature_dim(features: dict[str, Any], name: str) -> int | None:
        feature = features.get(name, {})
        shape = feature.get("shape") if isinstance(feature, dict) else None
        return int(shape[-1]) if shape else None

    @staticmethod
    def _image_shape(feature: Any) -> list[int]:
        return list(feature.get("shape", [])) if isinstance(feature, dict) else []


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def discover_devices(self) -> dict[str, Any]:
        can_devices, leaders = await asyncio.to_thread(self._local_devices)
        cameras: list[dict[str, str]] = []
        try:
            environment = dict(os.environ)
            environment.pop("LD_LIBRARY_PATH", None)
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "conda",
                    "run",
                    "-n",
                    self.settings.conda_env,
                    "--no-capture-output",
                    "python",
                    str(self.settings.project_root / "a1z_web" / "scripts" / "probe-realsense.py"),
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                env=environment,
            )
            if result.returncode == 0:
                cameras = json.loads(result.stdout.strip() or "[]")
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        return {"mock": False, "can": can_devices, "leaders": leaders, "cameras": cameras}

    @staticmethod
    def _local_devices() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        can_devices: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["ip", "-details", "-json", "link", "show"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                can_devices = HealthService._parse_can_links(json.loads(result.stdout))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        leaders = [{"port": str(path), "state": "available"} for path in sorted(Path("/dev").glob("ttyACM*"))]
        return can_devices, leaders

    @staticmethod
    def _parse_can_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        devices = []
        for link in links:
            info = link.get("linkinfo", {})
            if info.get("info_kind") != "can":
                continue
            flags = set(link.get("flags", []))
            state = "healthy" if "UP" in flags and "LOWER_UP" in flags else str(link.get("operstate", "unknown")).lower()
            data = info.get("info_data", {})
            item = {"name": link["ifname"], "state": state}
            bitrate = data.get("bitrate")
            bittiming = data.get("bittiming")
            if bitrate is None and isinstance(bittiming, dict):
                bitrate = bittiming.get("bitrate")
            if bitrate is not None:
                item["bitrate"] = int(bitrate)
            devices.append(item)
        return devices


class DatasetCompatibilityService:
    """Read-only LeRobot metadata gate; it never opens robot or camera devices."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def inspect(self, payload: RecordingRequest) -> dict[str, Any]:
        expected_dim = 14 if payload.mode == "dual" else 7
        expected_cameras = set(payload.cameras) if payload.cameras else (
            {"top_rgb", "left_wrist_rgb", "right_wrist_rgb"}
            if payload.mode == "dual"
            else {"top_rgb", "wrist_rgb"}
        )
        if not payload.resume:
            return {
                "compatible": True,
                "new_dataset": True,
                "existing_episodes": 0,
                "checks": {"new_dataset": True},
                "expected": {"state_dim": expected_dim, "action_dim": expected_dim, "fps": payload.dataset.fps},
            }
        if self.settings.mock:
            return {
                "compatible": True,
                "new_dataset": False,
                "existing_episodes": 25,
                "checks": {"state": True, "action": True, "fps": True, "camera_keys": True, "resolution": True},
                "expected": {"state_dim": expected_dim, "action_dim": expected_dim, "fps": payload.dataset.fps},
            }
        info_path = self.settings.project_root / payload.dataset.root / "meta" / "info.json"
        if not info_path.exists():
            raise ApiError("resume_dataset_missing", f"Resume dataset not found: {payload.dataset.root}", status_code=404)
        info = json.loads(info_path.read_text(encoding="utf-8"))
        features = info.get("features", {})
        state_dim = self._shape_dim(features.get("observation.state"))
        action_dim = self._shape_dim(features.get("action"))
        state_names = (features.get("observation.state") or {}).get("names", [])
        action_names = (features.get("action") or {}).get("names", [])
        if payload.mode == "dual":
            expected_names = [
                *[f"left_arm_{index}.pos" for index in range(6)],
                "left_ee_0.pos",
                *[f"right_arm_{index}.pos" for index in range(6)],
                "right_ee_0.pos",
            ]
            expected_robot = "a1z"
        else:
            expected_names = [*[f"arm_{index}.pos" for index in range(6)], "gripper.pos"]
            expected_robot = "a1z_single"
        camera_features = {
            key.removeprefix("observation.images."): value
            for key, value in features.items()
            if key.startswith("observation.images.")
        }
        checks = {
            "state": state_dim == expected_dim,
            "action": action_dim == expected_dim,
            "feature_names": state_names == expected_names and action_names == expected_names,
            "robot_type": info.get("robot_type") == expected_robot,
            "fps": int(info.get("fps", -1)) == payload.dataset.fps,
            "camera_keys": set(camera_features) == expected_cameras,
            "resolution": all(self._image_resolution(value) == [480, 640] for value in camera_features.values()),
        }
        return {
            "compatible": all(checks.values()),
            "new_dataset": False,
            "existing_episodes": int(info.get("total_episodes", 0)),
            "checks": checks,
            "actual": {"state_dim": state_dim, "action_dim": action_dim, "fps": info.get("fps"), "camera_keys": sorted(camera_features)},
            "expected": {"state_dim": expected_dim, "action_dim": expected_dim, "fps": payload.dataset.fps, "camera_keys": sorted(expected_cameras)},
        }

    @staticmethod
    def _shape_dim(feature: Any) -> int | None:
        shape = feature.get("shape", []) if isinstance(feature, dict) else []
        return int(shape[-1]) if shape else None

    @staticmethod
    def _image_resolution(feature: Any) -> list[int]:
        shape = feature.get("shape", []) if isinstance(feature, dict) else []
        if len(shape) != 3:
            return []
        if shape[-1] in {1, 3, 4}:
            return list(shape[:2])
        if shape[0] in {1, 3, 4}:
            return list(shape[-2:])
        return []


@dataclass
class Services:
    settings: Settings
    hardware: Any
    events: Any
    tasks: Any
    commands: CommandBuilder
    policy: PolicyService
    health: HealthService
    datasets: DatasetCompatibilityService
    profiles: PairingProfiles
    preflight: PreflightService
    device_setup: DeviceSetupService

    def dataset_existing_episodes(self, payload: RecordingRequest) -> int:
        return int(self.datasets.inspect(payload)["existing_episodes"])

    def schedule_mock_save(self, runtime: Any) -> None:
        async def finish() -> None:
            await asyncio.sleep(0.05)
            if runtime.record.phase.value == "saving":
                runtime.record.apply_system("saving_complete")
                await self.events.publish("record_phase", {"record_phase": runtime.record.phase.value}, runtime.info.task_id)

        asyncio.create_task(finish())
