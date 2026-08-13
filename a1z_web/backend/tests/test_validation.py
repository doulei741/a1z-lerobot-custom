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
