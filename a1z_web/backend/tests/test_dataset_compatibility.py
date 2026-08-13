from __future__ import annotations


def test_mock_resume_reports_existing_and_14d_contract(client):
    response = client.post(
        "/api/record/compatibility",
        json={"resume": True, "dataset": {"root": "datasets/existing"}},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["compatible"] is True
    assert report["existing_episodes"] == 25
    assert report["expected"]["state_dim"] == 14


def test_workflow_schema_exposes_safety_metadata(client):
    response = client.get("/api/schema/inference")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"]["properties"]["max_joint_delta"]["maximum"] == 0.5
    assert payload["ui"]["max_joint_delta"]["danger_level"] == "safety"
