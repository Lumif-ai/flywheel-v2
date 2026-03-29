---
phase: 05-review-api-and-frontend
plan: 03
subsystem: ui
tags: [react, sonner, toast, zustand, react-query, email, sidebar]

# Dependency graph
requires:
  - phase: 05-02
    provides: "ThreadList, ThreadDetail, emailStore with alertDismissedIds/dismissAlert, useEmailThreads hook"
  - phase: 05-01
    provides: "GET /email/threads and GET /email/digest backend API endpoints"
provides:
  - "Sonner Toaster mounted globally at app root — toasts visible on all pages"
  - "CriticalEmailAlert renderless component — fires persistent toast.warning for max_priority=5 threads"
  - "alertDismissedIds deduplication — dismissed alerts never re-fire across 30s refetches"
  - "useDailyDigest hook — GET /email/digest with 5min staleTime"
  - "DigestView component — low-priority threads grouped by category with click-to-select"
  - "EmailPage Inbox/Digest toggle — switches between virtual ThreadList and DigestView"
  - "Email nav link in AppSidebar with Mail icon"
  - "DigestThread + DigestResponse types added to email.ts"
affects: [phase-06, email-alerts, email-digest]

# Tech tracking
tech-stack:
  added: ["sonner ^2.0.7 (toast notifications)"]
  patterns:
    - "Renderless alert component pattern — CriticalEmailAlert fires side effects (toasts) from props"
    - "Two-layer deduplication — Sonner id-based (same render) + Zustand alertDismissedIds (across refetches)"
    - "Global query in AppShell — lightweight React Query call shared via cache with page-level component"

key-files:
  created:
    - "frontend/src/components/ui/sonner.tsx"
    - "frontend/src/features/email/components/CriticalEmailAlert.tsx"
    - "frontend/src/features/email/components/DigestView.tsx"
    - "frontend/src/features/email/hooks/useDailyDigest.ts"
  modified:
    - "frontend/src/app/layout.tsx"
    - "frontend/src/features/email/components/EmailPage.tsx"
    - "frontend/src/features/email/types/email.ts"
    - "frontend/src/features/navigation/components/AppSidebar.tsx"
    - "frontend/package.json"

key-decisions:
  - "Removed next-themes dep from shadcn-generated sonner.tsx — project uses no theme provider; hardcoded light theme with CSS var token mapping"
  - "Toaster mounted outside BrowserRouter (at QueryClientProvider level) — ensures it renders even before routing is resolved"
  - "CriticalEmailAlert calls dismissAlert() immediately after toast() — marks thread as alerted so 30s refetch skips it; Sonner id handles same-render deduplication"
  - "useEmailThreads() called in AppShell (non-standalone branch only) — avoids firing tenant-dependent API calls on onboarding/invite routes"
  - "DigestView uses selectThread (Zustand) for row clicks — opens ThreadDetail Sheet without navigation; consistent with inbox behavior"
  - "Priority filter hidden in Digest view — not applicable to low-priority digest content"

patterns-established:
  - "Renderless side-effect component: return null, logic in useEffect — CriticalEmailAlert"
  - "shadcn component post-install audit: always check generated code for incompatible deps (next-themes, next/font, etc.)"

# Metrics
duration: 15min
completed: 2026-03-24
---

# Phase 5 Plan 03: Alerts and Digest Frontend Summary

**Sonner toast alerts for priority-5 emails (global, persistent, deduplicated) and daily digest view grouped by category with Inbox/Digest toggle in EmailPage**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T (session start)
- **Completed:** 2026-03-24
- **Tasks:** 2
- **Files modified:** 9 (4 created, 5 modified)

## Accomplishments

