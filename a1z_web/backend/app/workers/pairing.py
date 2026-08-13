from __future__ import annotations

import math

from a1z_lerobot.robots.a1z_follower.hardware.a1z import A1ZArm
from a1z_lerobot.teleoperators.a1z_leader import A1ZLeader, A1ZLeaderConfig
from a1z_lerobot.teleoperators.a1z_leader.a1z_leader import JOINT_NAMES
from common import emit, request_json


def main() -> int:
    request = request_json()
    leader = A1ZLeader(
        A1ZLeaderConfig(id=request["leader_id"], port=request["leader_port"])
    )
    follower = A1ZArm(request["can_interface"])
    try:
        leader.connect()
        # A1Z SDK read requires start; the API therefore treats pairing as a
        # confirmed motion-capable hardware session and owns the CAN resource.
        follower.start()
        raw = leader.bus.sync_read("Present_Position")
        leader_rad = [math.radians(float(raw[name])) for name in JOINT_NAMES]
        follower_state = follower.get_state_normalized()
        follower_rad = [float(value) for value in follower_state[:6]]
        offsets = [
            follower_rad[index]
            - leader_rad[index] * request["scales"][index] * request["signs"][index]
            for index in range(6)
        ]
        emit(
            "pairing_read",
            side=request["side"],
            leader_rad=leader_rad,
            follower_rad=follower_rad,
            signs=request["signs"],
            scales=request["scales"],
            offsets_rad=offsets,
        )
        emit("ready", phase="review")
        return 0
    except Exception as exc:
        emit("fault", reason=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        try:
            follower.stop()
        except Exception:
            pass
        if leader.is_connected:
            leader.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
