# A1Z Leader Joint Diagnostic Script Design

## Goal

Replace multiline inline Python diagnostics with a reusable command that observes selected STS3215
Leader joints without connecting to or commanding an A1Z Follower.

## Interface

Add the module `a1z_lerobot.tools.diagnose_leader_joints`, invoked as:

```bash
python -m a1z_lerobot.tools.diagnose_leader_joints \
  --port=/dev/ttyACM0 \
  --id=a1z_left_leader
```

Arguments:

- `--port`: required Leader serial port.
- `--id`: required calibration ID.
- `--duration-s`: observation duration, default `30` seconds; must be positive.
- `--threshold-rad`: minimum delta change printed, default `0.02` rad; must be positive.
- `--joint-indices`: zero-based joint indices, default `[1, 2]`, corresponding to physical joints 2
  and 3; each value must be in `0..5` and unique.

## Behavior

1. Construct the existing `A1ZLeader` with the requested port and calibration ID.
2. Connect with `calibrate=False`; never connect CAN, cameras, or any Follower.
3. Read one baseline action.
4. Until the duration expires, read the requested joints and print only when a delta has changed by at
   least the threshold since the last printed sample.
5. Show both current mapped radians and deltas from the baseline with unambiguous `J2`, `J3` labels.
6. On normal completion, `Ctrl+C`, or read failure, disconnect the Leader in `finally` and preserve the
   original failure.

The script does not change signs, offsets, calibration files, servo IDs, or follower commands. The
existing Leader connection path may configure the STS3215 operating mode exactly as normal calibration
and teleoperation already do.

## Output Contract

The initial output identifies the port, calibration ID, monitored joints, baseline values, duration, and
threshold. Change lines use this form:

```text
J2=+0.123 rad, delta_J2=-0.045 rad | J3=-0.456 rad, delta_J3=+0.010 rad
```

The final line states whether the duration completed or the operator interrupted the observation.

## Verification

Hardware-independent tests use a fake Leader and fake monotonic clock to verify:

- default J2/J3 monitoring and threshold filtering;
- argument validation;
- `calibrate=False` connection;
- cleanup after normal completion, `Ctrl+C`, and read failure;
- no robot, CAN, camera, or recording component is imported or constructed by the diagnostic module.

The dual-arm command guide will contain complete one-line commands for the left and right Leaders.
