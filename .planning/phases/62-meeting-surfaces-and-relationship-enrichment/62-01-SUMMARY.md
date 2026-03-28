---
phase: 62-meeting-surfaces-and-relationship-enrichment
plan: 01
subsystem: ui
tags: [react, tanstack-query, sse, lucide-react, sonner, react-router]

# Dependency graph
requires:
  - phase: 61-meeting-intelligence-pipeline
    provides: GET /meetings/, GET /meetings/{id}, POST /meetings/sync, POST /meetings/{id}/process — all live
  - phase: 58-unified-company-intelligence-engine
    provides: useSSE hook + useProfileRefresh SSE pattern (canonical model)
  - phase: 57-relationship-surfaces
    provides: BrandedCard, EmptyState, Skeleton, design tokens, RelationshipCard patterns
provides:
  - "Complete /meetings list page with filter tabs, sync button, status/type badges, and responsive card grid"
  - "Meeting detail page (/meetings/:id) with metadata, summary sections (tldr/decisions/actions/pain-points), transcript link (owner-only)"
  - "SSE-powered per-meeting processing feedback via useMeetingProcessing hook"
  - "Sidebar Meetings nav link (CalendarDays icon, general nav group)"
  - "Full meetings feature slice: types, API module, queryKeys, 4 hooks, 3 components"
affects:
  - "62-02 (Granola settings panel — uses same syncMeetings API and queryKeys)"
  - "62-03 (backend relationship enrichment — timeline/intel data feeds MeetingDetailPage)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useMeetingProcessing follows useProfileRefresh pattern exactly: useState for phase/stage/sseUrl, post to API first for run_id, then set SSE URL"
    - "STATUS_CONFIG + TYPE_COLORS maps defined at module level — single source of truth for all badge rendering"
    - "ProcessButton is isolated sub-component inside MeetingCard so each card has independent processing state"
    - "queryKeys.meetings.all invalidated on sync success; detail+list+signals invalidated on SSE done event"

key-files:
  created:
    - frontend/src/features/meetings/types/meetings.ts
    - frontend/src/features/meetings/api.ts
    - frontend/src/features/meetings/hooks/useMeetings.ts
    - frontend/src/features/meetings/hooks/useMeetingDetail.ts
    - frontend/src/features/meetings/hooks/useSyncMeetings.ts
    - frontend/src/features/meetings/hooks/useMeetingProcessing.ts
    - frontend/src/features/meetings/components/MeetingCard.tsx
    - frontend/src/features/meetings/components/MeetingsPage.tsx
    - frontend/src/features/meetings/components/MeetingDetailPage.tsx
  modified:
    - frontend/src/app/routes.tsx
    - frontend/src/features/navigation/components/AppSidebar.tsx

key-decisions:
  - "ProcessButton isolated as sub-component inside MeetingCard — each card has independent useMeetingProcessing state, no shared state contamination"
  - "queryKeys.meetings.all used for sync invalidation; detail(id)+all+signals for SSE done — ensures list badges and signals refresh together"
  - "transcript_url presence (truthy check) is the owner-only gate — absent for non-owners means no Transcript section renders"
  - "Build errors are 37 pre-existing TypeScript errors in unrelated files (FlywheelWheel, PipelinePage, BriefingCard, etc.) — confirmed by git stash test; zero errors in meetings files"

patterns-established:
  - "Pattern: Feature hooks follow useRelationships.ts — useQuery with enabled: !!user guard"
  - "Pattern: SSE hooks follow useProfileRefresh.ts — separate phase/stage/sseUrl state, post-then-setSseUrl ordering"

# Metrics
duration: ~25min
completed: 2026-03-28
---

# Phase 62 Plan 01: Meetings Feature Slice Summary

**React meetings feature slice with /meetings list + /meetings/:id detail pages, SSE per-meeting processing feedback, status/type badge system, and sidebar nav link wired to Phase 61 backend**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-03-28
- **Tasks:** 2/2
- **Files created:** 9 (new feature slice) + 2 modified

## Accomplishments

