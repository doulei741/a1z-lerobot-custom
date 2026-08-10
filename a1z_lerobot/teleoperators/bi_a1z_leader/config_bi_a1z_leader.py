from dataclasses import dataclass

from lerobot.teleoperators.config import TeleoperatorConfig

from ..a1z_leader import A1ZLeaderConfigBase


@TeleoperatorConfig.register_subclass("bi_a1z_leader")
@dataclass
class BiA1ZLeaderConfig(TeleoperatorConfig):
    """Two independently calibrated seven-servo A1Z leaders."""

    left_arm_config: A1ZLeaderConfigBase
    right_arm_config: A1ZLeaderConfigBase
    left_id: str = "a1z_left_leader"
    right_id: str = "a1z_right_leader"

    def __post_init__(self) -> None:
        if self.left_arm_config.port == self.right_arm_config.port:
            raise ValueError("left and right A1Z leaders must use different serial ports")
        if self.left_id == self.right_id:
            raise ValueError("left and right A1Z leaders must use different calibration IDs")
