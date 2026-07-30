"""ACT rollout entry point for one A1Z arm."""

import a1z_lerobot.robots.a1z_single  # noqa: F401
from lerobot.scripts.lerobot_rollout import main as native_main


def main() -> None:
    native_main()


if __name__ == "__main__":
    main()
