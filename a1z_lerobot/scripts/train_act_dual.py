"""ACT training entry point for dual A1Z datasets."""

import sys

from lerobot.scripts.lerobot_train import main as native_main

from .train_act_single import with_act_defaults


def main() -> None:
    sys.argv[:] = with_act_defaults(sys.argv)
    native_main()


if __name__ == "__main__":
    main()