- Full TypeScript data layer: Attendee, MeetingSummary, MeetingListItem, MeetingDetail, SyncResult types + queryKeys factory + 4 API functions + 4 hooks (useMeetings, useMeetingDetail, useSyncMeetings, useMeetingProcessing)
- MeetingsPage with status filter tabs (All/Pending/Complete/Skipped/Failed), sync button with Loader2 spinner + toast feedback, responsive 1/2/3 column grid, skeleton loading state, and empty state
- MeetingDetailPage with back link, meeting metadata header (date/duration/type badge/status badge), attendees section, full summary sections (tldr/key decisions/action items/pain points), transcript link (owner-only via transcript_url truthy check), and inline processing feedback panel
- useMeetingProcessing hook follows useProfileRefresh pattern exactly — stage updates via SSE, on done: invalidates detail+list+signals cache
- Sidebar Meetings link registered in general nav group with CalendarDays icon and pathname.startsWith('/meetings') active check

## Task Commits

Plan-level batch commit (per-plan strategy):

1. **Tasks 1+2 combined** — `1549de9` (feat: meetings feature slice — types, API, hooks, components, routes, sidebar)

## Files Created/Modified

- `frontend/src/features/meetings/types/meetings.ts` — Attendee, MeetingSummary, MeetingListItem, MeetingDetail, SyncResult, ProcessingStatus
- `frontend/src/features/meetings/api.ts` — queryKeys factory, fetchMeetings, fetchMeetingDetail, syncMeetings, processMeeting
- `frontend/src/features/meetings/hooks/useMeetings.ts` — useQuery wrapping fetchMeetings, enabled when authenticated
- `frontend/src/features/meetings/hooks/useMeetingDetail.ts` — useQuery wrapping fetchMeetingDetail(id)
- `frontend/src/features/meetings/hooks/useSyncMeetings.ts` — useMutation with invalidate + toast.success/error
- `frontend/src/features/meetings/hooks/useMeetingProcessing.ts` — SSE hook: phase/stage/sseUrl state, processMeeting POST then SSE URL set
- `frontend/src/features/meetings/components/MeetingCard.tsx` — BrandedCard with STATUS_CONFIG, TYPE_COLORS, attendee count, TLDR snippet, isolated ProcessButton sub-component
- `frontend/src/features/meetings/components/MeetingsPage.tsx` — List page with filter tabs, sync button, responsive grid, skeleton, empty state
- `frontend/src/features/meetings/components/MeetingDetailPage.tsx` — Detail page with all summary sections, transcript (owner-only), processing feedback panel
- `frontend/src/app/routes.tsx` — Added /meetings and /meetings/:id lazy routes
- `frontend/src/features/navigation/components/AppSidebar.tsx` — Added CalendarDays Meetings link to general nav group

## Decisions Made

- **ProcessButton isolated** as a sub-component inside MeetingCard so each card has its own `useMeetingProcessing(meetingId)` state — prevents one card's SSE from affecting another
- **transcript_url truthy check** is the owner-only gate — the field is simply absent from the API response for non-owners, so `meeting.transcript_url &&` naturally hides the section
- **37 pre-existing build errors** in unrelated files confirmed by git stash test — not introduced by this plan; tsc --noEmit (plan-level check) passes with zero errors for all meetings files

## Deviations from Plan

None — plan executed exactly as written. All 6 hooks and 3 components match spec. Badge configs match Pattern 3 exactly.

## Issues Encountered

`npm run build` fails with 37 pre-existing TypeScript errors in unrelated files (FlywheelWheel.tsx, PipelinePage.tsx, BriefingCard.tsx, ChatStream.tsx, etc.). These predate this plan — confirmed by git stash reverting my changes and re-running the build which showed the same 37 errors. The `npx tsc --noEmit` check (plan verification criterion) passes with zero errors for all meetings files.

## Self-Check

- [x] `frontend/src/features/meetings/types/meetings.ts` — exists
- [x] `frontend/src/features/meetings/api.ts` — exists
- [x] `frontend/src/features/meetings/hooks/useMeetingProcessing.ts` — exists
- [x] `frontend/src/features/meetings/components/MeetingsPage.tsx` — exists
- [x] `frontend/src/features/meetings/components/MeetingDetailPage.tsx` — exists
- [x] Commit `1549de9` — exists (git log confirms)
- [x] TypeScript passes with `npx tsc --noEmit` — zero errors

## Self-Check: PASSED

## Next Phase Readiness

- Plan 62-02 (Granola settings panel) can proceed immediately — it uses `syncMeetings()` and `queryKeys.meetings.all` from this plan's `api.ts`
- Plan 62-03 (backend relationship enrichment) is independent of this plan's frontend work

---
*Phase: 62-meeting-surfaces-and-relationship-enrichment*
*Completed: 2026-03-28*
