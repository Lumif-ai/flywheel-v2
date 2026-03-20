---
phase: 20-skill-execution
plan: 04
subsystem: ui, api
tags: [sse, eventstream, chat, streaming, rate-limit]

requires:
  - phase: 20-skill-execution
    provides: "SSE streaming, skill executor, chat orchestrator, rate limiting"
provides:
  - "Stage events delivered to browser via SSE (EventSource listeners registered)"
  - "Rendered HTML and cost data delivered to chat view on skill completion"
  - "Concurrent run limit shows friendly message instead of generic error"
affects: [21-onboarding, human-verification]

tech-stack:
  added: []
  patterns:
    - "SSE synthetic done event enriched with DB data for late-connect clients"
    - "Fetch fallback in ChatStream when SSE event lacks rendered_html"
    - "Error classification in Zustand catch block for distinct UX per error type"

key-files:
  created: []
  modified:
    - frontend/src/lib/sse.ts
    - frontend/src/types/events.ts
    - frontend/src/features/chat/components/ChatStream.tsx
    - frontend/src/features/chat/store.ts
    - backend/src/flywheel/services/skill_executor.py
    - backend/src/flywheel/api/skills.py

key-decisions:
  - "Fetch fallback for rendered_html instead of stuffing large HTML into events_log JSONB"
  - "Accept reject-with-message for concurrent limit (not true queueing) as appropriate for current stage"
  - "Concurrent limit shown as normal assistant message (not error box) for friendlier UX"

duration: 2min
completed: 2026-03-20
---

# Phase 20 Plan 04: Verification Gap Closure Summary

**SSE stage/result event listeners, rendered output delivery via enriched done events, and concurrent limit UX in chat**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T14:43:02Z
- **Completed:** 2026-03-20T14:45:13Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Stage events from skill executor now reach ChatStream.tsx (added 'stage' and 'result' to SSEEventType union and eventTypes array)
- Skill completion delivers rendered_html, tokens_used, and cost_estimate to chat view via enriched SSE done events (both executor and synthetic endpoint events)
- Concurrent run limit (429) shows friendly "3 skills running" message as normal assistant response instead of red error box

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix SSE stage events and deliver output on completion** - `bf162d9` (fix)
2. **Task 2: Distinguish concurrent limit error from generic errors** - `302442a` (fix)

## Files Created/Modified
- `frontend/src/lib/sse.ts` - Added 'stage' and 'result' to SSEEventType and eventTypes array
- `frontend/src/types/events.ts` - Added StageEvent, ResultEvent interfaces; enriched DoneEvent with cost fields
- `frontend/src/features/chat/components/ChatStream.tsx` - Read rendered_html from done event with fetch fallback
- `frontend/src/features/chat/store.ts` - Detect ConcurrentRunLimitExceeded and show friendly message
- `backend/src/flywheel/services/skill_executor.py` - Include tokens_used, cost_estimate, run_id in done event
- `backend/src/flywheel/api/skills.py` - Enrich synthetic done event with rendered_html and cost from run record

## Decisions Made
- Fetch fallback pattern: ChatStream reads rendered_html from SSE done event first, falls back to fetching `/skills/runs/{runId}` if missing -- avoids stuffing large HTML blobs into events_log JSONB
- Concurrent limit as reject-with-message: accepted simplification over true queueing, appropriate for current stage
- Concurrent limit renders as `status: 'complete'` (not 'error') so it appears as a normal assistant message rather than a red error box

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 5 Phase 20 observable truths should now pass verification
- Human verification still required: end-to-end chat execution with real API key, late-connect replay, concurrent limit UX

## Self-Check: PASSED

All 6 modified files verified on disk. Both task commits (bf162d9, 302442a) found in git log.

---
*Phase: 20-skill-execution*
*Completed: 2026-03-20*
