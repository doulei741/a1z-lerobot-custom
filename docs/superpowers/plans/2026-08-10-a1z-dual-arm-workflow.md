# A1Z Dual-Arm Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete dual-A1Z LeRobot workflow for two seven-servo leaders, two followers, three 480p RGB RealSense cameras, recording, ACT training, and rollout while preserving every existing single-arm interface and behavior.

**Architecture:** Compose two existing `A1ZLeader` objects behind a new `BiA1ZLeader` teleoperator and reuse the existing `a1z` dual follower. Extend only the dual follower with safe lifecycle and gripper-start behavior, then expose native LeRobot functionality through thin dual CLI wrappers and YAML files.

**Tech Stack:** Python 3.12, LeRobot v3, draccus dataclass configuration, Feetech STS3215, GALAXEA A1Z SDK, SocketCAN, Intel RealSense, pytest.

## Global Constraints

- Existing single-arm classes, commands, YAML files, calibration files, mapping values, and behavior remain unchanged.
- Left follower uses `can0`; right follower uses `can1`.
- Each leader uses servo IDs 1–7 on a distinct serial bus and has an independent calibration ID and mapping.
- Dual state/action order is left six joints, left gripper, right six joints, right gripper.
- Default cameras are `top_rgb`, `left_wrist_rgb`, and `right_wrist_rgb`, all RGB 640×480@30 with depth disabled.
- The dual follower retains raw-radian gripper features for compatibility with existing dual datasets and the HDF5 converter.
- Dual disconnect does not move home or open grippers unless explicitly enabled.
- No automated test connects physical hardware.

---

### Task 1: Compose Two A1Z Leaders

**Files:**
- Create: `a1z_lerobot/teleoperators/bi_a1z_leader/__init__.py`
- Create: `a1z_lerobot/teleoperators/bi_a1z_leader/config_bi_a1z_leader.py`
- Create: `a1z_lerobot/teleoperators/bi_a1z_leader/bi_a1z_leader.py`
- Create: `tests/test_bi_a1z_leader.py`

**Interfaces:**
- Consumes: `A1ZLeader`, `A1ZLeaderConfig`, and normalized single-leader `gripper.pos`.
- Produces: registered teleoperator type `bi_a1z_leader` and ordered 14-key `RobotAction` compatible with `A1Z_DUAL.motors`.

- [ ] **Step 1: Write failing tests for registration, independent nested configuration, exact keys, conversion, and cleanup**

```python
def test_bi_leader_maps_two_single_actions_to_dual_contract():
    left = {**{f"arm_{i}.pos": float(i) for i in range(6)}, "gripper.pos": 0.0}
    right = {**{f"arm_{i}.pos": float(i + 10) for i in range(6)}, "gripper.pos": 1.0}
    action = compose_dual_action(left, right)
    assert list(action) == [f"{m}.pos" for m in A1Z_DUAL.motors]
    assert action["left_ee_0.pos"] == pytest.approx(GRIPPER_CLOSE_RAD)
    assert action["right_ee_0.pos"] == pytest.approx(GRIPPER_OPEN_RAD)
```

Also assert duplicate ports raise `ValueError`, nested mapping values reach the correct child, right-connect failure disconnects the already-connected left child, and both children use motor IDs 1–7 through the existing `A1ZLeader` implementation.

- [ ] **Step 2: Run the new test and verify it fails because the package does not exist**

Run:

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_bi_a1z_leader.py
```

Expected: import failure for `a1z_lerobot.teleoperators.bi_a1z_leader`.

- [ ] **Step 3: Implement the registered config and composition helper**

```python
@TeleoperatorConfig.register_subclass("bi_a1z_leader")
@dataclass
class BiA1ZLeaderConfig(TeleoperatorConfig):
    left_arm_config: A1ZLeaderConfig
    right_arm_config: A1ZLeaderConfig

    def __post_init__(self):
        if self.left_arm_config.port == self.right_arm_config.port:
            raise ValueError("left and right A1Z leaders must use different serial ports")
```

`compose_dual_action(left, right)` validates both single-arm key sets, prefixes joint keys, renames `gripper.pos` to `left_ee_0.pos`/`right_ee_0.pos`, and converts normalized grippers with `GRIPPER_CLOSE_RAD + value * (GRIPPER_OPEN_RAD - GRIPPER_CLOSE_RAD)`.

- [ ] **Step 4: Implement `BiA1ZLeader` lifecycle and action features**

Construct each `A1ZLeader` directly from its nested config so calibration IDs and mappings remain independent. Connect left then right; on right failure disconnect left. Disconnect both sides even if one raises, reporting the first error after cleanup.

- [ ] **Step 5: Run the new tests and existing leader tests**

Run:

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_bi_a1z_leader.py tests/test_a1z_leader.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add a1z_lerobot/teleoperators/bi_a1z_leader tests/test_bi_a1z_leader.py
git commit -m "feat: add bimanual A1Z leader"
```

