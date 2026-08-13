from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import ApiError
from app.models.tasks import RecordPhase


@dataclass(frozen=True)
class RecordResult:
    phase: RecordPhase
    episode_index: int
    saved_episodes: int
    quick_next_armed: bool


@dataclass
class RecordSession:
    """Domain state machine independent from process and UI state."""

    existing_episodes: int
    add_episodes: int
    phase: RecordPhase = RecordPhase.READY
    episode_index: int = 0
    frames: int = 0
    saved_episodes: int = 0
    quick_next_armed: bool = False
    current_episode_invalid: bool = False
    fault_reason: str | None = None
    _actions: dict[str, RecordResult] = field(default_factory=dict)

    @property
    def last_trusted_episode(self) -> int:
        return self.existing_episodes + self.saved_episodes - 1

    def snapshot(self) -> RecordResult:
        return RecordResult(
            self.phase, self.episode_index, self.saved_episodes, self.quick_next_armed
        )

    def note_frame(self) -> None:
        if self.phase is not RecordPhase.RECORDING:
            raise ApiError("illegal_record_phase", "Frames are accepted only while recording", status_code=409)
        self.frames += 1

    def is_duplicate(self, action_id: str) -> bool:
        return action_id in self._actions

    def apply(self, command: str, action_id: str) -> RecordResult:
        if action_id in self._actions:
            return self._actions[action_id]
        if self.phase is RecordPhase.FAULT:
            raise ApiError("illegal_record_phase", "Recording is faulted", status_code=409)

        if command == "start_episode":
            self._require(RecordPhase.READY)
            if self.episode_index >= self.add_episodes:
                raise ApiError("episode_limit_reached", "Requested episode count is complete", status_code=409)
            self.phase = RecordPhase.RECORDING
            self.frames = 0
            self.current_episode_invalid = False
        elif command in {"finish_episode", "quick_next"}:
            self._require(RecordPhase.RECORDING)
            if self.frames == 0:
                raise ApiError(
                    "episode_has_no_frames",
                    "At least one frame is required before saving an episode",
                    status_code=409,
                )
            self.quick_next_armed = command == "quick_next"
            self.phase = RecordPhase.SAVING
        elif command == "rerecord":
            self._require(RecordPhase.RECORDING)
            self.frames = 0
            self.current_episode_invalid = False
            self.phase = RecordPhase.RECORDING
        elif command == "reset_done":
            self._require(RecordPhase.RESETTING)
            if self.quick_next_armed:
                self.quick_next_armed = False
                self.phase = RecordPhase.RECORDING
                self.frames = 0
            else:
                self.phase = RecordPhase.READY
        elif command == "stop":
            if self.phase in {RecordPhase.SAVING, RecordPhase.RESETTING}:
                raise ApiError("record_busy", "Wait for saving/resetting to finish", status_code=409)
            self.phase = RecordPhase.FINISHED
        else:
            raise ApiError("unknown_record_command", f"Unknown command: {command}")

        result = self.snapshot()
        self._actions[action_id] = result
        return result

    def apply_system(self, event: str) -> RecordResult:
        if event == "saving_complete":
            self._require(RecordPhase.SAVING)
            self.saved_episodes += 1
            self.episode_index += 1
            if self.episode_index >= self.add_episodes:
                self.phase = RecordPhase.FINISHED
                self.quick_next_armed = False
            else:
                self.phase = RecordPhase.RESETTING
        else:
            raise ApiError("unknown_record_event", f"Unknown record event: {event}")
        return self.snapshot()

    def fault(self, reason: str) -> None:
        self.fault_reason = reason
        self.current_episode_invalid = self.phase in {RecordPhase.RECORDING, RecordPhase.SAVING}
        self.quick_next_armed = False
        self.phase = RecordPhase.FAULT

    def _require(self, expected: RecordPhase) -> None:
        if self.phase is not expected:
            raise ApiError(
                "illegal_record_phase",
                f"Command requires phase {expected.value}, current phase is {self.phase.value}",
                status_code=409,
                details={"expected": expected.value, "actual": self.phase.value},
            )
