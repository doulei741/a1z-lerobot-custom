# A1Z Dual-Arm LeRobot Workflow Design

## Goal

Extend the existing, hardware-validated single-arm A1Z workflow with a complete dual-arm workflow for calibration, teleoperation, LeRobot v3 recording, ACT training, and ACT rollout. Existing single-arm classes, command names, configuration files, feature names, calibration files, and behavior remain unchanged.

## Hardware Contract

- Left follower A1Z uses `can0`; right follower A1Z uses `can1`.
- The left and right leaders each contain seven STS3215 servos with IDs 1 through 7. Reusing IDs is valid because the leaders are connected to independent serial buses.
- Each leader has its own serial port, calibration ID, calibration file, joint signs, joint scales, and joint offsets.
- Default visual inputs are RGB only:
  - `top_rgb`: Intel RealSense D435, 640×480 at 30 FPS.
  - `left_wrist_rgb`: Intel RealSense D405, 640×480 at 30 FPS.
  - `right_wrist_rgb`: Intel RealSense D405, 640×480 at 30 FPS.
- Depth is disabled for all three cameras.
- Camera count remains configurable through the existing `robot.cameras` dictionary. Recording and rollout must use the same camera keys as training.

The known D435 serial is `025222071608`; the known D405 serial is `260522273365`. The second D405 serial is hardware-specific and must be supplied in the dual-arm YAML or as a CLI override before real-hardware use.

## Architecture

### Dual Leader Composition

Add a `bi_a1z_leader` LeRobot teleoperator that composes two existing `A1ZLeader` instances. It does not duplicate STS3215 bus, calibration, or joint-mapping logic.

Each nested leader configuration carries its own:

- `id`
- `port`
- `calibration_dir`
- `joint_signs`
- `joint_scales`
- `joint_offsets_rad`

The dual leader connects and disconnects both sides with partial-failure cleanup. Its 14 output keys exactly match the existing dual follower contract and preserve this order:

```text
left_arm_0.pos
left_arm_1.pos
left_arm_2.pos
left_arm_3.pos
left_arm_4.pos
left_arm_5.pos
left_ee_0.pos
right_arm_0.pos
right_arm_1.pos
right_arm_2.pos
right_arm_3.pos
right_arm_4.pos
right_arm_5.pos
right_ee_0.pos
```

The six joint values per side remain radians. Each single leader reports its gripper as normalized `[0, 1]`; the dual leader converts that value to the existing dual follower gripper-radian convention at `left_ee_0.pos` and `right_ee_0.pos`. This preserves compatibility with the current `A1ZDualArm` adapter and HDF5 converter.

### Dual Follower Safety

Keep the existing registered robot type `a1z` and its 14D ordering. Add only dual-specific safety and lifecycle behavior:

- `gripper_start_hold`: when enabled, each follower gripper begins from its measured opening and follows subsequent leader deltas instead of jumping to the leader's initial absolute opening.
- `return_home_on_disconnect`: default `false`.
- `open_grippers_on_disconnect`: default `false`.
- If the second arm or any camera fails to connect, already-connected arms and cameras are stopped or disconnected in reverse order.
- Disconnect attempts every cleanup step and reports the first error only after all resources have been given a cleanup attempt.

EMA and per-frame joint-delta clipping retain their current meaning. Only the twelve arm joints are delta-clipped; the two grippers remain unclipped.

### CLI Commands

Add four dual-arm commands without modifying the existing single-arm commands:

- `a1z-teleoperate-dual`: native LeRobot teleoperation with `a1z` and `bi_a1z_leader` registered.
- `a1z-record-dual`: native LeRobot v3 recording with Rerun, episode reset, rerecord, early-finish, and actual-sent-action recording.
- `a1z-train-act-dual`: native ACT training with the same RTX 4060 defaults as the single-arm wrapper (`cuda`, batch size 8 unless overridden).
- `a1z-rollout-act-dual`: native LeRobot rollout with `a1z` registered.

The existing commands `a1z-calibrate-leader`, `a1z-teleoperate-single`, `a1z-record-single`, `a1z-train-act-single`, and `a1z-rollout-act-single` retain their current behavior and arguments.

