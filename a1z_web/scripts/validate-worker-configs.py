#!/usr/bin/env python
"""Validate Web worker argv/config translation without opening any hardware."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import draccus
import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    backend = args.project_root / "a1z_web" / "backend"
    workers = backend / "app" / "workers"
    sys.path[:0] = [str(backend), str(workers)]

    from app.schemas.workflows import RecordingRequest, TeleoperationRequest
    from recording import merge_request
    from teleoperation import build_command
    from lerobot.scripts.lerobot_record import RecordConfig

    for mode in ("single", "dual"):
        record_request = RecordingRequest(mode=mode).model_dump(mode="json")
        source = yaml.safe_load((args.project_root / record_request["config_path"]).read_text())
        config = draccus.decode(RecordConfig, merge_request(source, record_request))
        expected_dim = 7 if mode == "single" else 14
        command = build_command(TeleoperationRequest(mode=mode).model_dump(mode="json"))
        assert config.dataset.fps == 30
        assert command[0] == f"a1z-teleoperate-{mode}"
        print(f"{mode}: record config decoded; expected contract={expected_dim}D; teleop argv valid")
    print("No CAN, Leader, RealSense, or motor was opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
