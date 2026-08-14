from __future__ import annotations

import math
import re
from pathlib import PurePath
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")


def safe_relative_path(value: str) -> str:
    if not value or PurePath(value).is_absolute() or ".." in PurePath(value).parts:
        raise ValueError("must be a project-relative path without '..'")
    if not SAFE_ID.fullmatch(value):
        raise ValueError("contains unsupported characters")
    return value


FiniteSix = Annotated[list[float], Field(min_length=6, max_length=6)]


class CanInitializeRequest(BaseModel):
    interface: Literal["can0", "can1"]


class JointMapping(BaseModel):
    signs: FiniteSix = Field(default_factory=lambda: [-1, -1, 1, 1, 1, -1])
    scales: FiniteSix = Field(default_factory=lambda: [1, 1, 1, 1, 1, 1])
    offsets_rad: FiniteSix = Field(default_factory=lambda: [0, 0, 0, 0, 0, 0])

    @field_validator("signs", "scales", "offsets_rad")
    @classmethod
    def finite(cls, values: list[float]) -> list[float]:
        if not all(math.isfinite(value) for value in values):
            raise ValueError("all mapping values must be finite")
        return values

    @field_validator("signs")
    @classmethod
    def valid_signs(cls, values: list[float]) -> list[float]:
        if any(value not in (-1, 1) for value in values):
            raise ValueError("joint signs must be -1 or 1")
        return values

    @field_validator("scales")
    @classmethod
    def positive_scales(cls, values: list[float]) -> list[float]:
        if any(value <= 0 or value > 4 for value in values):
            raise ValueError("joint scales must be in (0, 4]")
        return values


def single_verified_mapping() -> JointMapping:
    return JointMapping(
        signs=[-1, 1, 1, 1, 1, -1],
        scales=[1, 1, 1, 1, 1, 1],
        offsets_rad=[-0.040418965, 1.567886653, -1.698370257, -0.144229406, -0.011507665, -0.016411362],
    )


def left_dual_verified_mapping() -> JointMapping:
    return JointMapping(
        signs=[-1, -1, 1, 1, 1, -1],
        scales=[1, 1, 1, 1, 1, 1],
        offsets_rad=[0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.08975979],
    )


def right_dual_verified_mapping() -> JointMapping:
    return JointMapping(
        signs=[-1, -1, 1, 1, 1, -1],
        scales=[1, 1, 1, 1, 1, 1],
        offsets_rad=[-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975],
    )


