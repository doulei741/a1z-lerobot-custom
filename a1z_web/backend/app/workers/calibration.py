from __future__ import annotations

import json
import sys

from a1z_lerobot.teleoperators.a1z_leader import A1ZLeader, A1ZLeaderConfig
from a1z_lerobot.teleoperators.a1z_leader.a1z_leader import MOTOR_NAMES
from common import emit, request_json
from lerobot.motors import MotorCalibration
from lerobot.motors.feetech import OperatingMode


def main() -> int:
    request = request_json()
    leader = A1ZLeader(A1ZLeaderConfig(id=request["leader_id"], port=request["port"]))
    homing: dict[str, int] | None = None
    mins: dict[str, int] | None = None
    maxes: dict[str, int] | None = None
    try:
        leader.connect(calibrate=False)
        leader.bus.disable_torque()
        for motor in leader.bus.motors:
            leader.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)
        emit("ready", phase="waiting_middle", calibration_exists=bool(leader.calibration))
        for line in sys.stdin:
            command = json.loads(line).get("command")
            if command == "middle":
                homing = leader.bus.set_half_turn_homings()
                emit("phase", phase="waiting_range")
            elif command == "record_range":
                positions = leader.bus.sync_read("Present_Position", list(MOTOR_NAMES), normalize=False)
                mins = {key: int(value) for key, value in positions.items()}
                maxes = dict(mins)
                emit("phase", phase="recording_range")
                while True:
                    positions = leader.bus.sync_read("Present_Position", list(MOTOR_NAMES), normalize=False)
                    mins = {name: min(mins[name], int(positions[name])) for name in MOTOR_NAMES}
                    maxes = {name: max(maxes[name], int(positions[name])) for name in MOTOR_NAMES}
                    emit("calibration_ranges", ranges={name: {"min": mins[name], "max": maxes[name], "position": int(positions[name])} for name in MOTOR_NAMES})
                    # stdin command polling is deliberately handled by select.
                    import select

                    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if ready:
                        nested = json.loads(sys.stdin.readline()).get("command")
                        if nested == "stop_range":
                            emit("phase", phase="review")
                            break
            elif command == "save":
                if homing is None or mins is None or maxes is None:
                    raise RuntimeError("Calibration data is incomplete")
                if any(mins[name] == maxes[name] for name in MOTOR_NAMES):
                    raise RuntimeError("Every Leader joint and gripper must move during range recording")
                leader.calibration = {
                    name: MotorCalibration(
                        id=motor.id,
                        drive_mode=0,
                        homing_offset=homing[name],
                        range_min=mins[name],
                        range_max=maxes[name],
                    )
                    for name, motor in leader.bus.motors.items()
                }
                leader.bus.write_calibration(leader.calibration)
                leader._save_calibration()
                emit("calibration_saved", path=str(leader.calibration_fpath))
                return 0
            elif command == "cancel":
                return 0
    except Exception as exc:
        emit("fault", reason=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        if leader.is_connected:
            try:
                leader.disconnect()
            except Exception as exc:
                print(f"Calibration disconnect warning: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
