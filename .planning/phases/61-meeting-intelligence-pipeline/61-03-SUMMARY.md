---
phase: 61-meeting-intelligence-pipeline
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, meeting-processor, processing-rules, batch-processing]

# Dependency graph
requires:
  - phase: 61-01
    provides: meeting intelligence pipeline (7-stage) and classify_meeting in meeting_processor_web.py
  - phase: 61-02
    provides: auto_link_meeting_to_account, auto_create_prospect, upsert_account_contacts in meeting_processor_web.py

provides:
  - apply_post_classification_rules() pure function in meeting_processor_web.py — MPP-05 rules engine
  - POST /meetings/process-pending — batch endpoint, creates SkillRun per pending meeting
  - GET /meetings/ — paginated list with optional status filter
  - GET /meetings/{id} — detail with owner-only transcript_url/ai_summary privacy enforcement
  - Pipeline wired: skip check between Stage 3 and Stage 4 in skill_executor.py

affects:
  - 62-meeting-intelligence-frontend
  - any future phase that calls POST /meetings/process-pending

# Tech tracking
tech-stack:
  added: []
  patterns:
    - apply_post_classification_rules is a pure function (no DB, no async) for testability
    - Post-classification rules live in meeting_processor_web.py to avoid circular imports with api/meetings.py
    - Granola list_meetings aliased as granola_list_meetings in meetings.py to avoid name collision with new endpoint
    - Owner-only privacy: transcript_url and ai_summary only in GET /{id} response when user_id matches

key-files:
  created: []
  modified:
    - backend/src/flywheel/engines/meeting_processor_web.py
    - backend/src/flywheel/api/meetings.py
    - backend/src/flywheel/services/skill_executor.py

key-decisions:
  - "apply_post_classification_rules lives in meeting_processor_web.py (not api/meetings.py) — avoids circular import risk since skill_executor imports from meeting_processor_web"
  - "skip_internal defaults to True when key is absent — matches spec (internal-only meetings never waste LLM credits)"
  - "skip_domains check includes tenant_domain in allowed set — meetings where all attendees are tenant+skip_domain are skipped"
  - "Post-classification rules fire between Stage 3 and Stage 4 — classification result saved even on skip"
  - "granola_list_meetings alias used in meetings.py to avoid collision with async def list_meetings endpoint"

patterns-established:
  - "apply_post_classification_rules: pure function pattern — all 4 MPP-05 rule types, returns 'pending' or 'skipped'"
  - "Owner-only privacy pattern: is_owner = str(meeting.user_id) == str(user.sub); sensitive fields only added if is_owner"
  - "Batch endpoint pattern: collect all pending, mark processing, flush, link run_ids, commit in one transaction"

# Metrics
duration: 15min
completed: 2026-03-28
---

# Phase 61 Plan 03: Meeting Processing Rules + Batch/List/Detail API Summary

**MPP-05 post-classification rules engine (skip_meetings/skip_internal/skip_domains/skip_types) wired into the 7-stage pipeline + batch process-pending endpoint + paginated list + owner-privacy detail endpoint**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-28T00:00:00Z
- **Completed:** 2026-03-28T00:15:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `apply_post_classification_rules()` pure function added to `meeting_processor_web.py` implementing all 4 MPP-05 rule types: `manually_skipped` (by external_id), `skip_internal` (no external attendees, default ON), `skip_domains` (all attendees in skip/tenant domain set), `skip_meeting_types` (by classified meeting type)
- `POST /meetings/process-pending` batch endpoint creates a SkillRun for every pending meeting in one transaction — this is the frontend sync button's target endpoint
- `GET /meetings/` list endpoint with optional `?status=` filter and limit/offset pagination
- `GET /meetings/{id}` detail endpoint enforces owner-only access to `transcript_url` and `ai_summary` (MDE-01 privacy spec)
- Post-classification rules wired between Stage 3 (classify) and Stage 4 (extract) in `skill_executor.py` — loads `processing_rules` from Integration.settings and `tenant.domain` for the skip_domains rule; skipped meetings have `processing_status="skipped"` with `meeting_type` classification preserved

## Task Commits

Both tasks completed in a single per-plan commit:

1. **Task 1 + Task 2** - `b74982a` (feat: post-classification rules engine + batch/list/detail meeting endpoints)

## Files Created/Modified

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/engines/meeting_processor_web.py` — Added `apply_post_classification_rules()` pure function (MPP-05 rules, 4 types)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/meetings.py` — Added `POST /process-pending`, `GET /`, `GET /{id}` endpoints; aliased granola import to avoid name collision
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/skill_executor.py` — Added `apply_post_classification_rules` import + post-Stage-3 skip check with tenant_domain loading

## Decisions Made

- **apply_post_classification_rules co-located in meeting_processor_web.py** — not in api/meetings.py. skill_executor imports from meeting_processor_web; if the function lived in api/meetings.py, a circular import would result (api → skill_executor → api). Pure functions belong in the engine layer.
- **granola_list_meetings alias** — the granola adapter's `list_meetings` function and the new `GET /meetings/` route function both need the name `list_meetings`. Aliased the import as `granola_list_meetings` to avoid the collision at module load time.
- **skip_internal default True** — `processing_rules.get("skip_internal", True)` defaults to ON. The spec (MPP-05) states skip_internal is on by default; this means internal-only meetings are always skipped unless explicitly disabled.
- **Classification preserved on skip** — when post-classification rules skip a meeting, the pipeline still sets `meeting_type` to the classified value (not left NULL). This lets analytics queries see what types are being skipped.

## Deviations from Plan

None — plan executed exactly as written, including the naming conflict fix (granola alias) which was discovered during implementation.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Naming collision between granola_adapter.list_meetings and new GET / endpoint**
- **Found during:** Task 2 (list_meetings endpoint)
- **Issue:** `from flywheel.services.granola_adapter import ... list_meetings` and `async def list_meetings(...)` in same module would shadow the import
- **Fix:** Aliased import as `granola_list_meetings`; updated single call site in `sync_meetings`
- **Files modified:** `backend/src/flywheel/api/meetings.py`
- **Verification:** Import + endpoint both verified with `python3 -c "from flywheel.api.meetings import list_meetings; print('OK')"`
- **Committed in:** b74982a

---

**Total deviations:** 1 auto-fixed (Rule 1 — naming collision)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered

None beyond the naming collision documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 3 meeting API layers complete (sync, process, list, detail, batch-process)
- Processing rules engine covers all 4 MPP-05 rule types — frontend can expose rule configuration
- Phase 62 (meeting intelligence frontend) can now call `GET /meetings/` for the meeting list and `POST /meetings/process-pending` for the sync button
- `GET /meetings/{id}` returns full pipeline output (summary JSONB with tldr, action_items, etc.) once processing completes

---
*Phase: 61-meeting-intelligence-pipeline*
*Completed: 2026-03-28*
