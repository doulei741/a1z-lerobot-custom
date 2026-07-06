"""Dual-arm composition: two A1ZArm -> 14D interface [left j1..j6, left_ee, right j1..j6, right_ee]."""
import numpy as np


class A1ZDualArm:
    """Compose two A1ZArm into a 14D interface, presenting as "one robot"."""

    def __init__(self, left_can: str, right_can: str):
        from .a1z import A1ZArm
        self.left = A1ZArm(left_can)
        self.right = A1ZArm(right_can)

    @classmethod
    def from_arms(cls, left, right) -> "A1ZDualArm":
        """Assemble from already-constructed arm objects (testing / advanced use, no hardware init)."""
        obj = cls.__new__(cls)
        obj.left = left
        obj.right = right
        return obj

    def start(self) -> None:
        self.left.start()
        self.right.start()

    def stop(self) -> None:
        self.left.stop()
        self.right.stop()

    def get_state(self) -> np.ndarray:
        """Return the 14D state."""
        return np.concatenate([self.left.get_state(), self.right.get_state()])

    def send_command(self, cmd: np.ndarray) -> None:
        """Receive a 14D command and split it across the two arms."""
        self.left.send_command(cmd[:7])
        self.right.send_command(cmd[7:])

    def command_gripper(self, pos: float) -> None:
        self.left.command_gripper(pos)
        self.right.command_gripper(pos)

    def disable_gripper(self) -> None:
        self.left.disable_gripper()
        self.right.disable_gripper()

    def move_to_home(self, speed: float = 0.3) -> None:
        self.left.move_to_home(speed)
        self.right.move_to_home(speed)