class CameraSelection(BaseModel):
    enabled: bool = True
    serial: str = ""
    width: int = Field(default=640, ge=160, le=1920)
    height: int = Field(default=480, ge=120, le=1080)
    fps: int = Field(default=30, ge=1, le=60)

    @field_validator("serial")
    @classmethod
    def serial_chars(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("invalid camera serial")
        return value


class MotionBase(BaseModel):
    mode: Literal["single", "dual"] = "dual"
    left_can: str = "can0"
    right_can: str = "can1"
    fps: int = Field(default=30, ge=1, le=60)
    ema_alpha: float = Field(default=0.3, ge=0, le=1)
    max_joint_delta: float = Field(default=0.01, gt=0, le=0.5)
    return_home_on_disconnect: bool = False
    open_grippers_on_disconnect: bool = False
    safety_confirmed: bool = False

    @field_validator("left_can", "right_can")
    @classmethod
    def can_name(cls, value: str) -> str:
        if not re.fullmatch(r"can[0-9]+", value):
            raise ValueError("must be a SocketCAN interface such as can0")
        return value


class TeleoperationRequest(MotionBase):
    left_leader_port: str = "/dev/ttyACM0"
    right_leader_port: str = "/dev/ttyACM1"
    left_leader_id: str = "a1z_left_leader"
    right_leader_id: str = "a1z_right_leader"
    left_mapping: JointMapping = Field(default_factory=left_dual_verified_mapping)
    right_mapping: JointMapping = Field(default_factory=right_dual_verified_mapping)
    gripper_start_hold: bool = True
    display_data: bool = False
    cameras: dict[str, CameraSelection] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def mode_mapping_default(cls, values: object) -> object:
        if isinstance(values, dict) and values.get("mode", "dual") == "single" and "left_mapping" not in values:
            values = dict(values)
            values["left_mapping"] = single_verified_mapping().model_dump()
        return values

    @field_validator("left_leader_port", "right_leader_port")
    @classmethod
    def serial_port(cls, value: str) -> str:
        if not re.fullmatch(r"/dev/tty[A-Za-z0-9._-]+", value):
            raise ValueError("invalid serial port")
        return value


class DatasetRequest(BaseModel):
    repo_id: str = "local/a1z_dual_web"
    root: str = "datasets/a1z_dual_web"
    single_task: str = "Coordinate both arms to complete the configured task"
    num_episodes: int = Field(default=10, ge=1, le=10000)
    episode_time_s: float = Field(default=60, gt=0, le=3600)
    reset_time_s: float = Field(default=10, ge=0, le=3600)
    fps: int = Field(default=30, ge=1, le=60)
    video: bool = True

    @field_validator("repo_id", "root")
    @classmethod
    def paths(cls, value: str) -> str:
        return safe_relative_path(value)

    @field_validator("single_task")
    @classmethod
    def task_text(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 1000 or any(ord(char) < 32 for char in value):
            raise ValueError("task must be printable text up to 1000 characters")
        return value


class RecordingRequest(TeleoperationRequest):
    config_path: str = "a1z_lerobot/configs/record_a1z_dual_realsense.yaml"
    dataset: DatasetRequest = Field(default_factory=DatasetRequest)
    resume: bool = False
    display_data: bool = True
    display_compressed_images: bool = False
    right_wrist_serial: str | None = "260522278763"

    @model_validator(mode="before")
    @classmethod
    def mode_config_default(cls, values: object) -> object:
        if isinstance(values, dict) and values.get("mode", "dual") == "single" and "config_path" not in values:
            values = dict(values)
            values["config_path"] = "a1z_lerobot/configs/record_a1z_single_realsense.yaml"
        return values

    @field_validator("config_path")
    @classmethod
    def config_is_safe(cls, value: str) -> str:
        return safe_relative_path(value)

    @field_validator("right_wrist_serial")
    @classmethod
    def right_serial_chars(cls, value: str | None) -> str | None:
        if value and not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("invalid right wrist camera serial")
        return value


class PolicyInspectRequest(BaseModel):
    policy_path: str
    mode: Literal["single", "dual"] = "dual"

    @field_validator("policy_path")
    @classmethod
    def policy_is_safe(cls, value: str) -> str:
        return safe_relative_path(value)


class InferenceRequest(MotionBase):
    policy_path: str
    compatibility_token: str | None = None
    strategy_type: Literal["base"] = "base"
    inference_type: Literal["sync", "async"] = "sync"
    task: str = "Execute the trained task"
    duration: float = Field(default=10, gt=0, le=3600)
    display_data: bool = True
    gripper_start_hold: bool = False
    cameras: dict[str, CameraSelection] = Field(default_factory=dict)

    @field_validator("policy_path")
    @classmethod
    def policy_is_safe(cls, value: str) -> str:
        return safe_relative_path(value)

    @model_validator(mode="after")
    def act_never_holds_gripper(self) -> InferenceRequest:
        if self.gripper_start_hold:
            raise ValueError("ACT inference requires gripper_start_hold=false")
        return self


class DomainAction(BaseModel):
    client_action_id: str = Field(min_length=1, max_length=100)
    episode_index: int | None = Field(default=None, ge=0)


class RecordAction(BaseModel):
    client_action_id: str = Field(min_length=1, max_length=100)
    episode_index: int = Field(ge=0)


class StopRequest(BaseModel):
    reason: str = Field(default="operator_requested", max_length=200)


class CalibrationStartRequest(BaseModel):
    side: Literal["left", "right"]
    port: str
    leader_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("port")
    @classmethod
    def serial_port(cls, value: str) -> str:
        if not re.fullmatch(r"/dev/tty[A-Za-z0-9._-]+", value):
            raise ValueError("invalid serial port")
        return value


class PairingCalculateRequest(BaseModel):
    side: Literal["left", "right"]
    leader_rad: FiniteSix
    follower_rad: FiniteSix
    signs: FiniteSix = Field(default_factory=lambda: [-1, -1, 1, 1, 1, -1])
    scales: FiniteSix = Field(default_factory=lambda: [1, 1, 1, 1, 1, 1])

    @field_validator("leader_rad", "follower_rad", "signs", "scales")
    @classmethod
    def finite_values(cls, values: list[float]) -> list[float]:
        if not all(math.isfinite(value) for value in values):
            raise ValueError("pairing values must be finite")
        return values


class PairingSaveRequest(PairingCalculateRequest):
    profile_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    leader_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    can_interface: str = Field(pattern=r"^can[0-9]+$")


class PairingVerifyRequest(PairingCalculateRequest):
    offsets_rad: FiniteSix
    tolerance_rad: float = Field(default=0.05, gt=0, le=0.5)


class PairingReadRequest(BaseModel):
    side: Literal["left", "right"]
    leader_port: str
    leader_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    can_interface: str = Field(pattern=r"^can[0-9]+$")
    signs: FiniteSix = Field(default_factory=lambda: [-1, -1, 1, 1, 1, -1])
    scales: FiniteSix = Field(default_factory=lambda: [1, 1, 1, 1, 1, 1])
    safety_confirmed: bool = False

    @field_validator("leader_port")
    @classmethod
    def pairing_port(cls, value: str) -> str:
        if not re.fullmatch(r"/dev/tty[A-Za-z0-9._-]+", value):
            raise ValueError("invalid serial port")
        return value
