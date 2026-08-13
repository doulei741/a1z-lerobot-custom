from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from typing import Any

EVENT_PREFIX = "A1Z_EVENT "


def request_json() -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    return json.loads(parser.parse_args().request_json)


def emit(event_type: str, **data: Any) -> None:
    print(EVENT_PREFIX + json.dumps({"type": event_type, "data": data}, ensure_ascii=False), flush=True)


def cameras_argv(cameras: dict[str, dict[str, Any]]) -> str:
    configs = {}
    for name, camera in cameras.items():
        if camera.get("enabled", True) and camera.get("serial"):
            configs[name] = {
                "type": "intelrealsense",
                "serial_number_or_name": camera["serial"],
                "width": camera.get("width", 640),
                "height": camera.get("height", 480),
                "fps": camera.get("fps", 30),
                "color_mode": "rgb",
                "use_depth": False,
            }
    return json.dumps(configs, separators=(",", ":"))


def proxy_process(argv: list[str], ready_markers: tuple[str, ...]) -> int:
    """Run a verified CLI, forwarding signals and adding structured lifecycle events."""
    emit("phase", phase="starting", command=argv[0])
    process = subprocess.Popen(
        argv,
        cwd=os.environ.get("A1Z_PROJECT_ROOT") or os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    def forward(signum: int, _frame: Any) -> None:
        if process.poll() is None:
            os.killpg(process.pid, signum)

    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGTERM, forward)
    ready = False
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        if not ready and any(marker in line for marker in ready_markers):
            ready = True
            emit("ready", phase="running")
        lowered = line.lower()
        if "network is down" in lowered or "emergency stop" in lowered or "timed out waiting for frame" in lowered:
            emit("fault", reason=line.strip())
    return_code = process.wait()
    if return_code and not ready:
        emit("fault", reason=f"Worker exited before ready handshake (code {return_code})")
    return return_code


def mapping_args(prefix: str, mapping: dict[str, list[float]]) -> list[str]:
    return [
        f"--teleop.{prefix}.joint_signs={json.dumps(mapping['signs'], separators=(',', ':'))}",
        f"--teleop.{prefix}.joint_scales={json.dumps(mapping['scales'], separators=(',', ':'))}",
        f"--teleop.{prefix}.joint_offsets_rad={json.dumps(mapping['offsets_rad'], separators=(',', ':'))}",
    ]


def boolean(value: bool) -> str:
    return "true" if value else "false"
