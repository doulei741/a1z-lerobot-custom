from lerobot.cameras.realsense import RealSenseCameraConfig


def default_realsense_cameras(
    d435_serial: str,
    d405_serial: str,
) -> dict[str, RealSenseCameraConfig]:
    """Build the default RGB-only D435 top and D405 wrist camera configuration."""
    return {
        "top_rgb": RealSenseCameraConfig(
            serial_number_or_name=d435_serial,
            width=640,
            height=480,
            fps=30,
            use_depth=False,
        ),
        "wrist_rgb": RealSenseCameraConfig(
            serial_number_or_name=d405_serial,
            width=640,
            height=480,
            fps=30,
            use_depth=False,
        ),
    }
