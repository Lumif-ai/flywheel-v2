---
phase: 66-flywheel-ritual
verified: 2026-03-29T05:00:00Z
status: passed
score: 14/14 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 8/8
  note: "Previous verification (2026-03-28) covered Plans 01-02 only (old curl-based skill). Plans 03-04 added Stage 4 task execution and Stage 5 HTML brief. The phase was also rearchitected: SKILL.md replaced with engine frontmatter, api-reference.md deleted. Re-verification covers all 4 plans."
  gaps_closed:
    - "N/A — previous verification was pre-rearchitect; this is a full re-verification of the final state"
  gaps_remaining: []
  regressions:
    - "skills/flywheel/SKILL.md (817 lines → 42 lines): This is intentional, not a regression. The curl-based Claude Code skill was replaced with a backend engine frontmatter definition per the rearchitect plan (66-01 Task 2)."
gaps: []
human_verification:
  - test: "Invoke flywheel_run_skill('flywheel') via MCP in a Claude Code session with running backend"
    expected: "SkillRun created, all 5 stages execute in order, HTML daily brief rendered in document library via MeetingPrepRenderer"
    why_human: "Requires running backend with job queue, Granola credentials, and live MCP session"
  - test: "Verify Stage 1 dedup behavior — run flywheel_run_skill twice in a row"
    expected: "Second run shows 0 new meetings (already_seen > 0), not duplicates"
    why_human: "Dedup logic depends on database state; cannot simulate without running backend"
  - test: "Trigger with confirmed task that has suggested_skill='meeting-prep'"
    expected: "Stage 4 formulates input via Haiku, invokes _execute_meeting_prep, task transitions from confirmed to in_review"
    why_human: "Requires live Anthropic API key, confirmed task record, and running engine"
  - test: "Verify SSE events stream to a single run (not child runs)"
    expected: "All stage events visible in the parent SkillRun's events_log; no orphaned child runs"
    why_human: "Requires observing database state during live engine execution"
---

# Phase 66: /flywheel Ritual Verification Report

**Phase Goal:** The flywheel ritual is a backend orchestrator engine — same architecture as meeting-prep and meeting-processor. One MCP invocation syncs meetings from Granola, processes unprocessed recordings into intelligence, prepares briefings for upcoming external meetings, executes confirmed tasks, and returns a rich HTML daily brief. Invoked via `flywheel_run_skill("flywheel")` — no separate installation, no env vars, no curl.

