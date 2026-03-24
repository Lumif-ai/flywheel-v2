---
phase: 06-feedback-flywheel
plan: 01
subsystem: backend-engines
tags: [feedback-loop, voice-profile, dismiss-signal, background-tasks]
dependency_graph:
  requires:
    - backend/src/flywheel/db/models.py (EmailVoiceProfile schema)
    - backend/src/flywheel/api/email.py (approve_draft endpoint)
    - backend/src/flywheel/engines/email_scorer.py (scoring pipeline)
    - backend/src/flywheel/db/session.py (tenant_session)
  provides:
    - email_voice_updater.update_from_edit (diff analysis + Haiku merge)
    - email_dismiss_tracker.get_dismiss_signal (COUNT query + threshold gate)
    - approve_draft background voice update (fire-and-forget after commit)
    - score_email dismiss signal injection (prompt enrichment)
  affects:
    - backend/src/flywheel/api/email.py (approve_draft wired)
    - backend/src/flywheel/engines/email_scorer.py (dismiss signal injected)
tech_stack:
  added: [difflib (stdlib)]
  patterns:
    - BackgroundTasks fire-and-forget (mirrors trigger_sync pattern)
    - tenant_session in background helper (mirrors _run_sync pattern)
    - sa_text with make_interval(days => :days) for parameterized interval
    - JSON regex fallback parse (same as email_scorer and gmail_sync)
    - Caller-commits pattern (voice updater commits its own session)
key_files:
  created:
    - backend/src/flywheel/engines/email_voice_updater.py
    - backend/src/flywheel/engines/email_dismiss_tracker.py
  modified:
    - backend/src/flywheel/config.py
    - backend/src/flywheel/api/email.py
    - backend/src/flywheel/engines/email_scorer.py
decisions:
  - "voice_update_min_edits default=1: every edit triggers update; Haiku returns empty JSON for trivial diffs (no-op)"
  - "make_interval(days => :days) not string interpolation for interval — avoids SQL injection and parameterization issues with asyncpg"
  - "Diff captured as strings before null in approve_draft — ORM object expires after commit"
  - "Background task receives string values (not ORM refs or draft_id) — safe after session boundary"
  - "dismiss_signal injected before EMAIL TO SCORE block in user_message — visible to Haiku scorer"
metrics:
  duration: "~3 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  files_changed: 5
---

# Phase 6 Plan 01: Feedback Flywheel Engines Summary

**One-liner:** Difflib diff + Haiku incremental voice profile update from approve-time edits, and dismiss-based scoring signal injection using COUNT query on email_drafts.

## What Was Built

### Task 1: Voice Updater Engine, Dismiss Tracker Engine, Config Settings

**email_voice_updater.py** — two functions:
- `_compute_diff_summary(original, edited)`: stdlib `difflib.unified_diff`, capped at 50 lines, returns "No changes detected." on identical input
- `update_from_edit(db, tenant_id, user_id, original_body, edited_body)`: loads profile, calls Haiku with diff + current profile, merges returned JSON into profile fields (running avg for avg_length, case-insensitive dedup + cap-10 for phrases, replace for tone/sign_off), increments samples_analyzed, persists via UPDATE

**email_dismiss_tracker.py** — one function:
- `get_dismiss_signal(db, tenant_id, sender_email, days, threshold)`: COUNT query via `make_interval(days => :days)` parameterized interval, returns DISMISS SIGNAL block string if count >= threshold, empty string otherwise, non-fatal on error

**config.py** additions:
- `voice_update_min_edits: int = 1`
- `dismiss_lookback_days: int = 30`
- `dismiss_threshold: int = 3`

### Task 2: Wire Voice Update + Dismiss Signal

**api/email.py** modifications:
- `approve_draft`: added `background_tasks: BackgroundTasks` parameter
- Captures `original_body` and `edited_body` as strings BEFORE `draft.draft_body = None`
- Computes `has_edit = edited_body is not None and edited_body != original_body`
- After `await db.commit()`, fires `background_tasks.add_task(_run_voice_update, ...)` only when `has_edit and original_body is not None`
- Added `_run_voice_update` module-level helper using `tenant_session` (mirrors `_run_sync` pattern)

**engines/email_scorer.py** modifications:
- Import: `from flywheel.engines.email_dismiss_tracker import get_dismiss_signal`
- `score_email`: calls `get_dismiss_signal(db, tenant_id, email.sender_email, days=settings.dismiss_lookback_days, threshold=settings.dismiss_threshold)` between Step 2 (FTS) and Step 3 (prompt build)
- `_build_score_prompt`: added `dismiss_signal: str = ""` parameter, injected into user_message after `{entries_block}`

## Must-Have Truths Verified

| Truth | Status |
|-------|--------|
| After approving an edited draft, voice profile samples_analyzed increments and updated_at advances | Built — update_from_edit increments samples_analyzed and sets updated_at=now(UTC) |
| After dismissing 3+ drafts from same sender in 30 days, subsequent emails include DISMISS SIGNAL block | Built — get_dismiss_signal returns block string; injected into score prompt |
| Voice update only fires when user_edits differs from draft_body | Built — has_edit guard: `edited_body is not None and edited_body != original_body` |
| Voice update runs as background task — approve returns 200 before profile update | Built — BackgroundTasks.add_task fires after db.commit() |

## Deviations from Plan

None — plan executed exactly as written.

## Spec Gaps Discovered

None.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| email_voice_updater.py exists | FOUND |
| email_dismiss_tracker.py exists | FOUND |
| 06-01-SUMMARY.md exists | FOUND |
| commit 4a9ca18 (task 1) | FOUND |
| commit 5c8bf5a (task 2) | FOUND |
