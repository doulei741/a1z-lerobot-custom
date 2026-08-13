from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import ApiError

MOTORS = ("arm_0", "arm_1", "arm_2", "arm_3", "arm_4", "arm_5", "gripper")


@dataclass
class CalibrationSession:
    phase: str = "waiting_middle"
    calibration_status: str = "not_saved"
    ranges: dict[str, dict[str, int]] = field(
        default_factory=lambda: {name: {"min": 2048, "max": 2048} for name in MOTORS}
    )
    actions: set[str] = field(default_factory=set)

    def apply(self, command: str, action_id: str) -> dict[str, Any]:
        if action_id in self.actions:
            return self.payload()
        allowed = {
            "middle": {"waiting_middle"},
            "record_range": {"waiting_range"},
            "stop_range": {"recording_range"},
            "save": {"review"},
            "cancel": {"waiting_middle", "waiting_range", "recording_range", "review"},
        }
        if self.phase not in allowed.get(command, set()):
            raise ApiError(
                "illegal_calibration_phase",
                f"Cannot {command} while calibration phase is {self.phase}",
                status_code=409,
            )
        if command == "middle":
            self.phase = "waiting_range"
        elif command == "record_range":
            self.phase = "recording_range"
            # Mock values visibly evolve without claiming to be real hardware values.
            self.ranges = {name: {"min": 900 + index * 10, "max": 3200 - index * 10} for index, name in enumerate(MOTORS)}
        elif command == "stop_range":
            self.phase = "review"
        elif command == "save":
            self.phase = "saving"
            self.calibration_status = "pending"
        else:
            self.phase = "cancelled"
        self.actions.add(action_id)
        return self.payload()

    def payload(self) -> dict[str, Any]:
        return {"calibration_phase": self.phase, "calibration_status": self.calibration_status, "ranges": self.ranges}


class PairingProfiles:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @staticmethod
    def calculate(leader: list[float], follower: list[float], signs: list[float], scales: list[float]) -> list[float]:
        return [round(follower[index] - leader[index] * scales[index] * signs[index], 9) for index in range(6)]

    def list(self) -> list[dict[str, Any]]:
        profiles = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                profiles.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return profiles

    def save(self, profile: dict[str, Any]) -> dict[str, Any]:
        path = self.directory / f"{profile['profile_id']}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
        return profile