**Verified:** 2026-03-29T05:00:00Z
**Status:** passed
**Re-verification:** Yes — full re-verification after Plans 03-04 added Stages 4-5 and rearchitect replaced curl-based SKILL.md with engine frontmatter.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `flywheel_run_skill("flywheel")` dispatches to the flywheel engine (not generic _execute_with_tools) | VERIFIED | `skill_executor.py:581` — `is_flywheel = run.skill_name == "flywheel"`, dispatches to `execute_flywheel_ritual` at line 631 |
| 2 | SKILL.md has `engine: flywheel_ritual` frontmatter (no allowed-tools, no curl) | VERIFIED | `skills/flywheel/SKILL.md` line 9: `engine: flywheel_ritual`, line 10: `web_tier: 1`. No `allowed-tools`, no curl calls. 42 lines. |
| 3 | Stage 1 syncs Granola via shared `sync_granola_meetings()` function | VERIFIED | `flywheel_ritual.py:23` imports `sync_granola_meetings` from `meeting_sync.py`; `meetings.py:26` also imports same function — shared correctly |
| 4 | Stage 2 processes ALL unprocessed meetings via `_execute_meeting_processor()` | VERIFIED | `flywheel_ritual.py:161` docstring: "Process ALL meetings with unprocessed status (no caps)"; calls `_execute_meeting_processor` at line 191 |
| 5 | Stage 3 preps ALL today's unprepped external meetings via `_execute_meeting_prep()` | VERIFIED | `flywheel_ritual.py:255` docstring: "Prep ALL today's unprepped external meetings"; calls `_execute_account_meeting_prep` and `_execute_meeting_prep` at lines 296/317 |
| 6 | Stage 4 executes confirmed tasks via LLM formulation + `_execute_with_tools` | VERIFIED | `_stage_4_execute` at line 370; Haiku formulation at line 465; `_execute_with_tools` at line 531; task status → `in_review` at line 551 |
| 7 | Task failures do not stop other tasks from executing | VERIFIED | `except Exception as e` at line 566 logs failure, appends to `stage_results["tasks"]` with `success: False`, and loop continues (lines 566-592) |
| 8 | VALID_TRANSITIONS in tasks.py allows `confirmed -> in_review` | VERIFIED | `tasks.py:46`: `"confirmed": {"in_review", "in_progress", "dismissed"}` |
| 9 | Stage 5 composes HTML daily brief with 5 sections | VERIFIED | `_compose_daily_brief` at line 603 calls `_render_sync_section`, `_render_processed_section`, `_render_prep_section`, `_render_tasks_section`, `_render_remaining_section`. All 5 section IDs present. |
| 10 | Prep section shows summary cards (not full inline HTML) | VERIFIED | `flywheel_ritual.py:743`: `<p style="...">Full brief in Library</p>` — snippet shown, full HTML not inlined |
| 11 | Done SSE event includes `rendered_html` | VERIFIED | `flywheel_ritual.py:89-95`: `"event": "done"` with `"rendered_html": html_output` |
| 12 | SkillRenderer routes `flywheel` skillType to MeetingPrepRenderer | VERIFIED | `SkillRenderer.tsx:25`: `skillType === 'meeting-prep' \|\| skillType === 'ctx-meeting-prep' \|\| skillType === 'flywheel'` — all three preserved |
| 13 | MCP tool description mentions flywheel as an available skill | VERIFIED | `server.py:24-28`: docstring includes "Run a Flywheel skill like meeting-prep, company-intel, or flywheel" and describes daily ritual |
| 14 | FLY-01 through FLY-06 marked as superseded in REQUIREMENTS.md | VERIFIED | `REQUIREMENTS.md:87-92` and lines 197-204: all 6 FLY requirements marked `[~]` superseded with references to ORCH equivalents |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/services/meeting_sync.py` | Shared `sync_granola_meetings(factory, tenant_id, user_id)` function | VERIFIED | 8,987 bytes. `async def sync_granola_meetings` at line 133. Imported by both `meetings.py:26` and `flywheel_ritual.py:23` |
| `backend/src/flywheel/engines/flywheel_ritual.py` | Complete 5-stage engine with orchestrator function | VERIFIED | 919 lines. All 5 stage functions defined. `execute_flywheel_ritual` orchestrates stages 1-5. |
| `skills/flywheel/SKILL.md` | Backend-engine skill definition with `engine: flywheel_ritual` and `web_tier: 1` | VERIFIED | 42 lines. `engine: flywheel_ritual`, `web_tier: 1`, `contract_reads`, `contract_writes`. No `allowed-tools` or curl. |
| `backend/src/flywheel/services/skill_executor.py` | Dispatch wiring: `is_flywheel` flag, lazy import, subsidy allowlist | VERIFIED | `is_flywheel` at line 581, lazy import at line 631, subsidy allowlist at line 506 |
| `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` | Flywheel routing to MeetingPrepRenderer | VERIFIED | Line 25: `skillType === 'flywheel'` added to MeetingPrepRenderer condition |
| `cli/flywheel_mcp/server.py` | Updated tool description mentioning flywheel | VERIFIED | Docstring at line 24 updated to include flywheel as a skill option with description |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `skill_executor.py` | `flywheel_ritual.py::execute_flywheel_ritual` | lazy import at dispatch | WIRED | `from flywheel.engines.flywheel_ritual import execute_flywheel_ritual` at line 631 |
| `meetings.py` | `meeting_sync.py::sync_granola_meetings` | module import | WIRED | `from flywheel.services.meeting_sync import sync_granola_meetings` at line 26 |
| `flywheel_ritual.py` | `meeting_sync.py::sync_granola_meetings` | module import | WIRED | `from flywheel.services.meeting_sync import sync_granola_meetings` at line 23 |
| `flywheel_ritual.py` | `skill_executor.py::_execute_with_tools` | module import | WIRED | `from flywheel.services.skill_executor import _execute_with_tools, _load_skill_from_db, preload_tenant_context` at lines 24-32 |
| `flywheel_ritual.py Stage 4` | `Task.status = "in_review"` | sqlalchemy update | WIRED | `update(Task).where(Task.id == task.id).values(status="in_review")` at line 547-551 |
| `SkillRenderer.tsx` | `MeetingPrepRenderer` | skillType condition | WIRED | `skillType === 'flywheel'` added to existing condition at line 25; TypeScript compiles cleanly |

---

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| FLY-01: Daily brief invocable via single command | SATISFIED | `flywheel_run_skill("flywheel")` invokes engine; HTML brief produced |
| FLY-02: Sync from Granola | SATISFIED | Stage 1 via `sync_granola_meetings()` |
| FLY-03: Task execution | SATISFIED | Stage 4 via LLM formulation + `_execute_with_tools` |
| FLY-04: Meeting prep | SATISFIED | Stage 3 via `_execute_meeting_prep()` / `_execute_account_meeting_prep()` |
| FLY-05: Process unprocessed meetings | SATISFIED | Stage 2 via `_execute_meeting_processor()` |
| FLY-06: Auth | SATISFIED | MCP JWT session; subsidy key applies to 'flywheel'; no FLYWHEEL_API_TOKEN needed |

All FLY requirements marked superseded by ORCH equivalents in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | — |

**Anti-pattern checks:**
- TODO/FIXME/PLACEHOLDER in `flywheel_ritual.py`: 0 occurrences
- Empty implementations / `return null`: 0
- Placeholder HTML comments in Stage 5: 0 (Stage 5 placeholder replaced with full `_compose_daily_brief` implementation)
- `return {}` / static response with no real data: 0
- `api-reference.md` (deleted per plan): Confirmed deleted — correct per 66-01 Task 2

---

### Architectural Note: SKILL.md Change

The previous VERIFICATION.md (2026-03-28) verified an 817-line curl-based Claude Code skill at `skills/flywheel/SKILL.md`. This file has been intentionally replaced with a 42-line backend engine frontmatter definition. This is **not a regression** — it is the core of the rearchitect:

- **Old model (Plans 01-02, pre-rearchitect):** Claude Code skill with curl calls to the backend REST API. Required `FLYWHEEL_API_TOKEN` env var, `jq`, manual subcommands.
- **New model (Plans 01-04, post-rearchitect):** Backend engine invoked via MCP `flywheel_run_skill("flywheel")`. `SKILL.md` is a seed file for the `skill_definitions` DB table. No env vars, no curl, no separate installation.

The previous VERIFICATION.md is therefore outdated and this document supersedes it.

---

### Human Verification Required

#### 1. End-to-End Engine Execution

**Test:** Invoke `flywheel_run_skill("flywheel")` in a Claude Code session with a running backend and valid Granola credentials
**Expected:** All 5 stages execute; HTML daily brief appears in the document library rendered by MeetingPrepRenderer (not GenericRenderer)
**Why human:** Requires running backend with job queue, database, Granola integration, and live MCP session

#### 2. Granola Dedup Behavior

**Test:** Run `flywheel_run_skill("flywheel")` twice in a row
**Expected:** Second run shows 0 synced (already_seen > 0); no duplicate meeting records
**Why human:** Depends on database state and Granola integration; cannot simulate programmatically

#### 3. Stage 4 Task Execution

**Test:** Create a confirmed task with `suggested_skill = 'meeting-prep'`, then run flywheel ritual
**Expected:** Stage 4 formulates input text via Haiku, calls `_execute_meeting_prep`, task transitions from `confirmed` to `in_review`, output stored in stage_results for HTML brief
**Why human:** Requires live Anthropic API key, confirmed task record in database, running engine

#### 4. SSE Single-Run Event Stream

**Test:** Watch events_log in DB during flywheel execution
**Expected:** All stage events (sync, processing, prepping, executing, composing, done) appear in a single SkillRun's events_log — no separate child SkillRun records created by the orchestrator
**Why human:** Requires observing live database writes during engine execution

---

## Summary

Phase 66 goal is fully achieved across all 4 plans. The flywheel ritual operates as a backend engine matching the architecture of meeting-prep and meeting-processor:

1. **Dispatch wired** (`skill_executor.py`): `flywheel_run_skill("flywheel")` routes to `execute_flywheel_ritual` via lazy import; flywheel is in the subsidy allowlist.

2. **Stage 1 (sync)**: Extracts shared `sync_granola_meetings()` into `meeting_sync.py` used by both the API endpoint and the engine. Granola failure is non-fatal (continues to Stage 2).

3. **Stage 2 (process)**: Processes ALL unprocessed meetings via `_execute_meeting_processor()` with per-meeting failure isolation.

4. **Stage 3 (prep)**: Preps ALL today's unprepped external meetings via `_execute_meeting_prep()` / `_execute_account_meeting_prep()`.

5. **Stage 4 (execute)**: Queries confirmed tasks with `suggested_skill`, formulates input via Haiku LLM, dispatches to dedicated or generic engines, transitions tasks to `in_review`. VALID_TRANSITIONS updated. Individual failures don't block other tasks.

6. **Stage 5 (compose)**: `_compose_daily_brief()` renders 5 HTML sections (sync, processed, prep, tasks, remaining) with brand styling. Empty states handled per section and globally ("Your day is clear"). Done SSE event carries `rendered_html`.

7. **Frontend wired**: `SkillRenderer.tsx` routes `'flywheel'` skillType to `MeetingPrepRenderer` for HTML rendering. Existing `meeting-prep` and `ctx-meeting-prep` routing unchanged.

8. **MCP updated**: `flywheel_run_skill` docstring mentions flywheel as a skill option with description of daily ritual.

9. **SKILL.md correct**: Backend engine frontmatter (`engine: flywheel_ritual`, `web_tier: 1`) for `skill_definitions` DB seeding. No curl, no `allowed-tools`.

Human verification is recommended for the 4 runtime behaviors above, but all automated checks pass.

---

_Verified: 2026-03-29T05:00:00Z_
_Verifier: Claude (gsd-verifier)_