### Configuration

Add two dual-arm YAML files:

- `record_a1z_dual_realsense.yaml`: `can0`, `can1`, two independently configured leaders, three 480p RGB RealSense cameras, Rerun enabled, local-only LeRobot v3 recording, and safe startup/exit defaults.
- `a1z_dual_realsense.yaml`: the same robot and camera feature contract for ACT rollout, Rerun disabled by default, and no automatic home motion on exit.

The second D405 serial is represented by an explicit invalid sentinel in the checked-in YAML. The configuration must fail with a clear message until the caller replaces or overrides it with the detected serial; it must never silently select one of two identical D405 devices by product name.

## Data Contract

Dual-arm datasets have:

- `robot_type`: `a1z`
- `observation.state`: float32 shape `(14,)`
- `action`: float32 shape `(14,)`
- `observation.images.top_rgb`: video shape `(480, 640, 3)`
- `observation.images.left_wrist_rgb`: video shape `(480, 640, 3)`
- `observation.images.right_wrist_rgb`: video shape `(480, 640, 3)`

State and action names use the exact ordered 14-key contract above. Recording stores the dictionary returned by `Robot.send_action()`, so EMA, joint-delta clipping, gripper startup hold, and physical conversion are reflected in training labels.

ACT training and rollout must use identical state size, action size, camera keys, and image shapes. Rollout validates the policy feature contract before sending any policy action to the robot.

## Calibration and Hardware Bring-Up

The existing single-leader calibration command is run twice with distinct IDs and ports:

```bash
a1z-calibrate-leader --port=/dev/ttyACM0 --id=a1z_left_leader
a1z-calibrate-leader --port=/dev/ttyACM1 --id=a1z_right_leader
```

The checked-in mapping values are safe starting defaults only for the already-validated leader geometry. Each physical leader/follower pair must be validated one axis at a time with a five-second test and `max_joint_delta=0.01`. Signs and offsets remain configuration data; conversion code is not edited per robot.

Hardware acceptance proceeds in this order:

1. Verify both leader ports independently.
2. Calibrate and read each leader independently.
3. Bring up `can0` and validate the left pair alone.
4. Bring up `can1` and validate the right pair alone.
5. Run both pairs together for five seconds without cameras.
6. Verify all three RGB streams in Rerun.
7. Record one ten-second disposable dataset in a new directory.
8. Record the production dataset only after inspecting the test episode.

## Error Handling

- Duplicate serial ports for the two leaders are rejected before connecting hardware.
- Missing or malformed left/right mapping vectors are rejected during configuration parsing.
- Missing, extra, or non-finite leader action fields are rejected before follower commands are generated.
- An unconfigured right D405 serial is rejected before robot connection.
- Partial leader, follower, or camera connection failure triggers cleanup of resources already opened.
- Policy state, action, or visual-feature mismatch aborts rollout before policy actions are sent.
- Ctrl+C and normal exit use the same cleanup path and do not move home or open grippers unless explicitly configured.

## Verification

Automated verification must include:

- All existing 57 single-arm and LeRobot regression tests remain passing.
- Both composed leaders use servo IDs 1–7 on independent ports and independent calibration IDs.
- Dual action keys and order exactly match the dual follower's 14D motor list.
- Left and right signs, scales, and offsets are applied independently.
- Both normalized leader grippers convert correctly to follower raw radians.
- Startup hold is independent for left and right grippers.
- 14D commands split into the correct left and right 7D commands.
- Joint clipping excludes indices 6 and 13.
- Partial connection and disconnect paths clean up both sides safely.
- A LeRobot v3 dataset round trip preserves the 14D state/action names and three 480p RGB keys.
- All four new CLI entry points import registrations and parse their YAML/configuration arguments.
- ACT defaults can be overridden and single-arm wrappers are unchanged.

No automated test may require physical hardware. Final real-hardware validation remains the user's staged acceptance procedure described above.

## Version Control

Development occurs on `feature/dual-arm-workflow` in an isolated worktree. The verified single-arm baseline remains on `main`. Dual-arm changes are committed in reviewable units and pushed to `doulei741/a1z-lerobot-custom`; they are not pushed to the original upstream repository.
