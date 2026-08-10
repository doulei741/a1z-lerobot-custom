# Dual A1Z J2 Direction and Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct both dual Leader J2 mappings and bound dual follower actions before command history is updated.

**Architecture:** Reuse the existing six-axis A1Z limit table for each arm slice of the 14D action. Keep hardware mapping in the dual YAML and copy-paste command guide; do not change single-arm configuration.

**Tech Stack:** Python 3.12, NumPy, draccus YAML configuration, pytest.

## Global Constraints

- Do not change single-arm mapping or behavior.
- Change only J2 sign and J2 offset for the two approved dual Leader/Follower pairs.
- Clamp dual arm joints before `_prev_action` is updated or the SDK is called.
- Do not alter gripper processing.

---

### Task 1: Bound Dual Actions Before State Update

**Files:**
- Modify: `a1z_lerobot/robots/a1z_follower/a1z_follower.py`
- Test: `tests/test_a1z_dual.py`

**Interfaces:**
- Consumes: `A1Z_JOINT_LIMITS`, 14D order `[left j1..j6, left gripper, right j1..j6, right gripper]`.
- Produces: bounded action returned, stored in `_prev_action`, and passed to `arm.send_command()`.

- [ ] Add a failing integration test that sends out-of-range left/right J2 and J3 values, then sends a valid J2 value and asserts no invalid command history remains.
- [ ] Run the focused test and confirm it fails because the dual adapter currently returns and stores out-of-range values.
- [ ] Import `A1Z_JOINT_LIMITS` and clamp slices `0:6` and `7:13` after EMA/delta limiting and before logging/state/send.
- [ ] Run `tests/test_a1z_dual.py` and confirm it passes.

### Task 2: Apply Both J2 Pair Mappings

**Files:**
- Modify: `a1z_lerobot/configs/record_a1z_dual_realsense.yaml`
- Modify: `docs/a1z-dual-arm-commands.md`
- Test: `tests/test_dual_arm_cli.py`

**Interfaces:**
- Produces left/right signs `[-1,-1,1,1,1,-1]` and J2 offsets `1.676119148` / `1.672050437`.

- [ ] Change the YAML expectations first and confirm the focused CLI test fails against the old configuration.
- [ ] Update the dual YAML and every complete dual command in the guide; leave all non-J2 values unchanged.
- [ ] Run the focused dual CLI tests.
- [ ] Run `git diff --check`, help/parse checks, and the complete single/dual regression suite.
- [ ] Commit and push `feature/dual-arm-workflow`, then verify the remote hash equals local HEAD.
