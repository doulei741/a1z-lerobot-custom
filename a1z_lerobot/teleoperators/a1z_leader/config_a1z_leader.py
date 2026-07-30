import math
from dataclasses import dataclass

from lerobot.teleoperators.config import TeleoperatorConfig


@TeleoperatorConfig.register_subclass("a1z_leader")
@dataclass
class A1ZLeaderConfig(TeleoperatorConfig):
    """Configuration for the seven-STS3215 A1Z-shaped leader arm."""

    port: str
    joint_signs: tuple[float, ...] = (-1.0, -1.0, -1.0, 1.0, 1.0, -1.0)
    joint_scales: tuple[float, ...] = (1.0,) * 6
    joint_offsets_rad: tuple[float, ...] = (
        -0.040418965,
        -1.556060913,
        1.709433057,
        -0.144229406,
        -0.011507665,
        -0.016411362,
    )

    def __post_init__(self) -> None:
        for name in ("joint_signs", "joint_scales", "joint_offsets_rad"):
            values = getattr(self, name)
            if len(values) != 6:
                raise ValueError(f"{name} must contain 6 values")
            if not all(math.isfinite(float(value)) for value in values):
                raise ValueError(f"{name} values must be finite")
        if any(float(value) == 0.0 for value in self.joint_signs):
            raise ValueError("joint_signs values must be non-zero")
        if any(float(value) == 0.0 for value in self.joint_scales):
            raise ValueError("joint_scales values must be non-zero")
