"""LeRobot v3 recording entry point for the seven-axis leader and one A1Z arm."""

import a1z_lerobot.robots.a1z_single  # noqa: F401
import a1z_lerobot.teleoperators.a1z_leader  # noqa: F401
from lerobot.scripts.lerobot_record import main as native_main


def main() -> None:
    native_main()


if __name__ == "__main__":
    main()
