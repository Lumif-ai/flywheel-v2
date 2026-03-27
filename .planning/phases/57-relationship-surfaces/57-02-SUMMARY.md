---
phase: 57-relationship-surfaces
plan: "02"
subsystem: ui
tags: [relationships, card-grid, responsive, urgency-sort, empty-state, design-tokens]

requires:
  - phase: 57-01
    provides: RelationshipListPage placeholder, RelationshipType, RelationshipListItem, useRelationships hook, registers/spacing/typography design tokens
provides:
  - RelationshipCard component with urgency border, avatar, status badge, signal count, time ago
  - RelationshipListPage full implementation with warm tint register, responsive 3-col grid, shimmer loading, type-specific empty states
affects: [57-03, 57-04, 57-05]

tech-stack:
  added: []
  patterns:
    - "Urgency sort: signal_count desc then last_interaction_at desc (nulls last) — client-side on already-loaded list data"
    - "Register pattern applied: relationship pages always use registers.relationship.background (warm tint)"
    - "fromType URL param on every card click — /relationships/:id?fromType=prospect ensures detail page context"
    - "BrandedCard variant='action' for signal_count > 0 (coral left border), variant='info' otherwise"
    - "TYPE_CONFIG lookup object drives type-specific icon, label, empty description — single source of truth"

key-files:
  created:
    - frontend/src/features/relationships/components/RelationshipCard.tsx
  modified:
    - frontend/src/features/relationships/components/RelationshipListPage.tsx

key-decisions:
  - "[57-02] RelationshipCard uses BrandedCard variant='action' (coral left border) when signal_count > 0, 'info' otherwise — consistent with pipeline row styling"
  - "[57-02] formatTimeAgo inline helper returns 'Xd ago', 'Xh ago', or 'just now' — same logic as AccountsPage.formatRelativeTime"
  - "[57-02] TYPE_CONFIG object maps RelationshipType to label/icon/emptyDescription — avoids scattered switch statements"
  - "[57-02] ai_summary truncated at 120 chars client-side with ellipsis — consistent with plan spec; no line-clamp dependency needed"

patterns-established:
  - "Urgency sort function: sortByUrgency() — reusable pattern for any list that needs signal-first ordering"
  - "Responsive card grid: grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 — standard 3-col layout for relationship surfaces"

duration: ~4min
completed: 2026-03-27
---

# Phase 57 Plan 02: Relationship Card Grid Summary

**Responsive card grid for all 4 relationship types — warm tint background, urgency sort (signal_count desc), coral urgency borders, shimmer loading, type-specific empty states with Pipeline CTA**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-27T12:46:22Z
- **Completed:** 2026-03-27T12:50:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- RelationshipCard renders avatar (initials), name, domain, status badge with coral rgba, entity_level, ai_summary preview (120 chars), primary_contact_name with Users icon, last_interaction_at as relative time, signal count badge — coral left border when signal_count > 0
- RelationshipListPage replaces placeholder with warm tint register background, responsive 3-col grid, client-side urgency sort, 6 shimmer skeletons during load, type-specific empty states (unique icon + description per type), error state with retry
- All 4 relationship URLs (/relationships/prospects, /customers, /advisors, /investors) now render full grid pages
- fromType URL param propagated on every card click for detail page context

## Task Commits

All tasks committed as a single plan-level commit (per-plan strategy):

1. **Tasks 1+2: RelationshipCard + RelationshipListPage** — `4abd7ca` (feat)

## Files Created/Modified

- `frontend/src/features/relationships/components/RelationshipCard.tsx` — Individual card with urgency border, avatar, badge, time ago, signal count; navigates to `/relationships/:id?fromType=type`
- `frontend/src/features/relationships/components/RelationshipListPage.tsx` — Replaced placeholder; full card grid with warm tint, urgency sort, loading/empty/error states

## Decisions Made

- BrandedCard `variant='action'` (coral border) used when `signal_count > 0` — directly maps urgency signal to visual priority; `'info'` (no border) otherwise
- `formatTimeAgo` implemented inline in RelationshipCard following AccountsPage pattern — returns "Xd ago", "Xh ago", "just now"
- `TYPE_CONFIG` lookup object (single source of truth) drives label, icon, empty state copy per RelationshipType — no scattered switch statements
- ai_summary truncated at 120 chars with `…` client-side; no extra dependency needed

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — `npx tsc --noEmit` passed with zero errors on first attempt.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- RelationshipCard and RelationshipListPage complete — Plan 03 (RelationshipDetail) can proceed
- fromType param is ready and consistent on all card clicks
- Warm tint register established on all 4 relationship list URLs

## Self-Check: PASSED

Files verified:
- FOUND: frontend/src/features/relationships/components/RelationshipCard.tsx
- FOUND: frontend/src/features/relationships/components/RelationshipListPage.tsx
- FOUND: .planning/phases/57-relationship-surfaces/57-02-SUMMARY.md

Commit verified: 4abd7ca — feat(57-02): relationship card grid with urgency sort and empty states

---
*Phase: 57-relationship-surfaces*
*Completed: 2026-03-27*
