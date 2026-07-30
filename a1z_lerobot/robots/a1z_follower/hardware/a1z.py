"""Single-arm + gripper control wrapper over the GALAXEA-A1Z SDK (ArmRobot)."""
import numpy as np

from a1z.robots.gripper import GRIPPER_CLOSE_RAD as _GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD as _GRIPPER_OPEN_RAD

from .config import CONTROL_FREQ_HZ, MIN_FREQ_HZ

_GRIPPER_SPAN: float = _GRIPPER_OPEN_RAD - _GRIPPER_CLOSE_RAD


def _raw_to_norm(raw_rad: float) -> float:
    """Raw rad -> normalized [0.0 = closed, 1.0 = open]."""
    return float(np.clip((raw_rad - _GRIPPER_CLOSE_RAD) / _GRIPPER_SPAN, 0.0, 1.0))


def _norm_to_raw(norm: float) -> float:
    """Normalized [0.0 = closed, 1.0 = open] -> raw rad."""
    return _GRIPPER_CLOSE_RAD + float(np.clip(norm, 0.0, 1.0)) * _GRIPPER_SPAN


class A1ZArm:
    """Single-arm + gripper wrapper; 7D [j1..j6 rad, gripper_raw_rad] interface over the SDK ArmRobot."""

    def __init__(self, can_channel: str):
        from a1z.robots.get_robot import get_a1z_robot

        self._arm = get_a1z_robot(
            can_channel=can_channel,
            zero_gravity_mode=False,
            control_freq_hz=CONTROL_FREQ_HZ,
            min_freq_hz=MIN_FREQ_HZ,
            with_gripper=True,
        )

    def start(self) -> None:
        """Start the control loop; gripper enable + home done inside ArmRobot.start()."""
        self._arm.start()

    def stop(self) -> None:
        """Stop the control loop; gripper disable done inside ArmRobot.stop()."""
        self._arm.stop()

    def get_state(self) -> np.ndarray:
        """Return 7D state [j1..j6 rad, gripper_raw_rad]; gripper converted normalized -> raw rad."""
        obs = self._arm.get_joint_state()
        pos = obs["pos"]
        gripper_raw = _norm_to_raw(self._arm.gripper.get_feedback_norm())
        return np.concatenate([pos, [gripper_raw]]).astype(np.float32)

    def get_state_normalized(self) -> np.ndarray:
        """Return 7D state [j1..j6 rad, gripper normalized to 0=closed, 1=open]."""
        obs = self._arm.get_joint_state()
        gripper = self._arm.gripper.get_feedback_norm()
        return np.concatenate([obs["pos"], [gripper]]).astype(np.float32)

    def send_command(self, cmd: np.ndarray) -> None:
        """Send a 7D command [j1..j6 rad, gripper_raw_rad]; gripper converted raw rad -> normalized."""
        self._arm.command_joint_pos(cmd[:6])
        self._arm.gripper.command(_raw_to_norm(float(cmd[6])))

    def send_command_normalized(self, cmd: np.ndarray) -> None:
        """Send [j1..j6 rad, gripper normalized to 0=closed, 1=open]."""
        self._arm.command_joint_pos(np.asarray(cmd, dtype=np.float32))

    def command_gripper(self, pos: float) -> None:
        """Send a gripper position command (raw rad)."""
        self._arm.gripper.command(_raw_to_norm(pos))

    def disable_gripper(self) -> None:
        """Disable the gripper motor (already called inside ArmRobot.stop(); this is a safety net)."""
        if self._arm.gripper is not None:
            self._arm.gripper.disable()

    def move_to_home(self, speed: float = 0.3) -> None:
        """Smoothly return to the home position (blocks until reached)."""
        self._arm.move_joints(np.zeros(6), speed=speed)
