---
phase: 63-meeting-prep-loop
plan: 01
subsystem: api
tags: [anthropic, skill-executor, sse, context-store, meeting-prep, relationships]

# Dependency graph
requires:
  - phase: 62-meeting-surfaces-and-relationship-enrichment
    provides: ContextEntry intel rows accumulated from meeting processing pipeline
  - phase: 61-meeting-intelligence-pipeline
    provides: write_context_entries writing PREP_CONTEXT_FILES content per account
  - phase: 55-relationships-and-signals-apis
    provides: Account model with graduated_at partition contract
provides:
  - POST /relationships/{id}/prep endpoint creating SkillRun with Account-ID input_text
  - _execute_account_meeting_prep() in skill_executor.py reading 7+1 INTEL_FILES from ContextEntry
  - Account-ID dispatch routing — skill_executor routes Account-ID-prefixed meeting-prep runs separately from onboarding path
affects:
  - 63-02-PLAN (frontend meeting prep button and SSE briefing display)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Account-ID prefix in SkillRun.input_text as dispatch discriminator — prefix routes to account engine vs onboarding engine
    - PREP_CONTEXT_FILES constant defining 7+1 files that feed the briefing LLM prompt
    - Empty context guard returns friendly HTML before reaching LLM call

key-files:
  created: []
  modified:
    - backend/src/flywheel/api/relationships.py
    - backend/src/flywheel/services/skill_executor.py

key-decisions:
  - "Account-ID: prefix in SkillRun.input_text acts as dispatch discriminator — is_account_meeting_prep checked BEFORE is_meeting_prep so existing onboarding path is completely untouched"
  - "PREP_CONTEXT_FILES includes 'contacts' (7 intel files + contacts = 8 total) — contacts are needed for Contacts & Stakeholders section"
  - "Empty context guard returns friendly HTML (not an error/exception) — avoids broken UI when account has no processed meetings yet"
  - "PrepRequest.meeting_id is optional — enriches prompt with meeting-specific context when provided; works without it for general prep"
  - "Return 404 (not 403) for non-graduated or non-existent accounts — per Phase 59 policy (never leak resource existence)"

patterns-established:
  - "Per-plan batch commit (per-plan strategy): single commit covers both tasks"
  - "Account-scoped engine dispatch: check `run.input_text.startswith('Account-ID:')` before generic skill name check"

# Metrics
duration: 12min
completed: 2026-03-28
---

# Phase 63 Plan 01: Meeting Prep Loop — Backend Summary

**Account-scoped meeting prep engine: POST /relationships/{id}/prep creates SkillRun dispatched to _execute_account_meeting_prep(), which reads 8 ContextEntry files per account and generates an HTML briefing via Claude streaming SSE**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-28T~00:00Z
- **Completed:** 2026-03-28
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Added `POST /relationships/{id}/prep` endpoint that creates a SkillRun with `Account-ID:` prefix and returns `{run_id, stream_url}` for SSE consumption
- Built `_execute_account_meeting_prep()` with 7 stages: parse input, read ContextEntry rows with RLS, empty context guard, optional meeting context, LLM prompt assembly, LLM call, emit done event
- Wired `is_account_meeting_prep` dispatch in execute_run() — routes before `is_meeting_prep` so the onboarding path is completely untouched
- Empty context store returns a styled friendly HTML message ("Not enough context yet") instead of a broken briefing or error

## Task Commits

Plan commit (per-plan strategy — all work in one commit):

1. **Tasks 1+2: endpoint + engine** - `a7dc2a0` (feat)

**Plan metadata:** (included in same commit)

## Files Created/Modified

- `backend/src/flywheel/api/relationships.py` — Added `PrepRequest` model, `SkillRun` import, `POST /relationships/{id}/prep` endpoint (RAPI-09)
- `backend/src/flywheel/services/skill_executor.py` — Added `is_account_meeting_prep` dispatch detection, `_execute_account_meeting_prep()` function (~250 lines), `PREP_CONTEXT_FILES` constant, updated `rendered_html` assignment to cover both meeting prep paths

## Decisions Made

- `Account-ID:` prefix in `SkillRun.input_text` is the dispatch discriminator — checked before the generic `is_meeting_prep` check, preserving the existing onboarding path without modification
- `PREP_CONTEXT_FILES` includes `"contacts"` in addition to the 6 INTEL_FILES from RAPI-02 — needed for the Contacts & Stakeholders section in the briefing
- Empty context guard emits a `done` event with friendly HTML (not an `error` event) — ensures the frontend can render the message without special-casing empty state
- `Meeting` is imported locally inside `_execute_account_meeting_prep` (not at module level) — matches the existing pattern used by `_execute_meeting_processor`

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend is fully ready for Phase 63 Plan 02 (frontend meeting prep button + SSE briefing display)
- `stream_url` returned by the endpoint is `/api/v1/skills/runs/{run_id}/stream` — frontend SSE hook should connect to this URL
- Empty context case is handled gracefully — frontend can render the "friendly HTML" from the briefing viewer without special-casing

---
*Phase: 63-meeting-prep-loop*
*Completed: 2026-03-28*
