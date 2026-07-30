# Relative Single-Arm Teleoperation Implementation Plan

**Goal:** Rebase Leader actions to the A1Z pose at connection so initial Leader pose never causes an A1Z jump.

**Architecture:** Keep the GALAXEA SDK position-hold startup and existing EMA, per-step limit, and physical limits. Add an opt-in `relative_action_reference` mode to `A1ZSingle`; on its first action it captures the Leader action and thereafter transforms the requested action to `follower_start + leader_current - leader_start`. The recording configuration enables the mode; ACT rollout remains absolute.

## Tasks

- [ ] Add a failing unit test for rebasing equal Leader actions to the recorded A1Z state.
- [ ] Add `relative_action_reference: bool = False` and minimal anchoring state to `A1ZSingle`.
- [ ] Add failing tests that relative mode holds on its first action while default mode preserves absolute policy actions.
- [ ] Enable relative mode in `record_a1z_single_realsense.yaml` and document the teleoperation flag.
- [ ] Run the full hardware-free regression suite and CLI help checks.
