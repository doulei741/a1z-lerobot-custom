from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ApiError
from app.models.tasks import RecordPhase
from app.services.record_state import RecordSession


def test_record_protocol_prevents_empty_episode_and_double_commands():
    session = RecordSession(existing_episodes=25, add_episodes=15)
    assert session.phase is RecordPhase.READY
    session.apply("start_episode", "action-1")

    with pytest.raises(ApiError) as exc:
        session.apply("finish_episode", "action-2")
    assert exc.value.code == "episode_has_no_frames"

    session.note_frame()
    result = session.apply("finish_episode", "action-2")
    assert result.phase is RecordPhase.SAVING
    assert session.apply("finish_episode", "action-2") == result


def test_quick_next_waits_for_save_reset_and_health():
    session = RecordSession(existing_episodes=0, add_episodes=2)
    session.apply("start_episode", "a")
    session.note_frame()
    session.apply("quick_next", "b")
    assert session.phase is RecordPhase.SAVING
    assert session.quick_next_armed is True

    session.apply_system("saving_complete")
    assert session.phase is RecordPhase.RESETTING
    session.apply("reset_done", "c")
    assert session.phase is RecordPhase.RECORDING
    assert session.episode_index == 1


def test_fault_invalidates_unsaved_episode_and_blocks_next():
    session = RecordSession(existing_episodes=4, add_episodes=3)
    session.apply("start_episode", "start")
    session.note_frame()
    session.fault("can1 lost")

    assert session.phase is RecordPhase.FAULT
    assert session.current_episode_invalid is True
    assert session.last_trusted_episode == 3
    with pytest.raises(ApiError) as exc:
        session.apply("start_episode", "again")
    assert exc.value.code == "illegal_record_phase"


def test_rerecord_discards_buffer_and_immediately_restarts_same_index():
    session = RecordSession(existing_episodes=2, add_episodes=3)
    session.apply("start_episode", "start")
    session.note_frame()
    result = session.apply("rerecord", "retry")
    assert result.phase is RecordPhase.RECORDING
    assert session.episode_index == 0
    assert session.frames == 0


@pytest.mark.parametrize("phase", [RecordPhase.READY, RecordPhase.RECORDING, RecordPhase.RESETTING])
def test_normal_stop_is_available_outside_the_atomic_saving_phase(phase):
    session = RecordSession(existing_episodes=0, add_episodes=3, phase=phase)

    result = session.apply("stop", f"stop-{phase.value}")

    assert result.phase is RecordPhase.FINISHED


def test_normal_stop_waits_for_atomic_episode_save():
    session = RecordSession(existing_episodes=0, add_episodes=3, phase=RecordPhase.SAVING)

    with pytest.raises(ApiError) as exc:
        session.apply("stop", "stop-saving")

    assert exc.value.code == "record_busy"


def test_worker_natural_timeout_enters_saving_before_save_completion():
    session = RecordSession(existing_episodes=0, add_episodes=2)
    session.apply("start_episode", "start")

    session.begin_saving_from_worker(frames=42)
    assert session.phase is RecordPhase.SAVING
    assert session.frames == 42

    session.apply_system("saving_complete")
    assert session.phase is RecordPhase.RESETTING
    assert session.saved_episodes == 1


def test_worker_saving_event_is_idempotent_after_manual_finish():
    session = RecordSession(existing_episodes=0, add_episodes=1)
    session.apply("start_episode", "start")
    session.note_frame()
    session.apply("finish_episode", "finish")

    session.begin_saving_from_worker(frames=20)
    assert session.phase is RecordPhase.SAVING
    assert session.frames == 20


def test_recording_countdown_tracks_episode_and_clears_outside_recording():
    started = datetime(2026, 8, 14, 13, 0, tzinfo=UTC)
    session = RecordSession(existing_episodes=0, add_episodes=1, episode_time_s=60)
    session.apply("start_episode", "start", now=started)

    assert session.remaining_time_s(started + timedelta(seconds=17.2)) == 43
    session.note_frame()
    session.apply("finish_episode", "finish")
    assert session.remaining_time_s(started + timedelta(seconds=20)) is None


def test_worker_frame_count_synchronizes_exactly_and_never_moves_backwards():
    session = RecordSession(existing_episodes=0, add_episodes=1)
    session.apply("start_episode", "start")

    session.sync_frames_from_worker(1)
    session.sync_frames_from_worker(25)
    session.sync_frames_from_worker(24)

    assert session.frames == 25
