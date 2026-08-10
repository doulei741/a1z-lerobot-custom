"""Two seven-axis leaders to dual A1Z teleoperation entry point."""

import a1z_lerobot.robots.a1z_follower  # noqa: F401
import a1z_lerobot.teleoperators.bi_a1z_leader  # noqa: F401
from lerobot.scripts.lerobot_teleoperate import main as native_main


def main() -> None:
    native_main()


if __name__ == "__main__":
    main()
