"""ACT training entry point with RTX 4060-oriented defaults."""

import sys

from lerobot.scripts.lerobot_train import main as native_main


def with_act_defaults(argv: list[str]) -> list[str]:
    defaults = (
        ("--policy.type=", "--policy.type=act"),
        ("--policy.device=", "--policy.device=cuda"),
        ("--batch_size=", "--batch_size=8"),
    )
    result = list(argv)
    for prefix, default in defaults:
        if not any(argument.startswith(prefix) for argument in result[1:]):
            result.append(default)
    return result


def main() -> None:
    sys.argv[:] = with_act_defaults(sys.argv)
    native_main()


if __name__ == "__main__":
    main()
