"""ACT rollout entry point for two A1Z arms."""

import a1z_lerobot.robots.a1z_follower  # noqa: F401
from lerobot.scripts.lerobot_rollout import main as native_main


def main() -> None:
    native_main()


if __name__ == "__main__":
    main()
