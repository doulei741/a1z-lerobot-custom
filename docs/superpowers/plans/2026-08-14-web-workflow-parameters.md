# A1Z Web Workflow Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Web teleoperation and recording pages expose the real, useful parameters from the verified A1Z commands, with `gripper_start_hold=false` as the GUI default and a complete graphical Resume workflow.

**Architecture:** Pydantic remains the authoritative allow-list and validation boundary. React renders common parameters directly and operational tuning under Advanced Settings; workers translate only validated fields into fixed argv/config structures. Resume keeps LeRobot's `num_episodes = episodes added in this session` contract while the UI also presents existing and target totals.

**Tech Stack:** FastAPI, Pydantic v2, React 19, TypeScript strict, TanStack Query, Vitest, pytest.

## Global Constraints

- Never accept free shell arguments or use shell string concatenation.
- Do not change the A1Z control loop, `send_action()`, 7D/14D contracts, camera keys, or RGB-only camera behavior.
- Real hardware motion remains disabled in automated tests.
- Existing unrelated user changes and the `GALAXEA-A1Z` submodule state must remain untouched.

---

### Task 1: Authoritative request models and worker translation

**Files:**
- Modify: `a1z_web/backend/app/schemas/workflows.py`
- Modify: `a1z_web/backend/app/workers/teleoperation.py`
- Modify: `a1z_web/backend/app/workers/recording.py`
- Test: `a1z_web/backend/tests/test_validation.py`
- Test: `a1z_web/backend/tests/test_worker_arguments.py`

**Interfaces:**
- Consumes: LeRobot `TeleoperateConfig`, `RecordConfig`, and `DatasetRecordConfig` fields.
- Produces: validated `TeleoperationRequest` and `RecordingRequest` payloads; fixed CLI argv and decoded recording config values.

- [ ] **Step 1: Write failing tests** proving teleoperation and recording default `gripper_start_hold` to false, teleoperation carries optional duration/compressed-display flags, and recording accepts bounded writer/encoder settings.
- [ ] **Step 2: Run the targeted pytest tests** and verify failures are caused by the missing fields/defaults.
- [ ] **Step 3: Add only the validated fields**: `teleop_time_s`, teleoperation `display_compressed_images`, recording `play_sounds`, writer process/thread counts, batch size, streaming encoding, queue size, encoder threads, and structured camera encoder settings.
- [ ] **Step 4: Translate validated fields** to the existing CLI argv and `RecordConfig` dictionary without changing control behavior.
- [ ] **Step 5: Run targeted and full backend tests**, Ruff, compileall, and `a1z_web/scripts/validate-worker-configs.py` in the `lerobot-a1z` environment.

### Task 2: Teleoperation advanced GUI

**Files:**
- Modify: `a1z_web/frontend/src/pages/Teleoperation.tsx`
- Test: `a1z_web/frontend/src/test/workflow-parameters.test.tsx`

**Interfaces:**
- Consumes: `TeleoperationRequest` JSON contract.
- Produces: typed form payload with indefinite operation by default, optional duration, compressed Rerun display, and explicit gripper behavior.

- [ ] **Step 1: Write a failing interaction test** that selects `gripper_start_hold=false`, compressed display, and an optional duration and observes those values in the preflight payload.
- [ ] **Step 2: Run the test and verify RED.**
- [ ] **Step 3: Add the controls under Advanced Settings**, keeping duration empty for unlimited teleoperation and showing the physical meaning of the gripper switch.
- [ ] **Step 4: Run the targeted frontend test and verify GREEN.**

### Task 3: Recording Resume and encoder GUI

**Files:**
- Modify: `a1z_web/frontend/src/pages/Recording.tsx`
- Modify: `a1z_web/frontend/src/services/api.ts`
- Test: `a1z_web/frontend/src/test/workflow-parameters.test.tsx`

**Interfaces:**
- Consumes: `/api/record/compatibility` report with `existing_episodes` and validated `RecordingRequest` fields.
- Produces: `resume`, `existing episodes`, `target total`, and derived `dataset.num_episodes` payload plus validated encoder/writer controls.

- [ ] **Step 1: Write a failing Resume test** where compatibility reports 25 existing episodes, target total is changed to 45, and start sends `resume=true` with `dataset.num_episodes=20`.
- [ ] **Step 2: Write a failing advanced-recording test** for gripper hold false and non-default writer/streaming/encoder values.
- [ ] **Step 3: Run both tests and verify RED.**
- [ ] **Step 4: Implement the Resume panel** so compatibility must run first, target must exceed existing count, and the UI derives the LeRobot add count.
- [ ] **Step 5: Implement the Advanced Settings fields** with exact numeric inputs and explanatory text; keep local-only/no-upload behavior.
- [ ] **Step 6: Run targeted tests and verify GREEN.**

### Task 4: Integration verification and documentation

**Files:**
- Modify: `a1z_web/README.md`
- Review only: `docs/a1z-dual-arm-commands.md`

**Interfaces:**
- Consumes: completed backend and frontend behavior.
- Produces: operator documentation that explains defaults, Resume arithmetic, and advanced parameters.

- [ ] **Step 1: Update the Web README** with GUI defaults, Resume behavior, and advanced tuning warnings.
- [ ] **Step 2: Run frontend lint, typecheck, Vitest, build, and Playwright Mock E2E.**
- [ ] **Step 3: Run backend pytest, Ruff, compileall, and worker config validation.**
- [ ] **Step 4: Run `git diff --check` and inspect `git status --short`**, ensuring unrelated user changes are not staged.
- [ ] **Step 5: Commit only this feature's files.**
