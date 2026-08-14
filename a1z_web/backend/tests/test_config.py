from __future__ import annotations

from app.core.config import Settings, discover_project_root


def test_example_project_root_placeholder_uses_auto_discovery() -> None:
    settings = Settings(A1Z_PROJECT_ROOT="/path/to/a1z-lerobot")

    assert settings.project_root == discover_project_root()

