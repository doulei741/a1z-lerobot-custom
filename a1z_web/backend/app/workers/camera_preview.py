from __future__ import annotations

import signal
import time

import rerun as rr
from common import emit, request_json, start_task_rerun, stop_task_rerun
from lerobot.cameras.realsense import RealSenseCamera, RealSenseCameraConfig


def main() -> int:
    """Preview RealSense observations without constructing any robot or teleoperator."""

    payload = request_json()
    selected = {
        name: config
        for name, config in payload["cameras"].items()
        if config.get("enabled", True) and config.get("serial")
    }
    compress_images = payload.get("display_compressed_images", True)
    cameras: dict[str, RealSenseCamera] = {}
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    rerun_started = start_task_rerun("camera_preview")
    try:
        for name, config in selected.items():
            camera = RealSenseCamera(
                RealSenseCameraConfig(
                    serial_number_or_name=config["serial"],
                    width=config.get("width", 640),
                    height=config.get("height", 480),
                    fps=config.get("fps", 30),
                    use_depth=False,
                )
            )
            camera.connect()
            cameras[name] = camera
        emit("ready", phase="running", cameras=sorted(cameras))
        target_fps = min(config.get("fps", 30) for config in selected.values())
        period = 1.0 / max(target_fps, 1)
        while running:
            started = time.perf_counter()
            for name, camera in cameras.items():
                image = rr.Image(camera.async_read())
                rr.log(f"observation.images.{name}", image.compress() if compress_images else image)
            remaining = period - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)
        return 0
    except Exception as exc:
        emit("fault", reason=f"Camera preview failed: {exc}")
        raise
    finally:
        for camera in reversed(tuple(cameras.values())):
            if camera.is_connected:
                camera.disconnect()
        if rerun_started:
            stop_task_rerun()


if __name__ == "__main__":
    raise SystemExit(main())
