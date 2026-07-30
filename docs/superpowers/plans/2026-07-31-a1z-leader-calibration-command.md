# A1Z Leader Calibration Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable `a1z-calibrate-leader` command that safely performs only the seven-axis Leader calibration workflow.

**Architecture:** A small script module parses `--port` and `--id`, constructs the existing `A1ZLeaderConfig` and `A1ZLeader`, then delegates calibration to `connect()`. The script owns only connection lifecycle cleanup; `A1ZLeader` continues to own all Feetech calibration behavior.

**Tech Stack:** Python 3.12, argparse, LeRobot Teleoperator API, pytest, Flit console scripts.

## Global Constraints

- The command must not import or construct `a1z_single`, connect SocketCAN, or access cameras.
- Default Leader port is `/dev/ttyACM0`; default calibration ID is `a1z_leader`.
- Reuse the existing `A1ZLeader.connect()` calibration prompts and calibration-file mechanism.
- Always disconnect an already connected Leader when command execution ends or raises.
- Hardware-free tests must use a fake Leader class and must not open a serial device.

---

### Task 1: Add a tested calibration command module and console entry point

**Files:**
- Create: `a1z_lerobot/scripts/calibrate_leader.py`
- Modify: `pyproject.toml: [project.scripts]`
- Modify: `tests/test_single_arm_cli.py`

**Interfaces:**
- Consumes: `A1ZLeaderConfig(id: str, port: str)` and `A1ZLeader(config)`.
- Produces: `build_parser() -> argparse.ArgumentParser`, `calibrate_leader(port: str, leader_id: str) -> None`, and `main() -> None`.
- Console command: `a1z-calibrate-leader = "a1z_lerobot.scripts.calibrate_leader:main"`.

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_single_arm_cli.py`. It catches a command implementation that either skips calibration connection or leaves an already-connected Leader open.

```python
def test_calibrate_leader_command_constructs_requested_leader_and_disconnects(monkeypatch):
    import a1z_lerobot.scripts.calibrate_leader as command

    events = []

    class FakeLeader:
        def __init__(self, config):
            assert config.id == "bench_leader"
            assert config.port == "/dev/ttyUSB9"
            self.is_connected = False

        def connect(self):
            self.is_connected = True
            events.append("connect")

        def disconnect(self):
            self.is_connected = False
            events.append("disconnect")

    monkeypatch.setattr(command, "A1ZLeader", FakeLeader)

    command.calibrate_leader("/dev/ttyUSB9", "bench_leader")

    assert events == ["connect", "disconnect"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n lerobot-a1z env \
  PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  python -m pytest -q tests/test_single_arm_cli.py -k calibrate_leader
```

Expected: FAIL because `a1z_lerobot.scripts.calibrate_leader` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Create `a1z_lerobot/scripts/calibrate_leader.py` with this lifecycle:

```python
import argparse

from a1z_lerobot.teleoperators.a1z_leader import A1ZLeader, A1ZLeaderConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate the seven-axis A1Z STS3215 leader only.")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--id", dest="leader_id", default="a1z_leader")
    return parser


def calibrate_leader(port: str, leader_id: str) -> None:
    leader = A1ZLeader(A1ZLeaderConfig(id=leader_id, port=port))
    try:
        leader.connect()
    finally:
        if leader.is_connected:
            leader.disconnect()


def main() -> None:
    args = build_parser().parse_args()
    calibrate_leader(args.port, args.leader_id)


if __name__ == "__main__":
    main()
```

Add this console-script entry to `pyproject.toml`:

```toml
a1z-calibrate-leader = "a1z_lerobot.scripts.calibrate_leader:main"
```

- [ ] **Step 4: Run the focused tests and command help**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n lerobot-a1z env \
  PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  python -m pytest -q tests/test_single_arm_cli.py -k calibrate_leader
conda run -n lerobot-a1z python -m a1z_lerobot.scripts.calibrate_leader --help
```

Expected: focused test PASS; help output includes `--port` and `--id`.

- [ ] **Step 5: Commit**

```bash
git add a1z_lerobot/scripts/calibrate_leader.py pyproject.toml tests/test_single_arm_cli.py
git commit -m "feat: add A1Z leader calibration command"
```

### Task 2: Document safe operator use and run full verification

**Files:**
- Modify: `README.md: 单臂 A1Z：七轴示教、双 RealSense、ACT`
- Test: `tests/test_single_arm_cli.py`

**Interfaces:**
- Consumes: installed `a1z-calibrate-leader` console command from Task 1.
- Produces: copy-paste command and explicit guarantee that it does not connect A1Z, CAN, or cameras.

- [ ] **Step 1: Add the README command block**

Add this immediately before the low-speed teleoperation command:

```markdown
先单独校准 Leader；此命令只访问 `/dev/ttyACM0` 上的 STS3215，不连接 A1Z、CAN 或相机：

```bash
a1z-calibrate-leader --port=/dev/ttyACM0 --id=a1z_leader
```

首次运行按提示选择重校准，手动摆动 `arm_0..arm_4` 与夹爪；`arm_5` 保持不动并按全圈关节校准。
```

- [ ] **Step 2: Run the complete software verification**

Run:

```bash
conda run -n lerobot-a1z python -m pip install --no-deps -e .
conda run -n lerobot-a1z python -m pip check
PYTHONDONTWRITEBYTECODE=1 conda run -n lerobot-a1z env \
  PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest -q \
    tests/test_a1z_single.py tests/test_a1z_leader.py tests/test_single_arm_cli.py \
    tests/test_a1z_single_dataset.py tests/test_a1z_single_act.py \
    lerobot/tests/scripts/test_lerobot_record_sent_action.py lerobot/tests/test_rollout.py
for command in a1z-calibrate-leader a1z-teleoperate-single a1z-record-single \
  a1z-train-act-single a1z-rollout-act-single; do
  conda run -n lerobot-a1z "$command" --help >/dev/null
done
git diff --check
```

Expected: `pip check` reports no broken requirements, all tests pass, every command exits with status 0, and `git diff --check` has no output.

- [ ] **Step 3: Commit documentation**

```bash
git add README.md
git commit -m "docs: add leader calibration command"
```
