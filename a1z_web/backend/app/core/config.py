from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def discover_project_root() -> Path:
    """Find the checkout containing both A1Z integration packages."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "a1z_lerobot").is_dir() and (candidate / "GALAXEA-A1Z").is_dir():
            return candidate
    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_root: Path = Field(default_factory=discover_project_root, alias="A1Z_PROJECT_ROOT")
    conda_env: str = Field(default="lerobot-a1z", alias="A1Z_CONDA_ENV")
    mock: bool = Field(default=False, alias="A1Z_WEB_MOCK")
    allow_hardware: bool = Field(default=False, alias="A1Z_WEB_ALLOW_HARDWARE")
    data_dir: Path | None = Field(default=None, alias="A1Z_WEB_DATA_DIR")
    log_dir: Path | None = Field(default=None, alias="LOG_DIR")
    database_path: Path | None = Field(default=None, alias="DATABASE_PATH")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    graceful_stop_timeout_s: float = 8.0
    term_timeout_s: float = 3.0
    log_ring_size: int = 3000

    @field_validator("project_root", mode="before")
    @classmethod
    def replace_example_project_root(cls, value: object) -> object:
        if value is None or str(value).strip() in {"", "/path/to/a1z-lerobot"}:
            return discover_project_root()
        return value

    def model_post_init(self, __context: object) -> None:
        base = self.data_dir or self.project_root / "a1z_web" / ".runtime"
        self.data_dir = base
        self.log_dir = self.log_dir or base / "logs"
        self.database_path = self.database_path or base / "tasks.sqlite3"

    def prepare(self) -> None:
        assert self.data_dir is not None
        assert self.log_dir is not None
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.project_root / "a1z_web" / "config" / "profiles").mkdir(parents=True, exist_ok=True)
