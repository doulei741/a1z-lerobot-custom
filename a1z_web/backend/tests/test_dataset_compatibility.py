from types import SimpleNamespace

from app.schemas.workflows import RecordingRequest
from app.services.workflows import DatasetCompatibilityService


def test_new_dataset_rejects_an_existing_root_before_starting_worker(tmp_path) -> None:
    existing = tmp_path / "datasets" / "already-there"
    existing.mkdir(parents=True)
    service = DatasetCompatibilityService(SimpleNamespace(project_root=tmp_path, mock=False))
    payload = RecordingRequest(
        safety_confirmed=True,
        dataset={"root": "datasets/already-there", "repo_id": "local/already-there"},
    )

    report = service.inspect(payload)

    assert report["compatible"] is False
    assert report["checks"]["new_dataset_path_available"] is False
    assert report["reason"] == "dataset_root_exists"
