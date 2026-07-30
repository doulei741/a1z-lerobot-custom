import math
from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.robots.config import RobotConfig


@RobotConfig.register_subclass("a1z_single")
@dataclass
class A1ZSingleConfig(RobotConfig):
    """LeRobot configuration for one A1Z arm and a dynamic camera dictionary."""

    can_channel: str = "can0"
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
    ema_alpha: float = 0.3
    max_joint_delta: float = 0.05
    gripper_start_hold: bool = False
    return_home_on_disconnect: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        if not math.isfinite(self.ema_alpha) or not 0.0 <= self.ema_alpha <= 1.0:
            raise ValueError("ema_alpha must be finite and between 0 and 1")
        if not math.isfinite(self.max_joint_delta) or self.max_joint_delta < 0.0:
            raise ValueError("max_joint_delta must be finite and non-negative")
