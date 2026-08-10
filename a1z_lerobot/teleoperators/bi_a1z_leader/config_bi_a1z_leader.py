from dataclasses import dataclass

from lerobot.teleoperators.config import TeleoperatorConfig

from ..a1z_leader import A1ZLeaderConfig


@TeleoperatorConfig.register_subclass("bi_a1z_leader")
@dataclass
class BiA1ZLeaderConfig(TeleoperatorConfig):
    """Two independently calibrated seven-servo A1Z leaders."""

    left_arm_config: A1ZLeaderConfig
    right_arm_config: A1ZLeaderConfig

    def __post_init__(self) -> None:
        if self.left_arm_config.port == self.right_arm_config.port:
            raise ValueError("left and right A1Z leaders must use different serial ports")
