"""Seven-axis leader to single-arm A1Z teleoperation entry point."""

import a1z_lerobot.robots.a1z_single  # noqa: F401
import a1z_lerobot.teleoperators.a1z_leader  # noqa: F401
from lerobot.scripts.lerobot_teleoperate import main as native_main


def main() -> None:
    native_main()


if __name__ == "__main__":
    main()