### Task 2: Make the Existing Dual Follower Safe for Teleoperation

**Files:**
- Modify: `a1z_lerobot/robots/a1z_follower/config_a1z_follower.py`
- Modify: `a1z_lerobot/robots/a1z_follower/a1z_follower.py`
- Create: `tests/test_a1z_dual.py`

**Interfaces:**
- Consumes: raw-radian 14D dual actions from `BiA1ZLeader` or a policy.
- Produces: actual-sent 14D action with EMA, joint clipping, independent gripper startup hold, safe connection cleanup, and configurable exit movement.

- [ ] **Step 1: Write failing dual follower tests**

Tests use fake `A1ZDualArm` and cameras and assert:

```python
config = A1ZConfig(
    gripper_start_hold=True,
    return_home_on_disconnect=False,
    open_grippers_on_disconnect=False,
)
```

The first action keeps indices 6 and 13 at the measured follower values; subsequent deltas are independent. Default disconnect calls `stop()` but not `move_to_home()` or `command_gripper()`. Opt-in flags perform those actions. Arm/camera connection failures clean up resources already started.

- [ ] **Step 2: Run the dual test and verify missing config fields fail**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_a1z_dual.py
```

Expected: `A1ZConfig` rejects the new keyword arguments.

- [ ] **Step 3: Add dual safety configuration**

```python
gripper_start_hold: bool = True
return_home_on_disconnect: bool = False
open_grippers_on_disconnect: bool = False
```

- [ ] **Step 4: Implement independent gripper references and robust lifecycle cleanup**

Store initial follower gripper positions and first commanded leader gripper values for indices 6 and 13. Before EMA, replace each gripper target with `clip(follower_start + current - leader_start, GRIPPER_CLOSE_RAD, GRIPPER_OPEN_RAD)`. Reset references on disconnect. Make connect/disconnect cleanup symmetrical and conditionalize exit motion on the new flags.

- [ ] **Step 5: Add dual policy feature validation**

Reject non-14D state/action policies and incompatible visual keys before `robot.connect()` can send policy actions. Use the same validation shape rules as `a1z_single`, parameterized for 14D and configured camera names.

- [ ] **Step 6: Run dual and single follower regression tests**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_a1z_dual.py tests/test_a1z_single.py
```

Expected: all tests pass and no single-arm source file changes.

- [ ] **Step 7: Commit**

```bash
git add a1z_lerobot/robots/a1z_follower tests/test_a1z_dual.py
git commit -m "fix: make dual A1Z lifecycle safe"
```

### Task 3: Add Dual CLI Wrappers and RealSense Configurations

**Files:**
- Create: `a1z_lerobot/scripts/teleoperate_dual.py`
- Create: `a1z_lerobot/scripts/record_dual.py`
- Create: `a1z_lerobot/scripts/train_act_dual.py`
- Create: `a1z_lerobot/scripts/rollout_act_dual.py`
- Create: `a1z_lerobot/configs/record_a1z_dual_realsense.yaml`
- Create: `a1z_lerobot/configs/a1z_dual_realsense.yaml`
- Modify: `pyproject.toml`
- Create: `tests/test_dual_arm_cli.py`

**Interfaces:**
- Consumes: registered `a1z` robot and `bi_a1z_leader` teleoperator.
- Produces: four console commands and two parseable YAML configurations.

- [ ] **Step 1: Write failing wrapper and YAML parsing tests**

Assert the registered choices are `a1z` and `bi_a1z_leader`, YAML parses two CAN channels, two distinct leader ports/IDs, three camera keys, `(640, 480, 30)`, and `use_depth is False`. Assert wrappers call the native LeRobot main functions and dual ACT defaults remain overrideable.

- [ ] **Step 2: Run the CLI tests and verify missing modules/commands fail**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_dual_arm_cli.py
```

- [ ] **Step 3: Implement thin wrappers**

Each teleoperate/record wrapper imports `a1z_lerobot.robots.a1z_follower` and `a1z_lerobot.teleoperators.bi_a1z_leader` before calling the corresponding native LeRobot main. Training applies `policy.type=act`, `policy.device=cuda`, and `batch_size=8` only when absent. Rollout imports the dual robot before native rollout.

- [ ] **Step 4: Register console scripts**

```toml
a1z-teleoperate-dual = "a1z_lerobot.scripts.teleoperate_dual:main"
a1z-record-dual = "a1z_lerobot.scripts.record_dual:main"
a1z-train-act-dual = "a1z_lerobot.scripts.train_act_dual:main"
a1z-rollout-act-dual = "a1z_lerobot.scripts.rollout_act_dual:main"
```

- [ ] **Step 5: Add the two three-camera YAML files**

Use `top_rgb`, `left_wrist_rgb`, and `right_wrist_rgb`, each `intelrealsense`, 640×480@30, `color_mode: rgb`, and `use_depth: false`. Use known serials for top and one wrist. Set the second wrist serial to the exact sentinel `CONFIGURE_RIGHT_D405_SERIAL`; validation rejects it until overridden.

- [ ] **Step 6: Run CLI tests and help smoke tests**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_dual_arm_cli.py
python -m a1z_lerobot.scripts.teleoperate_dual --help
python -m a1z_lerobot.scripts.record_dual --help
python -m a1z_lerobot.scripts.rollout_act_dual --help
```

