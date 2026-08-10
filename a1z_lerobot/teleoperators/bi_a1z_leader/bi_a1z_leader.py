import math
from functools import cached_property
from typing import Mapping

from a1z.robots.gripper import GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD
from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.types import RobotAction
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ...robots.a1z_follower.hardware.config import A1Z_DUAL
from ..a1z_leader import A1ZLeader, A1ZLeaderConfig
from ..a1z_leader.a1z_leader import ACTION_KEYS as SINGLE_ACTION_KEYS
from .config_bi_a1z_leader import BiA1ZLeaderConfig


def _gripper_norm_to_raw(value: float) -> float:
    normalized = min(max(float(value), 0.0), 1.0)
    return GRIPPER_CLOSE_RAD + normalized * (GRIPPER_OPEN_RAD - GRIPPER_CLOSE_RAD)


def _validate_single_action(action: Mapping[str, float]) -> None:
    if set(action) != set(SINGLE_ACTION_KEYS):
        raise ValueError(f"single leader action keys must be exactly {list(SINGLE_ACTION_KEYS)}")
    if not all(math.isfinite(float(value)) for value in action.values()):
        raise ValueError("single leader action values must be finite")


def compose_dual_action(
    left_action: Mapping[str, float], right_action: Mapping[str, float]
) -> RobotAction:
    """Map two single-leader actions to the existing A1Z 14D contract."""

    _validate_single_action(left_action)
    _validate_single_action(right_action)
    action: RobotAction = {}
    for side, source in (("left", left_action), ("right", right_action)):
        for index in range(6):
            action[f"{side}_arm_{index}.pos"] = float(source[f"arm_{index}.pos"])
        action[f"{side}_ee_0.pos"] = _gripper_norm_to_raw(source["gripper.pos"])
    return action


class BiA1ZLeader(Teleoperator):
    """Two A1Z leaders exposed as one 14D LeRobot teleoperator."""

    config_class = BiA1ZLeaderConfig
    name = "bi_a1z_leader"

    def __init__(self, config: BiA1ZLeaderConfig):
        super().__init__(config)
        self.config = config
        self.left_arm = A1ZLeader(self._child_config(config.left_id, config.left_arm_config))
        self.right_arm = A1ZLeader(self._child_config(config.right_id, config.right_arm_config))

    def _child_config(self, leader_id, arm_config) -> A1ZLeaderConfig:
        return A1ZLeaderConfig(
            id=leader_id,
            calibration_dir=self.config.calibration_dir,
            port=arm_config.port,
            joint_signs=arm_config.joint_signs,
            joint_scales=arm_config.joint_scales,
            joint_offsets_rad=arm_config.joint_offsets_rad,
        )

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {f"{motor}.pos": float for motor in A1Z_DUAL.motors}

    @cached_property
    def feedback_features(self) -> dict[str, type]:
        return {}

    @property
    def is_connected(self) -> bool:
        return self.left_arm.is_connected and self.right_arm.is_connected

    @property
    def is_calibrated(self) -> bool:
        return self.left_arm.is_calibrated and self.right_arm.is_calibrated

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        try:
            self.left_arm.connect(calibrate)
            self.right_arm.connect(calibrate)
        except Exception:
            for arm in (self.right_arm, self.left_arm):
                if arm.is_connected:
                    arm.disconnect()
            raise

    def calibrate(self) -> None:
        self.left_arm.calibrate()
        self.right_arm.calibrate()

    def configure(self) -> None:
        self.left_arm.configure()
        self.right_arm.configure()

    def setup_motors(self) -> None:
        self.left_arm.setup_motors()
        self.right_arm.setup_motors()

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        return compose_dual_action(self.left_arm.get_action(), self.right_arm.get_action())

    @check_if_not_connected
    def send_feedback(self, feedback: dict[str, float]) -> None:
        raise NotImplementedError("A1Z leaders do not provide force feedback")

    @check_if_not_connected
    def disconnect(self) -> None:
        first_error: Exception | None = None
        for arm in (self.right_arm, self.left_arm):
            if arm.is_connected:
                try:
                    arm.disconnect()
                except Exception as error:
                    first_error = first_error or error
        if first_error is not None:
            raise first_error
