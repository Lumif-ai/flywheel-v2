---
phase: 63-meeting-prep-loop
plan: "02"
subsystem: ui
tags: [react, typescript, sse, relationships, meetings]

# Dependency graph
requires:
  - phase: 63-01
    provides: POST /relationships/{id}/prep endpoint + SSE skill run stream
provides:
  - useRelationshipPrep SSE state machine hook (idle/running/done/error)
  - PrepBriefingPanel component with trigger button, streaming progress, HTML briefing viewer, error+retry
  - triggerRelationshipPrep() API function in relationships/api.ts
  - "Prep for Meeting" button on RelationshipDetail page (all account types)
  - "Prep for Meeting" button on MeetingDetailPage (conditional on account_id)
affects: [meeting-prep-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PrepBriefingPanel is self-contained — owns its own hook state, no prop drilling"
    - "SSE URL set after successful POST, same pattern as useMeetingProcessing"
    - "PrepBriefingPanel placed between TabsList and first TabsContent in RelationshipDetail — always visible regardless of active tab"

key-files:
  created:
    - frontend/src/features/relationships/hooks/useRelationshipPrep.ts
    - frontend/src/features/relationships/components/PrepBriefingPanel.tsx
  modified:
    - frontend/src/features/relationships/api.ts
    - frontend/src/features/relationships/components/RelationshipDetail.tsx
    - frontend/src/features/meetings/components/MeetingDetailPage.tsx

key-decisions:
  - "MeetingDetail type has no account_name field — used fallback string 'this account'; backend resolves name from DB"
  - "PrepBriefingPanel NOT importing MeetingPrepRenderer — different prop interface; renders dangerouslySetInnerHTML directly in styled container"
  - "done event renders both rendered_html and output fields for compatibility with different SkillRun response shapes"

patterns-established:
  - "SSE briefing pattern: POST trigger → run_id → /api/v1/skills/runs/{run_id}/stream — same shape as useMeetingProcessing"
  - "reset() helper on prep hook lets error state transition back to idle cleanly before retry"

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 63 Plan 02: Meeting Prep Loop — Frontend Trigger UI Summary

**SSE-powered PrepBriefingPanel with useRelationshipPrep hook, integrated into RelationshipDetail and MeetingDetailPage as dual trigger surfaces for AI meeting prep briefings**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-28T06:12:42Z
- **Completed:** 2026-03-28T06:14:12Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `triggerRelationshipPrep()` API function added to relationships/api.ts (POST /relationships/{id}/prep with optional meeting_id)
- `useRelationshipPrep` hook implements full idle/running/done/error SSE state machine, mirroring useMeetingProcessing pattern
- `PrepBriefingPanel` component covers all 4 states: idle button, streaming spinner with stage messages, rendered briefing HTML with Regenerate button, error card with Retry
- RelationshipDetail shows "Prep for Meeting" button above tabs for all account types
- MeetingDetailPage shows PrepBriefingPanel when meeting.account_id is set

## Task Commits

Plan-level batch commit (per-plan strategy):

1. **Tasks 1+2 (API + hook + component + integration)** - `7694a93` (feat)

## Files Created/Modified

- `frontend/src/features/relationships/api.ts` — added PrepResponse interface + triggerRelationshipPrep()
- `frontend/src/features/relationships/hooks/useRelationshipPrep.ts` — SSE state machine hook (created)
- `frontend/src/features/relationships/components/PrepBriefingPanel.tsx` — full-state prep panel component (created)
- `frontend/src/features/relationships/components/RelationshipDetail.tsx` — import + render PrepBriefingPanel between TabsList and TabsContent
- `frontend/src/features/meetings/components/MeetingDetailPage.tsx` — import + conditional render PrepBriefingPanel when meeting.account_id exists

## Decisions Made

- `MeetingDetail` type has no `account_name` field — passed `"this account"` as fallback; the backend resolves name from DB when generating the briefing
- Did not reuse `MeetingPrepRenderer` — it expects a specific onboarding prop interface; PrepBriefingPanel renders inline HTML directly via dangerouslySetInnerHTML in a styled container
- `done` event handler checks both `rendered_html` and `output` keys for compatibility with different SkillRun response shapes from the streaming endpoint

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 63 is fully complete — both backend (Plan 01) and frontend (Plan 02) of the meeting prep loop are shipped
- "Prep for Meeting" button is live on both the account detail page and meeting detail page
- Intelligence flywheel milestone (v3.0, Phases 59–63) is complete

## Self-Check: PASSED

- FOUND: frontend/src/features/relationships/hooks/useRelationshipPrep.ts
- FOUND: frontend/src/features/relationships/components/PrepBriefingPanel.tsx
- FOUND: frontend/src/features/relationships/api.ts
- FOUND: commit 7694a93