Expected: all tests pass and each help command exits zero without hardware.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml a1z_lerobot/scripts a1z_lerobot/configs tests/test_dual_arm_cli.py
git commit -m "feat: add dual A1Z workflow commands"
```

### Task 4: Verify the Dual LeRobot Dataset and ACT Contract

**Files:**
- Create: `tests/test_a1z_dual_dataset.py`
- Create: `tests/test_a1z_dual_act.py`
- Modify: `a1z_lerobot/robots/a1z_follower/a1z_follower.py`

**Interfaces:**
- Consumes: dual robot hardware features and three RGB frames.
- Produces: a validated LeRobot v3 dataset and policy contract with 14D state/action and three visual keys.

- [ ] **Step 1: Write the failing dataset round-trip test**

Create a temporary no-video dataset from `hw_to_dataset_features`, add two frames with `observation.state.shape == (14,)`, `action.shape == (14,)`, and three `(480, 640, 3)` uint8 arrays, finalize, reload, and assert feature names/order match `A1Z_DUAL.motors` with `.pos` suffixes.

- [ ] **Step 2: Write failing policy feature validation tests**

Use minimal fake ACT configurations and assert valid 14D/three-camera features pass, while 7D state, 7D action, a missing wrist key, and an unexpected camera set raise descriptive `ValueError` before hardware connection.

- [ ] **Step 3: Run both tests and confirm the intended failures**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q tests/test_a1z_dual_dataset.py tests/test_a1z_dual_act.py
```

- [ ] **Step 4: Complete dual feature validation with exact 14D and visual-key checks**

Keep validation pure and callable from `A1Z.validate_policy_features(policy_config)`. Do not change `A1ZSingle.validate_policy_features`.

- [ ] **Step 5: Run dataset, ACT, and native LeRobot rollout/record regressions**

```bash
PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" pytest -q \
  tests/test_a1z_dual_dataset.py tests/test_a1z_dual_act.py \
  lerobot/tests/scripts/test_lerobot_record_sent_action.py lerobot/tests/test_rollout.py
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_a1z_dual_dataset.py tests/test_a1z_dual_act.py a1z_lerobot/robots/a1z_follower/a1z_follower.py
git commit -m "test: verify dual A1Z dataset and ACT contract"
```

### Task 5: Document Bring-Up and Run Final Verification

**Files:**
- Modify: `README.md`
- Create: `docs/a1z-dual-arm-commands.md`

**Interfaces:**
- Consumes: all new commands and configurations.
- Produces: an exact staged hardware procedure and final automated evidence.

- [ ] **Step 1: Document two-leader calibration and CAN setup**

Include exact commands for distinct `/dev/ttyACM0` and `/dev/ttyACM1` calibration IDs, `can0`/`can1` setup, five-second no-camera teleoperation, camera discovery, one-episode visual check, production recording, ACT training, and ten-second rollout.

- [ ] **Step 2: Document the right-D405 override and safety controls**

State that `CONFIGURE_RIGHT_D405_SERIAL` must be replaced with the output of `lerobot-find-cameras realsense`, and explain `gripper_start_hold`, `return_home_on_disconnect`, and `open_grippers_on_disconnect`.

- [ ] **Step 3: Run formatting and complete regression suite**

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/lerobot/src:$PWD/GALAXEA-A1Z:$PWD" \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/test_a1z_single.py tests/test_a1z_leader.py tests/test_single_arm_cli.py \
  tests/test_a1z_single_dataset.py tests/test_a1z_single_act.py \
  tests/test_bi_a1z_leader.py tests/test_a1z_dual.py tests/test_dual_arm_cli.py \
  tests/test_a1z_dual_dataset.py tests/test_a1z_dual_act.py \
  lerobot/tests/scripts/test_lerobot_record_sent_action.py lerobot/tests/test_rollout.py
```

Expected: all tests pass, including the original 57 tests.

- [ ] **Step 4: Verify package and CLI installation contract**

```bash
python -m pip check
python -m a1z_lerobot.scripts.teleoperate_dual --help
python -m a1z_lerobot.scripts.record_dual --help
python -m a1z_lerobot.scripts.train_act_dual --help
python -m a1z_lerobot.scripts.rollout_act_dual --help
```

- [ ] **Step 5: Commit documentation**

```bash
git add README.md docs/a1z-dual-arm-commands.md
git commit -m "docs: add dual A1Z bring-up guide"
```

- [ ] **Step 6: Push the completed feature branch**

```bash
git push -u origin feature/dual-arm-workflow
```

The branch remains separate from `main` until real-hardware acceptance.
