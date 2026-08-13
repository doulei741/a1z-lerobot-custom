from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["A1Z_WEB_MOCK"] = "1"
os.environ["A1Z_WEB_ALLOW_HARDWARE"] = "0"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("A1Z_WEB_DATA_DIR", str(tmp_path))
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
