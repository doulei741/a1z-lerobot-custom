import dataclasses

# SDK default control frequency 250 Hz, minimum acceptable frequency 80 Hz
CONTROL_FREQ_HZ = 250.0
MIN_FREQ_HZ = 80.0


@dataclasses.dataclass(frozen=True)
class RobotConfig:
    motors: list[str]


# GALAXEA A1Z dual-arm: 6 joints + 1 gripper per side = 14D
# State/action vector order: [left_arm x6, left_gripper x1, right_arm x6, right_gripper x1]
A1Z_DUAL = RobotConfig(
    motors=[
        "left_arm_0", "left_arm_1", "left_arm_2",
        "left_arm_3", "left_arm_4", "left_arm_5",
        "left_ee_0",
        "right_arm_0", "right_arm_1", "right_arm_2",
        "right_arm_3", "right_arm_4", "right_arm_5",
        "right_ee_0",
    ],
)
