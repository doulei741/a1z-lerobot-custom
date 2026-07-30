# A1Z Single-Arm LeRobot Implementation Plan

> **For agentic workers:** Execute inline in this session. Apply strict red-green TDD for each production behavior and verify hardware-independent behavior before publishing hardware commands.

**Goal:** Add a seven-axis leader, single-CAN A1Z Robot, parameterized RGB RealSense recording, ACT training, and ACT rollout while retaining the current dual-arm workflow.

**Architecture:** Add `a1z_single` and `a1z_leader` as sibling adapters inside `a1z_lerobot`. Reuse `A1ZArm`, LeRobot cameras, datasets, training, and rollout. Make one focused upstream LeRobot record-loop fix so every Robot's returned sent action is the action stored in a dataset.

**Tech Stack:** Python 3.10+, LeRobot v0.5 tree, draccus, Feetech STS3215, GALAXEA-A1Z SDK, Intel RealSense, PyTorch ACT, pytest.

## Global Constraints

- Leader motor IDs 1–6 map to A1Z J1–J6 and ID 7 maps to the gripper.
- State/action order is `arm_0` through `arm_5`, then `gripper`.
- Arm values are radians and gripper values are normalized to `[0, 1]`.
- D435 `top_rgb` and D405 `wrist_rgb` are RGB-only, 640×480 at 30 FPS.
- Camera count is controlled by the Robot camera configuration dictionary.
- The LeRobot outer loop is 30 FPS; the A1Z SDK loop remains 250 Hz.
- Disconnect stops and disables by default; returning home requires explicit configuration.
- Preserve the existing dual-arm `a1z` implementation and user-owned `AGENTS.md` and `CLAUDE.md`.

---

### Task 1: Seven-Axis Leader Mapping

**Files:**
- Create: `a1z_lerobot/teleoperators/__init__.py`
- Create: `a1z_lerobot/teleoperators/a1z_leader/__init__.py`
- Create: `a1z_lerobot/teleoperators/a1z_leader/config_a1z_leader.py`
- Create: `a1z_lerobot/teleoperators/a1z_leader/a1z_leader.py`
- Test: `tests/test_a1z_leader.py`

**Interfaces:**
- Produces: `A1ZLeaderConfig(port, joint_signs, joint_scales, joint_offsets_rad)`.
- Produces: `map_leader_positions(raw, signs, scales, offsets) -> dict[str, float]`.
- Produces: `A1ZLeader.get_action() -> dict[str, float]`.

- [ ] Write tests that hand-check degrees-to-radians conversion, signs/scales/offsets, ID/key order, gripper normalization, and six-element configuration validation.
- [ ] Run `pytest -q tests/test_a1z_leader.py` and confirm missing-module failure.
- [ ] Implement the dataclass, pure mapping function, seven-motor bus, calibration, connect/read/disconnect lifecycle, and matching feature keys.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Single-Arm Robot Contract and Safety

**Files:**
- Modify: `a1z_lerobot/robots/a1z_follower/hardware/a1z.py`
- Modify: `a1z_lerobot/robots/a1z_follower/hardware/config.py`
- Create: `a1z_lerobot/robots/a1z_single/__init__.py`
- Create: `a1z_lerobot/robots/a1z_single/config_a1z_single.py`
- Create: `a1z_lerobot/robots/a1z_single/a1z_single.py`
- Test: `tests/test_a1z_single.py`

**Interfaces:**
- Produces: `A1Z_SINGLE_MOTORS`, `A1Z_JOINT_LIMITS`.
- Produces: `A1ZArm.get_state_normalized()` and `send_command_normalized(cmd)`.
- Produces: registered `A1ZSingleConfig` and `A1ZSingle`.

- [ ] Write tests for seven-dimensional features, 0/1/2 camera shapes, normalized gripper conversion, exact action keys, finite-value rejection, EMA, delta clipping, hard limits, returned sent action, and no-home default disconnect.
- [ ] Run the focused tests and confirm they fail for missing behavior.
- [ ] Add normalized wrapper methods without changing the existing dual-arm raw-gripper interface.
- [ ] Implement single-arm config validation and Robot lifecycle/action processing.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Persist the Actual Sent Action

**Files:**
- Modify: `lerobot/src/lerobot/scripts/lerobot_record.py`
- Create: `lerobot/tests/scripts/test_lerobot_record_sent_action.py`

**Interfaces:**
- Changes: `record_loop(...)` writes the value returned by `robot.send_action()` into the `action` dataset feature.

- [ ] Add a focused record-loop regression test using a real in-memory frame sink and a fake hardware boundary whose returned action differs from the requested action.
- [ ] Run the test and confirm it fails because the requested action is stored.
- [ ] Replace the dataset action source with `_sent_action` after `send_action()`.
- [ ] Run the regression test and relevant LeRobot script tests.

### Task 4: Registered CLI Entry Points and RealSense Defaults

**Files:**
- Create: `a1z_lerobot/scripts/teleoperate_single.py`
- Create: `a1z_lerobot/scripts/record_single.py`
- Create: `a1z_lerobot/scripts/train_act_single.py`
- Create: `a1z_lerobot/scripts/rollout_act_single.py`
- Create: `a1z_lerobot/configs/a1z_single_realsense.yaml`
- Modify: `pyproject.toml`
- Test: `tests/test_single_arm_cli.py`

**Interfaces:**
- Produces console scripts `a1z-teleoperate-single`, `a1z-record-single`, `a1z-train-act-single`, and `a1z-rollout-act-single`.
- Produces helper `default_realsense_cameras(d435_serial, d405_serial)` returning two RGB-only camera configs.

- [ ] Write tests proving local types are registered before parser use, camera defaults are 640×480@30 with depth off, serial numbers remain parameters, and each CLI accepts `--help` without hardware.
- [ ] Run focused tests and confirm missing-entry failures.
- [ ] Add thin registration wrappers and console script declarations.
- [ ] Add the reference YAML and command documentation without embedding local device serial numbers.
- [ ] Run focused tests and CLI help checks.

### Task 5: Dataset and ACT Smoke Validation

**Files:**
- Create: `tests/test_a1z_single_dataset.py`
- Create: `tests/test_a1z_single_act.py`
- Modify: `README.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Verifies: LeRobot dataset schema contains state 7, action 7, and two 480×640 RGB views.
- Verifies: ACT configuration and one CPU-sized forward/backward smoke step can consume the same feature contract.

- [ ] Write the dataset integration test with tiny generated frames and reload assertions.
- [ ] Run it and confirm any integration gap fails for the expected reason.
- [ ] Add only the minimal schema/helper correction required by the failure.
- [ ] Write and run an ACT smoke test with reduced test-only image/model sizes while retaining two visual keys and seven-dimensional state/action.
- [ ] Document calibration, camera discovery, teleoperation, recording, RTX 4060 ACT training, and rollout commands.
- [ ] Run dataset and ACT focused tests.

### Task 6: Full Verification and Handoff

**Files:**
- Verify all files changed by Tasks 1–5.

- [ ] Run root tests with `pytest -q tests`.
- [ ] Run targeted LeRobot regression tests.
- [ ] Run `python -m compileall -q a1z_lerobot`.
- [ ] Run all four new CLI `--help` checks.
- [ ] Run `git diff --check` in the root and modified submodule.
- [ ] Compare the implementation line by line with the design acceptance criteria.
- [ ] Report software evidence separately from the unexecuted real-hardware acceptance checklist.
