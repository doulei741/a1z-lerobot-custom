from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.robots.config import RobotConfig


@RobotConfig.register_subclass("a1z")
@dataclass
class A1ZConfig(RobotConfig):
    """lerobot Robot config for the A1Z dual-arm; camera keys: head_rgb / left_wrist_rgb / right_wrist_rgb."""

    # Left/right arm CAN bus interfaces
    left_can: str = "can0"
    right_can: str = "can1"

    # Camera configs; keys must match the training dataset's observation.images.*
    cameras: dict[str, CameraConfig] = field(default_factory=dict)

    # EMA smoothing factor: out = alpha*new + (1-alpha)*prev; alpha=1 means no smoothing
    ema_alpha: float = 0.3

    # Per-step joint change clip (rad); <=0 disables. Joints only, grippers unclipped
    max_joint_delta: float = 0.05

    # Keep both follower grippers at their measured startup positions until each leader moves.
    gripper_start_hold: bool = True

    # Exit movement is opt-in for dual-arm safety.
    return_home_on_disconnect: bool = False
    open_grippers_on_disconnect: bool = False
