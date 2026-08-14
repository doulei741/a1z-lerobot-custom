from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path


def test_dev_script_fails_fast_when_backend_port_is_already_owned() -> None:
    web_root = Path(__file__).resolve().parents[2]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        occupied_port = listener.getsockname()[1]
        env = {
            **os.environ,
            "A1Z_WEB_PORT": str(occupied_port),
            "A1Z_WEB_FRONTEND_PORT": str(occupied_port + 1),
        }
        result = subprocess.run(
            ["bash", str(web_root / "scripts" / "dev.sh")],
            cwd=web_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    assert result.returncode != 0
    assert "backend failed to start" in result.stderr.lower()
