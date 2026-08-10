"""Observe calibrated A1Z Leader joint deltas without connecting a Follower."""

import argparse
import logging
import math
import sys
import time
from collections.abc import Callable, Sequence

from a1z_lerobot.teleoperators.a1z_leader import A1ZLeader, A1ZLeaderConfig

logger = logging.getLogger(__name__)


class _CompatibleArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        raw_args = sys.argv[1:] if args is None else args
        normalized_args = list(raw_args)
        for index, argument in enumerate(normalized_args):
            if argument.startswith("--joint-indices="):
                option, value = argument.split("=", 1)
                normalized_args[index : index + 1] = [option, value]
                break
        return super().parse_args(normalized_args, namespace)


def validate_joint_indices(indices: Sequence[int]) -> tuple[int, ...]:
    result = tuple(indices)
    if (
        not result
        or len(set(result)) != len(result)
        or any(index not in range(6) for index in result)
    ):
        raise ValueError("joint indices must be unique values in 0..5")
    return result


def _validate_positive(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a positive finite value")
    return value


def format_joint_line(
    action: dict[str, float],
    deltas: dict[int, float],
    joint_indices: tuple[int, ...],
) -> str:
    return " | ".join(
        f"J{index + 1}={float(action[f'arm_{index}.pos']):+.3f} rad, "
        f"delta_J{index + 1}={deltas[index]:+.3f} rad"
        for index in joint_indices
    )


def _format_baseline(action: dict[str, float], joint_indices: tuple[int, ...]) -> str:
    values = " | ".join(
        f"J{index + 1}={float(action[f'arm_{index}.pos']):+.3f} rad"
        for index in joint_indices
    )
    return f"Baseline: {values}"


def observe_joint_deltas(
    leader,
    *,
    joint_indices: tuple[int, ...],
    duration_s: float,
    threshold_rad: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    output: Callable[[str], None] = print,
) -> str:
    duration_s = _validate_positive(duration_s, "duration_s")
    threshold_rad = _validate_positive(threshold_rad, "threshold_rad")
    joint_indices = validate_joint_indices(joint_indices)

    baseline = leader.get_action()
    output(_format_baseline(baseline, joint_indices))
    last_printed = dict.fromkeys(joint_indices, 0.0)
    started = monotonic()

    while monotonic() - started < duration_s:
        action = leader.get_action()
        deltas = {
            index: float(action[f"arm_{index}.pos"])
            - float(baseline[f"arm_{index}.pos"])
            for index in joint_indices
        }
        if any(
            abs(deltas[index] - last_printed[index]) >= threshold_rad
            for index in joint_indices
        ):
            output(format_joint_line(action, deltas, joint_indices))
            last_printed = deltas
        sleep(0.05)

    return "completed"


def run_diagnostic(
    port: str,
    leader_id: str,
    *,
    duration_s: float = 30.0,
    threshold_rad: float = 0.02,
    joint_indices: Sequence[int] = (1, 2),
    leader_factory=A1ZLeader,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    output: Callable[[str], None] = print,
) -> str:
    duration_s = _validate_positive(duration_s, "duration_s")
    threshold_rad = _validate_positive(threshold_rad, "threshold_rad")
    joint_indices = validate_joint_indices(joint_indices)

    config = A1ZLeaderConfig(id=leader_id, port=port)
    leader = leader_factory(config)
    original_error: BaseException | None = None
    connect_completed = False
    try:
        output(
            f"Leader={leader_id}, port={port}, joints="
            f"{[index + 1 for index in joint_indices]}, duration={duration_s:g}s, "
            f"threshold={threshold_rad:g}rad"
        )
        leader.connect(calibrate=False)
        connect_completed = True
        return observe_joint_deltas(
            leader,
            joint_indices=joint_indices,
            duration_s=duration_s,
            threshold_rad=threshold_rad,
            monotonic=monotonic,
            sleep=sleep,
            output=output,
        )
    except KeyboardInterrupt:
        return "interrupted"
    except BaseException as error:
        original_error = error
        raise
    finally:
        if leader.is_connected:
            try:
                if connect_completed:
                    leader.disconnect()
                else:
                    leader.bus.disconnect(disable_torque=False)
            except Exception:
                if original_error is None:
                    raise
                logger.exception(
                    "Leader disconnect failed while preserving the original diagnostic error"
                )


def build_parser() -> argparse.ArgumentParser:
    parser = _CompatibleArgumentParser(
        description="Observe A1Z Leader joint deltas without connecting a Follower."
    )
    parser.add_argument("--port", required=True, help="Leader serial port.")
    parser.add_argument(
        "--id", dest="leader_id", required=True, help="Leader calibration ID."
    )
    parser.add_argument("--duration-s", type=float, default=30.0)
    parser.add_argument("--threshold-rad", type=float, default=0.02)
    parser.add_argument("--joint-indices", type=int, nargs="+", default=[1, 2])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    status = run_diagnostic(
        args.port,
        args.leader_id,
        duration_s=args.duration_s,
        threshold_rad=args.threshold_rad,
        joint_indices=args.joint_indices,
    )
    if status == "interrupted":
        print("Diagnostic interrupted by operator; Leader disconnected.")
    else:
        print("Diagnostic completed; Leader disconnected.")


if __name__ == "__main__":
    main()
