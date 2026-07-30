"""Standalone calibration command for the seven-axis A1Z STS3215 leader."""

import argparse

from a1z_lerobot.teleoperators.a1z_leader import A1ZLeader, A1ZLeaderConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate the seven-axis A1Z STS3215 leader only."
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="Leader serial port.")
    parser.add_argument("--id", dest="leader_id", default="a1z_leader", help="Leader calibration ID.")
    return parser


def calibrate_leader(port: str, leader_id: str) -> None:
    """Force interactive calibration, even when an older file already exists."""
    leader = A1ZLeader(A1ZLeaderConfig(id=leader_id, port=port))
    try:
        leader.connect(calibrate=False)
        leader.calibrate()
        leader.configure()
    finally:
        if leader.is_connected:
            leader.disconnect()


def main() -> None:
    args = build_parser().parse_args()
    calibrate_leader(args.port, args.leader_id)


if __name__ == "__main__":
    main()
