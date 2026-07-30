import logging
from collections.abc import Mapping
from functools import cached_property

import numpy as np

from lerobot.cameras import make_cameras_from_configs
from lerobot.robots.robot import Robot
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..a1z_follower.hardware.a1z import A1ZArm
from ..a1z_follower.hardware.config import A1Z_JOINT_LIMITS, A1Z_SINGLE_MOTORS
from .config_a1z_single import A1ZSingleConfig

logger = logging.getLogger(__name__)

ACTION_KEYS = tuple(f"{motor}.pos" for motor in A1Z_SINGLE_MOTORS)
JOINT_LIMITS = np.asarray(A1Z_JOINT_LIMITS, dtype=np.float32)


def validate_policy_features(policy_config, camera_features: Mapping[str, tuple[int, int, int]]) -> None:
    """Fail before hardware connection when an ACT checkpoint contract does not match."""
    state_feature = policy_config.input_features.get("observation.state")
    if state_feature is None or tuple(state_feature.shape) != (7,):
        shape = None if state_feature is None else tuple(state_feature.shape)
        raise ValueError(f"policy state shape must be (7,), got {shape}")

    action_feature = policy_config.output_features.get("action")
    if action_feature is None or tuple(action_feature.shape) != (7,):
        shape = None if action_feature is None else tuple(action_feature.shape)
        raise ValueError(f"policy action shape must be (7,), got {shape}")

    expected_visuals = {
        key: tuple(feature.shape)
        for key, feature in policy_config.input_features.items()
        if key.startswith("observation.images.")
    }
    provided_visuals = {
        f"observation.images.{name}": (shape[2], shape[0], shape[1])
        for name, shape in camera_features.items()
    }
    if expected_visuals != provided_visuals:
        raise ValueError(
            "policy visual features must exactly match the configured cameras: "
            f"policy={expected_visuals}, robot={provided_visuals}"
        )


def process_single_action(
    action: Mapping[str, float],
    *,
    previous: np.ndarray,
    ema_alpha: float,
    max_joint_delta: float,
) -> np.ndarray:
    """Validate and convert a requested action into the safe command actually sent."""
    if set(action) != set(ACTION_KEYS):
        raise ValueError(f"action keys must be exactly {list(ACTION_KEYS)}")
    target = np.asarray([float(action[key]) for key in ACTION_KEYS], dtype=np.float32)
    if target.shape != (7,) or not np.isfinite(target).all():
        raise ValueError("all seven action values must be finite")
    previous = np.asarray(previous, dtype=np.float32)
    if previous.shape != (7,) or not np.isfinite(previous).all():
        raise ValueError("previous action must contain seven finite values")

    sent = ema_alpha * target + (1.0 - ema_alpha) * previous
    if max_joint_delta > 0.0:
        delta = np.clip(sent[:6] - previous[:6], -max_joint_delta, max_joint_delta)
        sent[:6] = previous[:6] + delta
    sent[:6] = np.clip(sent[:6], JOINT_LIMITS[:, 0], JOINT_LIMITS[:, 1])
    sent[6] = np.clip(sent[6], 0.0, 1.0)
    return sent.astype(np.float32)


def rebase_relative_action(
    action: Mapping[str, float],
    *,
    leader_reference: Mapping[str, float],
    follower_reference: np.ndarray,
) -> dict[str, float]:
    """Map Leader deltas from its start pose onto the A1Z start pose."""
    for values in (action, leader_reference):
        if set(values) != set(ACTION_KEYS):
            raise ValueError(f"action keys must be exactly {list(ACTION_KEYS)}")
    follower_reference = np.asarray(follower_reference, dtype=np.float32)
    if follower_reference.shape != (7,) or not np.isfinite(follower_reference).all():
        raise ValueError("follower reference must contain seven finite values")
    return {
        key: float(follower_reference[index] + float(action[key]) - float(leader_reference[key]))
        for index, key in enumerate(ACTION_KEYS)
    }


class A1ZSingle(Robot):
    """LeRobot Robot adapter for one six-joint A1Z arm and normalized gripper."""

    config_class = A1ZSingleConfig
    name = "a1z_single"

    def __init__(self, config: A1ZSingleConfig):
        super().__init__(config)
        self.config = config
        self.motors = list(A1Z_SINGLE_MOTORS)
        self.cameras = make_cameras_from_configs(config.cameras)
        self.arm: A1ZArm | None = None
        self._connected = False
        self._previous_action: np.ndarray | None = None
        self._relative_leader_reference: dict[str, float] | None = None
        self._relative_follower_reference: np.ndarray | None = None

    @property
    def _motors_ft(self) -> dict[str, type]:
        return dict.fromkeys(ACTION_KEYS, float)

    @property
    def _cameras_ft(self) -> dict[str, tuple[int, int, int]]:
        return {
            name: (config.height, config.width, 3)
            for name, config in self.config.cameras.items()
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple[int, int, int]]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        return self._connected and all(camera.is_connected for camera in self.cameras.values())

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        pass

    def validate_policy_features(self, policy_config) -> None:
        validate_policy_features(policy_config, self._cameras_ft)

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        self.arm = A1ZArm(self.config.can_channel)
        connected_cameras = []
        try:
            self.arm.start()
            for camera in self.cameras.values():
                camera.connect()
                connected_cameras.append(camera)
            self._previous_action = self.arm.get_state_normalized()
            self._relative_leader_reference = None
            self._relative_follower_reference = self._previous_action.copy()
            self._connected = True
        except Exception:
            for camera in reversed(connected_cameras):
                camera.disconnect()
            self.arm.stop()
            self.arm = None
            raise
        logger.info("%s connected.", self)

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        state = self.arm.get_state_normalized()
        observation: RobotObservation = {
            key: float(state[index]) for index, key in enumerate(ACTION_KEYS)
        }
        for name, camera in self.cameras.items():
            observation[name] = camera.async_read()
        return observation

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        if self.config.relative_action_reference:
            if self._relative_leader_reference is None:
                self._relative_leader_reference = {key: float(action[key]) for key in ACTION_KEYS}
            action = rebase_relative_action(
                action,
                leader_reference=self._relative_leader_reference,
                follower_reference=self._relative_follower_reference,
            )
        sent = process_single_action(
            action,
            previous=self._previous_action,
            ema_alpha=self.config.ema_alpha,
            max_joint_delta=self.config.max_joint_delta,
        )
        self.arm.send_command_normalized(sent)
        self._previous_action = sent.copy()
        return {key: float(sent[index]) for index, key in enumerate(ACTION_KEYS)}

    @check_if_not_connected
    def disconnect(self) -> None:
        arm = self.arm
        first_error: Exception | None = None
        try:
            for camera in self.cameras.values():
                if camera.is_connected:
                    try:
                        camera.disconnect()
                    except Exception as error:
                        first_error = first_error or error
            if arm is not None:
                if self.config.return_home_on_disconnect:
                    try:
                        arm.move_to_home()
                    except Exception as error:
                        first_error = first_error or error
                try:
                    arm.stop()
                except Exception as error:
                    first_error = first_error or error
        finally:
            self.arm = None
            self._connected = False
            self._previous_action = None
            self._relative_leader_reference = None
            self._relative_follower_reference = None
        if first_error is not None:
            raise first_error
        logger.info("%s disconnected.", self)
