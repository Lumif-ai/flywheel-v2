---
phase: 05-review-api-and-frontend
plan: 02
subsystem: ui
tags: [react, typescript, zustand, react-query, tanstack-virtual, tailwind]

requires:
  - phase: 05-01
    provides: "Backend email read API — GET /email/threads, GET /email/threads/:id, POST /email/sync, POST/PUT /email/drafts/:id/*, digest"

provides:
  - "TypeScript interfaces for all email API response shapes (Thread, Message, Score, Draft, ThreadDetailResponse, FlatItem)"
  - "Zustand emailStore (selectedThreadId, detailOpen, alertDismissedIds)"
  - "useEmailThreads, useThreadDetail, useDraftActions (approve/dismiss/edit), useManualSync React Query hooks"
  - "Virtual-scrolled ThreadList with priority tier group headers (~20 DOM nodes regardless of thread count)"
  - "ThreadCard with priority badge, draft indicator, unread styling, relative timestamps"
  - "ThreadDetail slide-in Sheet panel with messages, scores, reasoning collapsible, context ref chips"
  - "DraftReview with approve/edit/dismiss, edit mode textarea, loading spinners, sent success state"
  - "EmailPage shell with priority filter dropdown, Sync button, thread count"
  - "Lazy-loaded /email route registered in routes.tsx"

affects: [05-03-alerts-and-digest]

tech-stack:
  added: ["@tanstack/react-virtual ^3.13.23"]
  patterns:
    - "useVirtualizer with parentRef + constrained height container for 500+ item lists"
    - "FlatItem discriminated union for virtualizing heterogeneous rows (headers + thread cards)"
    - "Sheet from @base-ui/react/dialog controlled by Zustand store (detailOpen/closeDetail)"
    - "React Query hooks follow useBriefing.ts pattern: queryKey array, staleTime 30_000"
    - "Mutation hooks invalidate both ['email-threads'] and ['thread-detail'] on success"

key-files:
  created:
    - frontend/src/features/email/types/email.ts
    - frontend/src/features/email/store/emailStore.ts
    - frontend/src/features/email/hooks/useEmailThreads.ts
    - frontend/src/features/email/hooks/useThreadDetail.ts
    - frontend/src/features/email/hooks/useDraftActions.ts
    - frontend/src/features/email/hooks/useManualSync.ts
    - frontend/src/features/email/components/ThreadCard.tsx
    - frontend/src/features/email/components/ThreadList.tsx
    - frontend/src/features/email/components/DraftReview.tsx
    - frontend/src/features/email/components/ThreadDetail.tsx
    - frontend/src/features/email/components/EmailPage.tsx
  modified:
    - frontend/src/app/routes.tsx

key-decisions:
  - "FlatItem discriminated union for virtualizer — enables headers + thread rows in single pass without separate header tracking"
  - "TIER_ORDER sorted before flatItems build — deterministic sort by tier priority then recency within tier"
  - "ThreadDetail reads store internally (no props) — keeps EmailPage lean, Sheet is self-contained"
  - "DraftReview: user_edits ?? draft_body for display — preserves original for Phase 6 diff analysis (matches backend decision)"
  - "EmailPage: flex-1 min-h-0 on list container — required for virtualization when parent is flex column"

patterns-established:
  - "Virtual list pattern: useVirtualizer with absolute positioning + translateY(start) for first virtual item"
  - "Email store follows useUIStore pattern from stores/ui.ts — create<State>(set => ...)"

duration: 3min
completed: 2026-03-24
---

# Phase 5 Plan 02: Email Inbox Frontend Summary

**Virtual-scrolled email inbox UI with Zustand store, React Query hooks, priority-grouped ThreadList, slide-in ThreadDetail panel, DraftReview approve/edit/dismiss, and lazy /email route**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-24T14:31:56Z
- **Completed:** 2026-03-24T14:35:42Z
- **Tasks:** 2 of 2
- **Files modified:** 14 (11 created, 3 modified)

## Accomplishments

- Complete `frontend/src/features/email/` feature directory with all types, store, hooks, and components
- Virtual scrolling active via `@tanstack/react-virtual` — only ~20 DOM nodes rendered at any thread count
- Full draft workflow: approve (POST /approve), edit (PUT /:id), dismiss (POST /dismiss) with React Query invalidation
- Slide-in Sheet panel shows per-message scores, reasoning (collapsible), and context ref chips from Phase 3

## Task Commits

Both tasks were delivered in a single feature commit:

1. **Task 1 + Task 2: All email feature files** — `dec1169` (feat)

## Files Created/Modified

- `frontend/src/features/email/types/email.ts` — Thread, Message, Score, Draft, ThreadDetailResponse, FlatItem TypeScript interfaces
- `frontend/src/features/email/store/emailStore.ts` — Zustand store (selectedThreadId, detailOpen, alertDismissedIds)
- `frontend/src/features/email/hooks/useEmailThreads.ts` — GET /email/threads with priority_min/offset/limit params
- `frontend/src/features/email/hooks/useThreadDetail.ts` — GET /email/threads/:threadId, enabled: !!threadId
- `frontend/src/features/email/hooks/useDraftActions.ts` — useApproveDraft, useDismissDraft, useEditDraft mutations
- `frontend/src/features/email/hooks/useManualSync.ts` — POST /email/sync mutation
- `frontend/src/features/email/components/ThreadCard.tsx` — Priority badges, draft indicator, unread bold, relative time
- `frontend/src/features/email/components/ThreadList.tsx` — useVirtualizer with tier group headers
- `frontend/src/features/email/components/DraftReview.tsx` — Approve/edit/dismiss with loading states
- `frontend/src/features/email/components/ThreadDetail.tsx` — Sheet panel with messages + scores + DraftReview
- `frontend/src/features/email/components/EmailPage.tsx` — Page shell with priority filter + Sync button
- `frontend/src/app/routes.tsx` — Added lazy /email route

## Decisions Made

- FlatItem discriminated union lets the virtualizer handle both header rows (40px) and thread rows (84px) in a single `count`
- `TIER_ORDER` sort ensures critical threads always appear first, recency within tier as tiebreaker
- ThreadDetail is self-contained (reads Zustand store directly) — no prop drilling through EmailPage
- `DraftReview` uses `user_edits ?? draft_body` for display — consistent with backend: user_edits preserves original for Phase 6 diff analysis
- `flex-1 min-h-0` on the list container is required for virtualization to work in a flex column layout

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. TypeScript type check passed on first compilation attempt.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `/email` route is live and lazy-loaded
- All hooks wire directly to the backend API paths from Phase 5 Plan 01
- Phase 5 Plan 03 (alerts + digest frontend) can now be built — the emailStore.alertDismissedIds and useManualSync hook are already in place

---
*Phase: 05-review-api-and-frontend*
*Completed: 2026-03-24*
