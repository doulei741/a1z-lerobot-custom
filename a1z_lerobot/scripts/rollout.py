# a1z_lerobot/scripts/rollout.py
"""A1Z dual-arm policy inference entry point (reuses lerobot's native rollout engine)."""
import a1z_lerobot.robots.a1z_follower  # noqa: F401  triggers A1Z registration
from lerobot.scripts.lerobot_rollout import rollout


def main():
    rollout()


if __name__ == "__main__":
    main()
