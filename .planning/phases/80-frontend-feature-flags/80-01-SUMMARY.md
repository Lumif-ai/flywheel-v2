---
phase: 80-frontend-feature-flags
plan: 01
subsystem: ui
tags: [vite, feature-flags, react-router, compile-time]

# Dependency graph
requires: []
provides:
  - "FEATURE_EMAIL and FEATURE_TASKS compile-time boolean constants"
  - "Gated routes with redirect fallback for disabled features"
  - "Conditional sidebar nav items"
  - "Two-component AuthenticatedAlerts pattern preventing unnecessary API calls"
affects: [frontend-features, design-partner-demo, email, tasks]

# Tech tracking
tech-stack:
  added: []
  patterns: ["compile-time feature flags via Vite env vars", "two-component pattern for conditional hook calls"]

key-files:
  created:
    - "frontend/src/lib/feature-flags.ts"
  modified:
    - "frontend/src/vite-env.d.ts"
    - "frontend/src/app/routes.tsx"
    - "frontend/src/features/navigation/components/AppSidebar.tsx"
    - "frontend/src/app/layout.tsx"

key-decisions:
  - "Default-to-enabled pattern (!== 'false') so developers without env vars get all features"
  - "Two-component AuthenticatedAlerts pattern to prevent useEmailThreads() hook from firing when email disabled"

patterns-established:
  - "Feature flag module: centralized boolean constants evaluated at compile time via import.meta.env"
  - "Two-component pattern: outer component gates on flag, inner component calls hooks -- avoids conditional hook calls"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 80 Plan 01: Feature Flags Summary

**Compile-time feature flags gating email and tasks routes, nav items, and global alerts via VITE_FEATURE_EMAIL/VITE_FEATURE_TASKS env vars**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T18:04:15Z
- **Completed:** 2026-03-30T18:06:15Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created centralized feature-flags module with JSDoc documentation and default-to-enabled semantics
- Gated /email and /tasks routes with Navigate redirect fallbacks for disabled features
- Conditional sidebar nav items hidden when respective feature flag is false
- Refactored AuthenticatedAlerts to two-component pattern preventing useEmailThreads() from firing when email is disabled

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `6066cfa` (feat: compile-time feature flags for email and tasks)

## Files Created/Modified
- `frontend/src/lib/feature-flags.ts` - Centralized FEATURE_EMAIL and FEATURE_TASKS boolean constants with JSDoc
- `frontend/src/vite-env.d.ts` - TypeScript declarations for VITE_FEATURE_EMAIL and VITE_FEATURE_TASKS
- `frontend/src/app/routes.tsx` - Conditional route rendering with redirect fallback for gated features
- `frontend/src/features/navigation/components/AppSidebar.tsx` - Conditional nav items gated by feature flags
- `frontend/src/app/layout.tsx` - Two-component AuthenticatedAlerts pattern gated behind FEATURE_EMAIL

## Decisions Made
- Default-to-enabled pattern (`!== 'false'`) ensures developers without env vars see all features -- only explicit `VITE_FEATURE_EMAIL=false` disables
- Two-component AuthenticatedAlerts/EmailAlertInner pattern chosen to avoid conditional hook calls while ensuring useEmailThreads() never fires when email is disabled

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing TypeScript errors in pipeline, profile, streams, and tasks files cause `tsc -b` (used by `npm run build`) to fail. These are unrelated to feature flag changes. `tsc --noEmit` passes clean and `vite build` succeeds.

## User Setup Required

None - no external service configuration required. To disable features for design partners, set env vars before build:
- `VITE_FEATURE_EMAIL=false` -- hides email everywhere
- `VITE_FEATURE_TASKS=false` -- hides tasks everywhere

## Next Phase Readiness
- Feature flags are ready for use in design partner deployments
- Pattern is extensible -- new features can be gated by adding constants to feature-flags.ts

---
*Phase: 80-frontend-feature-flags*
*Completed: 2026-03-30*
