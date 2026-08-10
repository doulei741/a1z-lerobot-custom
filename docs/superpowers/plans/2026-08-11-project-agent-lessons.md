# Project AGENTS Lessons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the root project rules accurately capture the validated A1Z workflows and failure lessons.

**Architecture:** Keep one authoritative root `AGENTS.md`. Organize stable architecture and operational rules separately from the J2/J3 failure case so later agents can find both invariants and troubleshooting steps.

**Tech Stack:** Markdown, Git, pytest hardware-independent regression suite.

## Global Constraints

- Do not create a competing singular `AGENT.md`.
- Do not change source code, hardware configuration, or single-arm mappings.
- Do not include passwords, access tokens, or private credentials.
- Distinguish automated verification from operator-confirmed hardware verification.

---

### Task 1: Refresh Project Rules and Add Failure Lessons

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: validated dual mapping and limit behavior at commit `821f464`.
- Produces: project instructions automatically loaded by Codex.

- [ ] Replace stale dual-camera, Teleoperator, and disconnect descriptions with current behavior.
- [ ] Add exact current dual signs/offsets and state that new physical pairs require independent pairing.
- [ ] Document the J2/J3 symptoms, Leader-only diagnostic interpretation, A1Z limits, sign/offset coupling, and pre-history clipping invariant.
- [ ] Add staged hardware acceptance, reusable-script, environment, and GitHub maintenance rules without credentials.
- [ ] Run `git diff --check` and scan the final document for old contradictory phrases and secrets.
- [ ] Run the complete hardware-independent regression suite.
- [ ] Commit, push `feature/dual-arm-workflow`, and verify local/remote hashes match.
