---
phase: 03-email-scorer-skill
plan: "02"
subsystem: email
tags: [sqlalchemy, postgresql, email-scoring, gmail-sync, daily-cap, haiku, rls]

# Dependency graph
requires:
  - phase: 03-email-scorer-skill
    plan: "01"
    provides: score_email() engine in backend/src/flywheel/engines/email_scorer.py

provides:
  - gmail_sync.py: _score_new_emails(), _check_daily_scoring_cap(), get_thread_priority() wired into sync loop
  - skill_executor.py: is_email_scorer dispatch guard + subsidy key allowlist entry

affects:
  - 05-email-copilot-ui (reads EmailScore rows scored automatically by sync)
  - Phase 5 API layer (uses get_thread_priority() for thread-level priority display)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Score-after-commit: scoring runs after upsert db.commit() so scoring failure never loses synced emails"
    - "RETURNING clause on pg_insert to capture UUID without extra SELECT"
    - "Per-tenant daily cap via scored_at JOIN query (not created_at) for accurate budget tracking"
    - "Non-fatal per-email scoring: exceptions logged by email.id only (no PII), loop continues"
    - "Read-time thread priority: MAX(priority) WHERE is_replied=FALSE, not a stored column"

key-files:
  created: []
  modified:
    - backend/src/flywheel/services/gmail_sync.py
    - backend/src/flywheel/services/skill_executor.py

key-decisions:
  - "Score-after-commit pattern: scoring failure cannot block or roll back email upserts"
  - "upsert_email() returns UUID via .returning(Email.id) — avoids extra SELECT round-trip"
  - "Daily cap default 500/day — prevents Haiku cost runaway during initial full sync (200+ emails)"
  - "get_thread_priority() is read-time MAX query, not a stored column (avoids denormalization)"
  - "SCORE-08 handled automatically by architecture: new thread messages hit normal sync path"
  - "email-scorer in skill_executor subsidy key allowlist — background scoring never has user API key"

# Metrics
duration: 8min
completed: 2026-03-24
---

# Phase 3 Plan 02: Gmail Sync Scoring Integration Summary

**Automatic email scoring wired into the 5-minute sync cycle with 500/day per-tenant cap and RETURNING-based UUID collection — every newly synced email scored by Haiku within one sync cycle**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-24T12:26:00Z
- **Completed:** 2026-03-24T12:34:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Email scorer engine (from Plan 01) is now automatically invoked for every new email during both full sync and incremental sync cycles
- Per-tenant daily cap of 500 scores/day prevents cost blowout during initial full sync (200+ emails at once)
- Thread priority is computable at read time via `get_thread_priority()` — exported and ready for Phase 5 API layer
- `skill_executor.py` recognizes "email-scorer" and uses the subsidy key (background jobs never have user API keys)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire scorer into gmail_sync.py with daily cap** - `f196f2b` (feat)
2. **Task 2: Register email-scorer dispatch in skill_executor.py** - `8dced8c` (feat)

**Plan metadata:** TBD (docs commit — this summary)

## Files Created/Modified

- `backend/src/flywheel/services/gmail_sync.py` — Added score_email + EmailScore + sa_text imports; upsert_email() now returns UUID via RETURNING; _check_daily_scoring_cap(), _score_new_emails(), get_thread_priority() added; _full_sync() and sync_gmail() collect new_email_ids and call _score_new_emails() after commit
- `backend/src/flywheel/services/skill_executor.py` — Added is_email_scorer dispatch guard, elif branch (non-crashing placeholder), email-scorer to subsidy key allowlist

## Decisions Made

- **Score-after-commit pattern:** `_score_new_emails()` is called only after `await db.commit()` for the upserted emails. Scoring failure is wrapped in try/except and logged — emails are always safely persisted regardless of scoring outcome.
- **RETURNING clause on upsert:** Modified `upsert_email()` to add `.returning(Email.id)` and return the UUID. This avoids a second SELECT round-trip to look up the email ID for scoring, and works correctly for both INSERT and ON CONFLICT UPDATE paths (PostgreSQL RETURNING works for both).
- **Daily cap = 500/day:** Chosen to prevent runaway costs during initial full sync of large inboxes. The cap is configurable via the `cap` parameter on `_check_daily_scoring_cap()` for future tuning. Cap is measured via `scored_at >= today_utc` JOIN query — re-scoring the same email today still counts against the budget.
- **SCORE-08 by design:** New messages in existing threads are automatically scored because they arrive as new Email rows and their IDs are collected in `new_email_ids`. No special re-scoring logic needed.
- **Read-time thread priority:** `get_thread_priority()` computes MAX(priority) WHERE is_replied=FALSE as a read-time query. This avoids denormalizing priority onto the emails table and is always accurate as messages are replied to.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — the RETURNING clause approach for capturing email UUIDs after upsert worked correctly with SQLAlchemy's `pg_insert` implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SCORE-01 through SCORE-09 are fully addressed across Plans 01 and 02
- `get_thread_priority(db, tenant_id, gmail_thread_id)` is exported from `gmail_sync.py` and ready for Phase 5 API consumption
- Phase 4 (Email Drafting Engine) is next — draft context assembly and voice injection format validation recommended before planning

---
*Phase: 03-email-scorer-skill*
*Completed: 2026-03-24*
