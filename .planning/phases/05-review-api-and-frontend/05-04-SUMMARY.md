---
phase: 05-review-api-and-frontend
plan: 04
subsystem: ui
tags: [react, typescript, zustand, react-router, react-query]

requires:
  - phase: 05-review-api-and-frontend
    provides: EmailPage, ThreadDetail, CriticalEmailAlert, AppShell with useEmailThreads

provides:
  - Priority filter values 5/4/3 matching backend ge=1 le=5 (eliminates HTTP 422)
  - useSearchParams in EmailPage auto-opens ThreadDetail Sheet from ?thread= query param
  - Dynamic per-message badge colors via priorityToTier() helper
  - useEmailThreads guarded inside AuthenticatedAlerts, never fires on standalone routes

affects: [phase-06]

tech-stack:
  added: []
  patterns:
    - AuthenticatedAlerts wrapper component — isolates hooks that require auth context from the standalone-route fast-path
    - priorityToTier() — maps numeric priority (1-5) to PriorityTier; mirrors backend tier mapping
    - useSearchParams + useEffect for URL-driven Sheet open — navigate('/email?thread=id') flows into selectThread() cleanly

key-files:
  created: []
  modified:
    - frontend/src/features/email/components/EmailPage.tsx
    - frontend/src/features/email/components/ThreadDetail.tsx
    - frontend/src/app/layout.tsx

key-decisions:
  - "IIFE pattern ((() => { ... })()) in JSX for msgTier computation — avoids extracting a const before the JSX block while keeping the helper call readable"
  - "useSearchParams + setSearchParams({}, { replace: true }) on mount — one-shot thread open that does not re-trigger on refresh"
  - "AuthenticatedAlerts wrapper (not conditional hook call) — React rules-of-hooks prohibit conditionally calling hooks; wrapper component is the correct fix"

duration: 2min
completed: 2026-03-24
---

# Phase 5 Plan 04: Gap Closure Summary

**Four targeted frontend fixes: corrected priority filter values (5/4/3), URL-driven ThreadDetail auto-open via useSearchParams, dynamic per-message badge tier colors, and useEmailThreads guarded behind AuthenticatedAlerts wrapper**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-24T16:13:16Z
- **Completed:** 2026-03-24T16:15:31Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Priority filter dropdown now sends values 5, 4, 3 to the backend — the HTTP 422 on every non-All filter selection is eliminated
- CriticalEmailAlert View button (`navigate('/email?thread=<id>')`) now actually opens the ThreadDetail Sheet on arrival at /email; query param is cleared after open to prevent re-trigger on refresh
- Per-message score badges in ThreadDetail now show red for critical (P5), orange for high (P4), amber for medium (P3), gray for low (P1-P2) — was all-red before
- useEmailThreads() is no longer called at the AppShell top level; it lives inside AuthenticatedAlerts which only renders in non-standalone branches — no 401 API calls on /onboarding or /invite

## Task Commits

All four fixes shipped in a single plan commit (gap_closure plan — no interdependencies between tasks):

1. **Tasks 1+2: All four fixes** - `aa87211` (fix)

## Files Created/Modified

- `frontend/src/features/email/components/EmailPage.tsx` — PRIORITY_FILTERS values 5/4/3, useSearchParams import, useEmailStore.selectThread wired in useEffect
- `frontend/src/features/email/components/ThreadDetail.tsx` — priorityToTier() helper added, IIFE in JSX replaces hardcoded TIER_COLORS.critical badge
- `frontend/src/app/layout.tsx` — AuthenticatedAlerts component extracted; useEmailThreads() moved inside it; AppShell top-level call removed

## Decisions Made

- **IIFE vs extracted const for msgTier:** Used an IIFE `(() => { const msgTier = ...; return <span> })()` inside JSX rather than adding a const before the JSX return. Keeps the computation co-located with its usage inside the `{message.score && (` block without restructuring the surrounding render logic.
- **AuthenticatedAlerts wrapper (not conditional hook):** React rules-of-hooks forbid calling hooks conditionally. The correct pattern is to extract a separate component that unconditionally calls the hook, then only render that component in the authenticated path.
- **setSearchParams({}, { replace: true }):** Clears the ?thread= param without adding a history entry, so the back button still works as expected.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. TypeScript compiled cleanly on first attempt.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All Phase 5 verification gaps are now closed
- Priority filtering, thread deep-linking, badge colors, and auth guard all operate correctly
- Phase 6 can proceed with a stable email inbox foundation

---
*Phase: 05-review-api-and-frontend*
*Completed: 2026-03-24*