- Sonner installed and Toaster mounted at app root — toast alerts appear on any page, not just /email
- CriticalEmailAlert renderless component: priority-5 threads trigger persistent `toast.warning` with "View" action navigating to the thread; two-layer deduplication prevents repeat toasts
- Daily digest: `useDailyDigest` hook + `DigestView` component with category grouping, empty state, and clickable rows; EmailPage has Inbox/Digest toggle
- Email nav link added to AppSidebar with Mail icon
- TypeScript compiles clean (`tsc --noEmit` zero errors)

## Task Commits

Plan committed atomically (per-plan strategy):

1. **Tasks 1 + 2: Sonner alerts + digest + sidebar** - `69d06ec` (feat)

**Plan metadata:** (created in final state update commit)

## Files Created/Modified

- `frontend/src/components/ui/sonner.tsx` — Themed Toaster wrapper (fixed next-themes dep from shadcn output)
- `frontend/src/features/email/components/CriticalEmailAlert.tsx` — Renderless alert component, fires toast.warning for max_priority===5 threads
- `frontend/src/features/email/components/DigestView.tsx` — Daily digest grouped by category, empty state, clickable rows
- `frontend/src/features/email/hooks/useDailyDigest.ts` — React Query hook for GET /email/digest
- `frontend/src/app/layout.tsx` — Mounts Toaster + CriticalEmailAlert (with useEmailThreads) in AppShell
- `frontend/src/features/email/components/EmailPage.tsx` — Inbox/Digest toggle; renders DigestView when digest selected
- `frontend/src/features/email/types/email.ts` — Added DigestThread + DigestResponse types
- `frontend/src/features/navigation/components/AppSidebar.tsx` — Email nav link with Mail icon after Documents
- `frontend/package.json` + `package-lock.json` — sonner ^2.0.7 added

## Decisions Made

- **Removed next-themes from sonner.tsx**: shadcn generated code with `useTheme` from `next-themes` which is not in this project. Fixed to use `theme="light"` directly with CSS var token mapping — no behavior change, eliminates broken import.
- **Toaster outside BrowserRouter**: `<Toaster>` sits at `QueryClientProvider` level (outside `<BrowserRouter>`), while `CriticalEmailAlert` (which uses `useNavigate`) sits inside `<BrowserRouter>` in AppShell. This ensures toasts appear immediately and navigation in the action button works correctly.
- **useEmailThreads in AppShell**: Called only when `!isStandalone` — avoids firing tenant-dependent API calls on onboarding/invite routes.
- **CriticalEmailAlert: dismissAlert immediately after toast()**: The toast fires for undismissed threads; `dismissAlert()` is called right after so the Zustand set of dismissed ids grows immediately. On the next 30s React Query refetch, those threads are already in `alertDismissedIds` and are skipped. Sonner's `id:` deduplication handles the same-session case.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed incompatible next-themes import from shadcn-generated sonner.tsx**
- **Found during:** Task 1 (Install Sonner)
- **Issue:** shadcn generated `sonner.tsx` imports `useTheme` from `next-themes`, which is not installed in this project. Would cause a build error.
- **Fix:** Rewrote `sonner.tsx` to use `theme="light"` directly and map design tokens via CSS vars — equivalent visual output, no external dep.
- **Files modified:** `frontend/src/components/ui/sonner.tsx`
- **Verification:** `tsc --noEmit` passes, no import errors
- **Committed in:** `69d06ec`

---

**Total deviations:** 1 auto-fixed (Rule 1 - incompatible generated dep)
**Impact on plan:** Necessary for build correctness. No scope creep.

## Issues Encountered

None beyond the shadcn-generated next-themes issue (handled as deviation above).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 5 is now fully complete:
- 05-01: Backend API (thread list, thread detail, digest, manual sync)
- 05-02: Email inbox UI (virtual ThreadList, ThreadDetail Sheet, DraftReview)
- 05-03: Alerts and digest frontend (Sonner toasts, DigestView, sidebar nav)

Ready for Phase 6: Voice profile editing / settings / production readiness (per ROADMAP).

---
*Phase: 05-review-api-and-frontend*
*Completed: 2026-03-24*
