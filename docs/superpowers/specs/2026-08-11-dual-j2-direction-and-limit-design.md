# Dual A1Z J2 Direction and Limit Design

## Goal

Make both dual-arm followers track the available physical J2 motion of their matching Leaders, and
prevent out-of-range dual-arm commands from accumulating in the smoothing state.

## Mapping

Both dual Leaders use `joint_signs = [-1, -1, 1, 1, 1, -1]`. Only J2 changes sign. To keep the
existing paired zero pose at the A1Z J2 lower limit without a startup jump, negate each existing J2
offset:

- left J2 offset: `1.676119148`
- right J2 offset: `1.672050437`

All other signs, scales, and offsets remain unchanged. The single-arm defaults and configuration
remain unchanged.

## Dual Action Safety

After EMA and per-step delta limiting, clamp each left and right six-joint slice to
`A1Z_JOINT_LIMITS`. Perform this clamp before logging, storing `_prev_action`, sending to the SDK,
and returning the sent action. Gripper values keep their existing behavior.

## Verification

Tests must prove that invalid J2/J3 commands on both sides are clamped before they enter
`_prev_action`, that a following valid command starts from the bounded value rather than an invalid
accumulated value, and that the recording YAML decodes the new per-side signs and offsets. Run the
complete single/dual dataset and ACT regression suite before committing the implementation.
