---
phase: 58-unified-company-intelligence-engine
plan: 03
subsystem: ui
tags: [react, sse, react-query, lucide, typescript]

# Dependency graph
requires:
  - phase: 58-02
    provides: POST /profile/refresh and POST /profile/reset endpoints returning run_id, plus /api/v1/skills/runs/{run_id}/stream SSE endpoint

provides:
  - useProfileRefresh hook with startRefresh(), startReset(), startFromRunId(), dismiss() actions
  - Refresh and Reset buttons on company profile page header (visible when profile has data)
  - Inline reset confirmation (no modal, no navigation)
  - LiveCrawl SSE overlay during refresh/reset replacing profile body
  - DocumentAnalyzePanel refactored to hand off run_id to parent via onRunStarted callback

affects:
  - CompanyProfilePage — extended with refresh/reset UI
  - DocumentAnalyzePanel — API contract changed (analyze-document now returns run_id not categories_written)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - useProfileRefresh follows same state shape as useProfileCrawl but decoupled (separate hook, not God hook)
    - startFromRunId() pattern — caller does POST, passes run_id; hook handles SSE only (separation of concerns)
    - SSE overlay replaces page body (not modal/drawer) during streaming — consistent with onboarding LiveCrawl pattern

key-files:
  created:
    - frontend/src/features/profile/hooks/useProfileRefresh.ts
  modified:
    - frontend/src/features/profile/components/CompanyProfilePage.tsx
    - frontend/src/features/profile/hooks/useCompanyProfile.ts
    - frontend/src/lib/sse.ts

key-decisions:
  - "useProfileRefresh is a separate hook from useProfileCrawl — decoupled per research recommendation, avoids God hook"
  - "startFromRunId() accepts an already-obtained run_id and only sets SSE URL — caller (DocumentAnalyzePanel) owns the POST"
  - "SSE overlay replaces entire profile body when refreshing/complete — not a modal, consistent with onboarding LiveCrawl pattern"
  - "Reset shows inline confirmation div (not modal) with red styling; cancel restores normal view"
  - "useSSE already appends token internally — SSE URL in hook is plain path without ?token= suffix"
  - "discovery event type added to sse.ts SSEEventType union — skills/runs stream sends discovery events, not text events"

patterns-established:
  - "run_id handoff pattern: DocumentAnalyzePanel POSTs, calls onRunStarted(run_id), parent hooks SSE — clean separation"
  - "dismiss() resets all state to idle — used as LiveCrawl onContinue handler after completion"

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 58 Plan 03: Refresh/Reset Buttons with SSE Streaming Summary

**Refresh and Reset buttons on the company profile page with LiveCrawl SSE streaming overlay, inline reset confirmation, and DocumentAnalyzePanel refactored to route through useProfileRefresh.startFromRunId()**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T15:21:56Z
- **Completed:** 2026-03-27T15:25:33Z
- **Tasks:** 3 (Task 1, Task 2a, Task 2b)
- **Files modified:** 4

## Accomplishments
- New `useProfileRefresh` hook with `startRefresh()`, `startReset()`, `startFromRunId()`, and `dismiss()` — decoupled from useProfileCrawl, same state shape
- Refresh + Reset buttons in profile header (visible only when `hasGroups` is true), Reset shows inline confirmation before executing
- SSE streaming via `/api/v1/skills/runs/{run_id}/stream` using existing `LiveCrawl` component as overlay; completion invalidates `company-profile` query and returns to normal view
- `DocumentAnalyzePanel` refactored: removed old `categories_written` inline handling, now accepts `onRunStarted` prop and calls it with `run_id` from POST
- All EnrichmentBanner / retry-enrichment dead code removed from CompanyProfilePage and useCompanyProfile

## Task Commits

All tasks committed together (per-plan strategy):

1. **Task 1: useProfileRefresh hook** - `8ca2ad7` (feat)
2. **Task 2a: Remove dead code, refactor DocumentAnalyzePanel** - `8ca2ad7` (feat)
3. **Task 2b: Wire buttons, confirmation, SSE overlay** - `8ca2ad7` (feat)

## Files Created/Modified
- `frontend/src/features/profile/hooks/useProfileRefresh.ts` — New hook: startRefresh/startReset POST to profile endpoints, startFromRunId accepts caller-provided run_id, all three set SSE URL and phase='refreshing'
- `frontend/src/features/profile/components/CompanyProfilePage.tsx` — Refresh/Reset buttons in header, inline reset confirmation, LiveCrawl SSE overlay, DocumentAnalyzePanel wired with onRunStarted callback; EnrichmentBanner removed
- `frontend/src/features/profile/hooks/useCompanyProfile.ts` — useRetryEnrichment function removed (no longer imported anywhere)
- `frontend/src/lib/sse.ts` — Added 'discovery' to SSEEventType union and event listener registration

## Decisions Made
- `useSSE` already appends the token internally (line 30 of sse.ts), so `setSseUrl` receives the bare path without `?token=` suffix — avoids double-token appending
- `void refresh.startReset()` used in onClick to avoid floating Promise lint warning (async function called in event handler)
- `useRetryEnrichment` removed from `useCompanyProfile.ts` — was exported but no longer imported anywhere after CompanyProfilePage cleanup

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added 'discovery' event type to sse.ts SSEEventType union**
- **Found during:** Task 1 (useProfileRefresh hook creation)
- **Issue:** The `skills/runs/{run_id}/stream` endpoint emits `discovery` events, but `useSSE` only registered listeners for `['thinking', 'text', 'skill_start', 'stage', 'result', 'clarify', 'error', 'done', 'crawl_error']`. The `discovery` event type was absent from both the type union and the listener registration loop, meaning SSE events would silently be dropped.
- **Fix:** Added `'discovery'` to `SSEEventType` union and to the `eventTypes` array in `useSSE`
- **Files modified:** `frontend/src/lib/sse.ts`
- **Verification:** TypeScript compiles clean with no errors
- **Committed in:** `8ca2ad7` (plan commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** Essential fix — without it, discovery events from the refresh/reset SSE stream would be silently dropped, breaking the entire LiveCrawl visualization.

## Issues Encountered
None — TypeScript passed clean on first run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 58 is the final phase — all 3 plans complete
- Refresh and Reset flows are fully wired and ready for end-to-end testing
- No blockers

---
*Phase: 58-unified-company-intelligence-engine*
*Completed: 2026-03-27*
