import logging
import math
import time
from collections.abc import Mapping, Sequence

from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from .config_a1z_leader import A1ZLeaderConfig

logger = logging.getLogger(__name__)

JOINT_NAMES = tuple(f"arm_{index}" for index in range(6))
MOTOR_NAMES = (*JOINT_NAMES, "gripper")
ACTION_KEYS = tuple(f"{name}.pos" for name in MOTOR_NAMES)


def map_leader_positions(
    raw_positions: Mapping[str, float],
    signs: Sequence[float] = (1.0,) * 6,
    scales: Sequence[float] = (1.0,) * 6,
    offsets_rad: Sequence[float] = (0.0,) * 6,
) -> dict[str, float]:
    """Convert calibrated leader degrees and gripper percent to A1Z units."""
    expected = set(MOTOR_NAMES)
    if set(raw_positions) != expected:
        raise ValueError(
            f"leader position keys must be exactly {sorted(expected)}, got {sorted(raw_positions)}"
        )
    if not all(len(values) == 6 for values in (signs, scales, offsets_rad)):
        raise ValueError("leader joint mapping vectors must contain 6 values")
    if not all(math.isfinite(float(value)) for value in raw_positions.values()):
        raise ValueError("leader positions must be finite")

    action = {
        f"{name}.pos": (
            math.radians(float(raw_positions[name])) * float(scales[index]) * float(signs[index])
            + float(offsets_rad[index])
        )
        for index, name in enumerate(JOINT_NAMES)
    }
    action["gripper.pos"] = min(max(float(raw_positions["gripper"]) / 100.0, 0.0), 1.0)
    return action


class A1ZLeader(Teleoperator):
    """Seven-axis STS3215 leader whose output matches ``a1z_single``."""

    config_class = A1ZLeaderConfig
    name = "a1z_leader"

    def __init__(self, config: A1ZLeaderConfig):
        super().__init__(config)
        self.config = config
        self.bus = FeetechMotorsBus(
            port=config.port,
            motors={
                **{
                    name: Motor(index + 1, "sts3215", MotorNormMode.DEGREES)
                    for index, name in enumerate(JOINT_NAMES)
                },
                "gripper": Motor(7, "sts3215", MotorNormMode.RANGE_0_100),
            },
            calibration=self.calibration,
        )

    @property
    def action_features(self) -> dict[str, type]:
        return dict.fromkeys(ACTION_KEYS, float)

    @property
    def feedback_features(self) -> dict[str, type]:
        return self.action_features

    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected

    @property
    def is_calibrated(self) -> bool:
        return self.bus.is_calibrated

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        self.bus.connect()
        if not self.is_calibrated and calibrate:
            self.calibrate()
        self.configure()
        logger.info("%s connected.", self)

    def calibrate(self) -> None:
        if self.calibration:
            answer = input(
                f"Press ENTER to use calibration for {self.id}, or type 'c' then ENTER to recalibrate: "
            )
            if answer.strip().lower() != "c":
                self.bus.write_calibration(self.calibration)
                return

        self.bus.disable_torque()
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

        input(f"Move {self} to the middle of every joint range and press ENTER...")
        homing_offsets = self.bus.set_half_turn_homings()
        ranged_motors = [*JOINT_NAMES, "gripper"]
        print(
            "Move arm_0..arm_5 and gripper through their full ranges. "
            "Press ENTER to stop."
        )
        range_mins, range_maxes = self.bus.record_ranges_of_motion(ranged_motors)

        self.calibration = {
            name: MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=homing_offsets[name],
                range_min=range_mins[name],
                range_max=range_maxes[name],
            )
            for name, motor in self.bus.motors.items()
        }
        self.bus.write_calibration(self.calibration)
        self._save_calibration()
        print(f"Calibration saved to {self.calibration_fpath}")

    def configure(self) -> None:
        self.bus.disable_torque()
        self.bus.configure_motors()
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

    def setup_motors(self) -> None:
        for motor in reversed(self.bus.motors):
            input(f"Connect only the '{motor}' servo and press ENTER.")
            self.bus.setup_motor(motor)

    @check_if_not_connected
    def get_action(self) -> dict[str, float]:
        start = time.perf_counter()
        raw = self.bus.sync_read("Present_Position")
        action = map_leader_positions(
            raw,
            signs=self.config.joint_signs,
            scales=self.config.joint_scales,
            offsets_rad=self.config.joint_offsets_rad,
        )
        logger.debug("%s read action in %.1fms", self, (time.perf_counter() - start) * 1e3)
        return action

    @check_if_not_connected
    def send_feedback(self, feedback: dict[str, float]) -> None:
        if set(feedback) != set(ACTION_KEYS):
            raise ValueError(f"feedback keys must be exactly {list(ACTION_KEYS)}")
        goals = {}
        for index, name in enumerate(JOINT_NAMES):
            value = float(feedback[f"{name}.pos"])
            denominator = float(self.config.scales[index]) * float(self.config.joint_signs[index])
            goals[name] = math.degrees(
                (value - float(self.config.joint_offsets_rad[index])) / denominator
            )
        goals["gripper"] = min(max(float(feedback["gripper.pos"]), 0.0), 1.0) * 100.0
        self.bus.sync_write("Goal_Position", goals)

    @check_if_not_connected
    def disconnect(self) -> None:
        self.bus.disconnect()
        logger.info("%s disconnected.", self)
