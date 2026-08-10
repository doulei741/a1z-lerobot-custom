# A1Z Leader Joint Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable, follower-free command that prints selected Leader joint deltas and replaces multiline inline Python diagnostics.

**Architecture:** A small tool module owns argument validation, the sampling loop, output formatting, and cleanup. The hardware-independent core accepts an existing Leader plus injected clock, sleep, and output callables; `main()` supplies the real `A1ZLeader` and standard-library functions.

**Tech Stack:** Python 3.12, `argparse`, existing `A1ZLeader`, pytest.

## Global Constraints

- Never construct or connect an A1Z Follower, CAN interface, camera, recorder, or dataset.
- Connect the Leader with `calibrate=False` and always disconnect it in `finally`.
- Default to joint indices `[1, 2]`, duration `30` seconds, and threshold `0.02` rad.
- Reject non-positive duration/threshold and duplicate or out-of-range joint indices before hardware connection.
- Preserve read failures after cleanup; treat `Ctrl+C` as an operator-requested normal stop.

---

### Task 1: Diagnostic Core and CLI

**Files:**
- Create: `a1z_lerobot/tools/diagnose_leader_joints.py`
- Create: `tests/test_diagnose_leader_joints.py`

**Interfaces:**
- Consumes: `A1ZLeader`, `A1ZLeaderConfig`, and action keys `arm_0.pos..arm_5.pos`.
- Produces: `validate_joint_indices(indices: list[int]) -> tuple[int, ...]`, `format_joint_line(action, deltas, joint_indices) -> str`, `observe_joint_deltas(leader, *, joint_indices, duration_s, threshold_rad, monotonic, sleep, output) -> str`, `run_diagnostic(port, leader_id, *, duration_s, threshold_rad, joint_indices, leader_factory, monotonic, sleep, output) -> str`, `build_parser() -> argparse.ArgumentParser`, and `main() -> None`.

- [ ] **Step 1: Write failing validation and sampling tests**

Create tests that require these behaviors:

```python
def test_validate_joint_indices_accepts_unique_zero_based_joints():
    assert validate_joint_indices([1, 2]) == (1, 2)


@pytest.mark.parametrize("indices", [[1, 1], [-1], [6], []])
def test_validate_joint_indices_rejects_invalid_values(indices):
    with pytest.raises(ValueError):
        validate_joint_indices(indices)


def test_observer_prints_only_threshold_crossings():
    actions = [
        {"arm_1.pos": 0.00, "arm_2.pos": 0.00},
        {"arm_1.pos": 0.01, "arm_2.pos": 0.00},
        {"arm_1.pos": 0.03, "arm_2.pos": -0.04},
    ]
    output = []
    status = observe_joint_deltas(
        SequenceLeader(actions),
        joint_indices=(1, 2),
        duration_s=0.2,
        threshold_rad=0.02,
        monotonic=StepClock(0.1),
        sleep=lambda _: None,
        output=output.append,
    )
    assert status == "completed"
    assert any("delta_J2=+0.030" in line and "delta_J3=-0.040" in line for line in output)
    assert not any("+0.010" in line for line in output)
```

- [ ] **Step 2: Run tests and verify the module-missing failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -q tests/test_diagnose_leader_joints.py
```

Expected: collection fails because `a1z_lerobot.tools.diagnose_leader_joints` does not exist.

- [ ] **Step 3: Implement validation and the sampling loop**

Implement the core with exact signatures:

```python
def validate_joint_indices(indices: list[int]) -> tuple[int, ...]:
    result = tuple(indices)
    if not result or len(set(result)) != len(result) or any(index not in range(6) for index in result):
        raise ValueError("joint indices must be unique values in 0..5")
    return result


def observe_joint_deltas(
    leader,
    *,
    joint_indices: tuple[int, ...],
    duration_s: float,
    threshold_rad: float,
    monotonic,
    sleep,
    output,
) -> str:
    baseline = leader.get_action()
    last_printed = {index: 0.0 for index in joint_indices}
    started = monotonic()
    while monotonic() - started < duration_s:
        action = leader.get_action()
        deltas = {
            index: float(action[f"arm_{index}.pos"] - baseline[f"arm_{index}.pos"])
            for index in joint_indices
        }
        if any(abs(deltas[index] - last_printed[index]) >= threshold_rad for index in joint_indices):
            output(format_joint_line(action, deltas, joint_indices))
            last_printed = deltas
        sleep(0.05)
    return "completed"
