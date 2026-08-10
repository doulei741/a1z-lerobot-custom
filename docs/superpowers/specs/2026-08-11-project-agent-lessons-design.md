# Project AGENTS Lessons Design

## Goal

Turn the validated single/dual A1Z bring-up experience and the J2/J3 failure investigation into
project rules that future Codex sessions load automatically.

## Scope

Update the existing root `AGENTS.md`; do not create a competing `AGENT.md`. Correct stale statements
about dual teleoperation, recording, camera keys, and disconnect behavior. Add durable rules for
Leader calibration and pairing, sign/offset coupling, A1Z joint limits, action-history ordering,
diagnostic scripts, staged hardware acceptance, environment use, and version-control workflow.

## Safety and Accuracy

Record the current validated dual signs and offsets exactly, while stating that they belong only to
the current physical pairs. Preserve single-arm mappings. Never include passwords or tokens. Treat
hardware observations separately from hardware-independent automated test results.

## Verification

Check Markdown formatting, scan for obsolete contradictory statements and secrets, run the complete
hardware-independent regression suite, commit, push `feature/dual-arm-workflow`, and verify that the
remote hash equals local HEAD.
