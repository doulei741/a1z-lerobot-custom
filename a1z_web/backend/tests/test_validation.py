import pytest
from pydantic import ValidationError

from app.schemas.workflows import InferenceRequest, RecordingRequest, TeleoperationRequest


def test_joint_mapping_requires_exactly_six_finite_values():
    with pytest.raises(ValidationError):
        TeleoperationRequest.model_validate({"left_mapping": {"signs": [1, 1]}})
    with pytest.raises(ValidationError):
        TeleoperationRequest.model_validate(
            {"left_mapping": {"offsets_rad": [0, 0, 0, 0, 0, float("nan")]}}
        )


def test_dataset_and_policy_paths_reject_shell_like_or_traversal_values():
    with pytest.raises(ValidationError):
        RecordingRequest.model_validate({"dataset": {"repo_id": "local/x; touch /tmp/x"}})
    with pytest.raises(ValidationError):
        InferenceRequest.model_validate({"policy_path": "../../etc/passwd"})


def test_act_inference_locks_gripper_start_hold_false():
    request = InferenceRequest.model_validate({"policy_path": "outputs/model/checkpoints/last"})
    assert request.gripper_start_hold is False
    with pytest.raises(ValidationError):
        InferenceRequest.model_validate(
            {"policy_path": "outputs/model/checkpoints/last", "gripper_start_hold": True}
        )


def test_verified_mapping_defaults_are_mode_specific():
    dual = TeleoperationRequest()
    single = TeleoperationRequest(mode="single")
    assert dual.left_mapping.offsets_rad[1] == pytest.approx(1.676119148)
    assert dual.right_mapping.offsets_rad[2] == pytest.approx(-1.971852804)
    assert single.left_mapping.signs == [-1, 1, 1, 1, 1, -1]
    assert single.left_mapping.offsets_rad[1] == pytest.approx(1.567886653)


def test_operator_workflows_default_to_absolute_gripper_mapping():
    assert TeleoperationRequest().gripper_start_hold is False
    assert RecordingRequest().gripper_start_hold is False


def test_recording_accepts_bounded_writer_and_encoder_tuning():
    request = RecordingRequest.model_validate({
        "dataset": {
            "num_image_writer_processes": 1,
            "num_image_writer_threads_per_camera": 6,
            "video_encoding_batch_size": 4,
            "streaming_encoding": True,
            "encoder_queue_maxsize": 90,
            "encoder_threads": 3,
            "camera_encoder": {"vcodec": "libsvtav1", "crf": 26, "preset": 10, "g": 4},
        },
        "play_sounds": True,
    })

    assert request.dataset.num_image_writer_processes == 1
    assert request.dataset.streaming_encoding is True
    assert request.dataset.camera_encoder.crf == 26
    assert request.play_sounds is True

    with pytest.raises(ValidationError):
        RecordingRequest.model_validate({"dataset": {"encoder_queue_maxsize": 0}})