```

Validate `duration_s` and `threshold_rad` as positive before the baseline read.

- [ ] **Step 4: Write failing lifecycle tests**

Cover normal completion, `KeyboardInterrupt`, and read failure:

```python
def test_run_diagnostic_connects_without_calibration_and_disconnects():
    events = []
    leader = FakeLeader(events=events, actions=[zero_action(), zero_action()])
    status = run_diagnostic(
        "/dev/ttyUSB9",
        "bench_leader",
        duration_s=0.1,
        threshold_rad=0.02,
        joint_indices=(1, 2),
        leader_factory=lambda config: leader,
        monotonic=StepClock(0.1),
        sleep=lambda _: None,
        output=lambda _: None,
    )
    assert status == "completed"
    assert events[0] == ("connect", False)
    assert events[-1] == "disconnect"


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), RuntimeError("read failed")])
def test_run_diagnostic_always_disconnects(failure):
    leader = FailingLeader(failure)
    kwargs = {
        "duration_s": 0.1,
        "threshold_rad": 0.02,
        "joint_indices": (1, 2),
        "leader_factory": lambda config: leader,
        "monotonic": StepClock(0.1),
        "sleep": lambda _: None,
        "output": lambda _: None,
    }
    if isinstance(failure, KeyboardInterrupt):
        assert run_diagnostic("/dev/ttyUSB9", "bench_leader", **kwargs) == "interrupted"
    else:
        with pytest.raises(RuntimeError, match="read failed"):
            run_diagnostic("/dev/ttyUSB9", "bench_leader", **kwargs)
    assert leader.disconnect_calls == 1
```

- [ ] **Step 5: Implement hardware lifecycle and CLI**

`run_diagnostic()` constructs `A1ZLeaderConfig(id=leader_id, port=port)`, connects with
`calibrate=False`, calls the observer, catches only `KeyboardInterrupt`, and disconnects in `finally`
when connected. `build_parser()` exposes the five approved arguments. `main()` prints the final status
and exits without swallowing non-interrupt failures.

- [ ] **Step 6: Run focused and existing Leader tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -q \
  tests/test_diagnose_leader_joints.py \
  tests/test_a1z_leader.py \
  tests/test_bi_a1z_leader.py \
  tests/test_single_arm_cli.py
```

Expected: all selected tests pass without hardware access.

- [ ] **Step 7: Commit the tested tool**

```bash
git add a1z_lerobot/tools/diagnose_leader_joints.py
git add -f tests/test_diagnose_leader_joints.py
git commit -m "feat: add Leader joint diagnostic tool"
```

### Task 2: Complete Commands and Final Verification

**Files:**
- Modify: `docs/a1z-dual-arm-commands.md`

**Interfaces:**
- Consumes: `python -m a1z_lerobot.tools.diagnose_leader_joints` from Task 1.
- Produces: complete copy-paste commands for the current left and right Leaders.

- [ ] **Step 1: Add complete left and right diagnostic commands**

Document these exact invocations without heredocs or inline Python:

```bash
python -m a1z_lerobot.tools.diagnose_leader_joints \
  --port=/dev/ttyACM0 \
  --id=a1z_left_leader \
  --duration-s=30 \
  --threshold-rad=0.02 \
  --joint-indices=1 2

python -m a1z_lerobot.tools.diagnose_leader_joints \
  --port=/dev/ttyACM1 \
  --id=a1z_right_leader \
  --duration-s=30 \
  --threshold-rad=0.02 \
  --joint-indices=1 2
```

Explain that the operator moves physical joint 2 alone, returns it, then moves physical joint 3 alone;
the script never connects a Follower.

- [ ] **Step 2: Verify help, formatting, and the complete regression suite**

Run:

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  python -m a1z_lerobot.tools.diagnose_leader_joints --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/test_a1z_single.py tests/test_a1z_leader.py tests/test_single_arm_cli.py \
  tests/test_a1z_single_dataset.py tests/test_a1z_single_act.py \
  tests/test_bi_a1z_leader.py tests/test_a1z_dual.py tests/test_dual_arm_cli.py \
  tests/test_a1z_dual_dataset.py tests/test_a1z_dual_act.py \
  tests/test_diagnose_leader_joints.py \
  lerobot/tests/scripts/test_lerobot_record_sent_action.py lerobot/tests/test_rollout.py
```

Expected: help exits zero and the prior 80 tests plus the new diagnostic tests all pass.

- [ ] **Step 3: Commit documentation and push the feature branch**

```bash
git add -f docs/a1z-dual-arm-commands.md
git commit -m "docs: add Leader joint diagnostic commands"
git push https://github.com/doulei741/a1z-lerobot-custom.git feature/dual-arm-workflow
```
