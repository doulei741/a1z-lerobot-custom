#!/usr/bin/env python3
"""Enumerate RealSense USB identities without starting any camera stream."""

from __future__ import annotations

import json

import pyrealsense2 as rs


def main() -> int:
    cameras = []
    for device in rs.context().query_devices():
        cameras.append(
            {
                "name": device.get_info(rs.camera_info.name),
                "serial": device.get_info(rs.camera_info.serial_number),
                "state": "available",
            }
        )
    print(json.dumps(cameras, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
