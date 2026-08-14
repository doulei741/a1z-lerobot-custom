from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[2]


def test_safe_dev_restart_scripts_are_available() -> None:
    stop_script = WEB_ROOT / "scripts" / "stop-dev.sh"
    restart_script = WEB_ROOT / "scripts" / "restart-dev.sh"

    assert stop_script.is_file()
    assert restart_script.is_file()
    assert stop_script.stat().st_mode & 0o111
    assert restart_script.stat().st_mode & 0o111

    stop_source = stop_script.read_text()
    assert "/api/tasks" in stop_source
    assert "scripts/dev.sh" in stop_source
    assert "killall" not in stop_source
    assert "pkill" not in stop_source

    restart_source = restart_script.read_text()
    assert '"${SCRIPT_DIR}/stop-dev.sh"' in restart_source
    assert 'exec "${SCRIPT_DIR}/dev.sh"' in restart_source


def test_dev_scripts_drop_foreign_conda_library_path_and_quiet_access_logs() -> None:
    scripts = [
        WEB_ROOT / "scripts" / name
        for name in ("dev.sh", "dev-backend.sh", "dev-frontend.sh", "restart-dev.sh", "stop-dev.sh")
    ]

    for script in scripts:
        assert script.read_text().splitlines()[0] == "#!/usr/bin/env -S -u LD_LIBRARY_PATH bash"

    backend_source = (WEB_ROOT / "scripts" / "dev-backend.sh").read_text()
    assert "--no-access-log" in backend_source
    assert "--log-level warning" in backend_source
