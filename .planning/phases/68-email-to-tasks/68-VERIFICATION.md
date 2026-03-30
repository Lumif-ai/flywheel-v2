---
phase: 68-email-to-tasks
verified: 2026-03-29T16:05:03Z
status: passed
score: 8/8 must-haves verified
---

# Phase 68: Email-to-Tasks Verification Report

**Phase Goal:** Add a channel-agnostic task extraction stage to the flywheel ritual that converts high-priority scored emails into Task rows using existing score metadata (no new LLM calls). Includes dedup guard, volume control, schema migration, daily brief integration, and API surface updates.
**Verified:** 2026-03-29T16:05:03Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `/flywheel` ritual creates Task rows from emails scored `action_required` or `meeting_followup` with priority >= 4 since the last ritual run | VERIFIED | `channel_task_extractor.py:268-275`: query filters `EmailScore.category.in_(["action_required","meeting_followup"])` and `EmailScore.priority >= 4`. Ritual calls `extract_channel_tasks` between stage 2 and 3 at `flywheel_ritual.py:86` |
| 2 | First-run lookback is 7 days, capped at 15 emails, with a user-facing message explaining the scope | VERIFIED | `channel_task_extractor.py:250-254`: `if is_first_run: cutoff = now - 7 days; limit = 15`. Brief renders "Found N actionable emails from the last 7 days. Showing top 15 by priority." at `flywheel_ritual.py:844` |
| 3 | Duplicate detection flags email tasks that overlap with existing tasks (including meeting-sourced) via ratio-based word matching with stop word removal | VERIFIED | `_find_duplicate` at `channel_task_extractor.py:437-482`: queries all open tasks (no source filter), normalizes titles with stop words, computes `overlap / shorter >= 0.5`. Dedup check cross-sources via fall-through query at line 477 |
| 4 | Daily brief renders a "Detected Tasks" section showing email-sourced tasks with source badges, priority, and duplicate indicators | VERIFIED | `_render_detected_tasks_section` at `flywheel_ritual.py:822-903`: color-coded source badges (email=#3B82F6), priority dots (high=#E94D35, medium=#F97316), duplicate label with warning background. Inserted at section 2.5 (line 718) |
| 5 | `email_id` FK column on tasks table enables indexed idempotency checks — re-running the ritual does not create duplicate tasks | VERIFIED | Migration `035_add_email_task_fields.py:33-38`: adds `email_id` FK with `ondelete="SET NULL"`. Extractor excludes already-linked emails via `~Email.id.in_(existing_task_emails)` at line 272. `idx_tasks_email` index in both migration and ORM model |
| 6 | Email tasks with `suggested_skill` containing "email" have `trust_level="confirm"` (safety invariant) | VERIFIED | `channel_task_extractor.py:320-323`: `trust_level = "review"` set first, then overridden to `"confirm"` if `"email" in suggested_skill.lower()`. The only path to `suggested_skill` containing "email" is `"email-drafter"` (line 314) |
| 7 | `GET /tasks/?source=email` returns only email-sourced tasks | VERIFIED | `tasks.py:243,262-263`: `source: str | None = Query(None)` parameter, applied as `base.where(Task.source == source)` when present |
| 8 | Channel extractor architecture allows adding new sources by registering a function — no changes to stage orchestrator, dedup, or brief rendering needed | VERIFIED | `CHANNEL_EXTRACTORS` list at `channel_task_extractor.py:82,516`. Orchestrator iterates `extractors` list at line 141. New channel: `CHANNEL_EXTRACTORS.append(extract_slack_tasks)`. Stage orchestrator, dedup, and brief rendering all consume generic `CandidateTask` shape with no channel-specific logic |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/035_add_email_task_fields.py` | Alembic migration adding email_id FK and resolution columns | VERIFIED | 68 lines. Adds 4 columns + 2 indexes. Includes downgrade. |
| `backend/src/flywheel/db/models.py` | Updated Task model with email_id, resolved_by, resolution_source_id, resolution_note | VERIFIED | Lines 1380-1418: all 4 columns added, both new indexes in `__table_args__`, email relationship defined |
| `backend/src/flywheel/engines/channel_task_extractor.py` | Channel-agnostic extraction stage, email extractor, dedup guard | VERIFIED | 516 lines. `CandidateTask`, `extract_channel_tasks`, `extract_email_tasks`, `_find_duplicate`, `_normalize_title`, `_resolve_entity_to_account`, `CHANNEL_EXTRACTORS` registry — all present and substantive |
| `backend/src/flywheel/engines/flywheel_ritual.py` | Updated ritual with channel task extraction between stage 2 and stage 3 | VERIFIED | `extract_channel_tasks` import at line 23. Non-fatal try/except block at lines 81-102. `_render_detected_tasks_section` function at line 822. `has_content` check updated at line 737 |
| `backend/src/flywheel/api/tasks.py` | Source filter on GET /tasks/, new fields in response and update models | VERIFIED | `source` query param at line 243. `email_id`, `resolved_by`, `resolution_source_id`, `resolution_note` in `TaskResponse` (lines 154-169), `TaskUpdate` (lines 111-113), `_task_to_response` (lines 207-222), and `update_task` handler (lines 410-415) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `channel_task_extractor.py` | `models.py` | Creates Task ORM objects with email_id FK | VERIFIED | `Task(email_id=candidate["email_id"], ...)` at line 173-190 |
| `flywheel_ritual.py` | `channel_task_extractor.py` | Calls `extract_channel_tasks` in ritual orchestrator | VERIFIED | Import at line 23, call at line 86 |
| `channel_task_extractor.py` | `models.py` | Queries Email, EmailScore, SkillRun, Task, ContextEntity, AccountContact | VERIFIED | All 6 models imported at lines 32-40, used in queries |
| `flywheel_ritual.py` | `stage_results["channel_tasks"]` | `_compose_daily_brief` reads channel_tasks including tasks_detail | VERIFIED | Lines 717-718: `channel_tasks = stage_results.get("channel_tasks")` then `_render_detected_tasks_section(channel_tasks)` |
| `tasks.py` | `models.py` | Serializes new Task columns (email_id, resolved_by, etc.) | VERIFIED | `_task_to_response` at lines 207-222 maps all new ORM columns |

### Requirements Coverage

All 8 success criteria from the phase goal are satisfied by the verified truths above.

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholder returns, or stub implementations found in any modified file.

### Notable Implementation Details

1. **Idempotency subquery scope**: The `existing_task_emails` subquery at `channel_task_extractor.py:259-261` does not filter by `tenant_id/user_id`. It relies on RLS context being set (which it is, at lines 117-124). This is functionally correct given RLS, but means the subquery returns email_ids for the current tenant/user only at execution time. Not a bug.

2. **SkillRun status value**: The summary documents a deviation fix — plan spec said `status='complete'` but actual DB value is `"completed"`. The implementation correctly uses `"completed"` at line 130.

3. **CHANNEL_EXTRACTORS registration**: The list is initialized empty at line 82 and populated at line 516 (after function definitions). This is the correct pattern for avoiding forward-reference issues.

### Human Verification Required

| Test | What to Do | Expected | Why Human |
|------|-----------|----------|-----------|
| Brief visual layout | Run `/flywheel` ritual with emails scored action_required priority>=4, open the generated HTML brief | "Detected Tasks" section appears between Processing and Meeting Prep, with blue email badge, red/amber priority dot, and sender name | HTML rendering requires visual inspection |
| First-run message | On a fresh user account (no prior ritual runs), trigger the ritual | Blue italicized notice "Found N actionable emails from the last 7 days. Showing top 15 by priority." appears in brief | Requires a first-run state |
| Duplicate visual indicator | Trigger extraction with an email whose subject matches an existing task title (50%+ word overlap) | "possible duplicate of: {title}" label appears with amber/orange background | Requires matching data in dev DB |

---

_Verified: 2026-03-29T16:05:03Z_
_Verifier: Claude (gsd-verifier)_
