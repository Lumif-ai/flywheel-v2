---
phase: 57-relationship-surfaces
plan: 04
subsystem: ui
tags: [react, typescript, lucide, sonner, avatar, branded-card, empty-state, tabs]

requires:
  - phase: 57-03
    provides: RelationshipDetail two-panel shell with placeholder tab content and TAB_CONFIG
  - phase: 57-01
    provides: relationships types (TimelineItem, ContactItem, RelationshipDetailItem, RelationshipType)

provides:
  - TimelineTab component with icon rows, direction arrows, expand-on-click, show-more
  - PeopleTab component with 2-column contact card grid, 48px avatars, role badges, "Added X ago"
  - IntelligenceTab component with 6 labeled intel fields and inline edit stubs
  - CommitmentsTab component with two-column layout (What You Owe / What They Owe)
  - RelationshipActionBar sticky bottom bar with type-specific action buttons
  - RelationshipDetail.tsx wired to all 4 real tab components and action bar

affects:
  - 57-05 (AskPanel — left panel already present, tabs done)

tech-stack:
  added: []
  patterns:
    - "timeAgo/daysAgo helpers defined locally in each tab component — no shared util needed yet"
    - "lookupValue with case-insensitive key matching for intel JSONB fields"
    - "ACTION_CONFIG Record<RelationshipType, ActionConfig[]> drives type-specific action bar buttons"
    - "Empty state fallback inside each tab (not a single wrapper) — tabs own their empty rendering"

key-files:
  created:
    - frontend/src/features/relationships/components/tabs/TimelineTab.tsx
    - frontend/src/features/relationships/components/tabs/PeopleTab.tsx
    - frontend/src/features/relationships/components/tabs/IntelligenceTab.tsx
    - frontend/src/features/relationships/components/tabs/CommitmentsTab.tsx
    - frontend/src/features/relationships/components/RelationshipActionBar.tsx
  modified:
    - frontend/src/features/relationships/components/RelationshipDetail.tsx

key-decisions:
  - "timeAgo/daysAgo helpers are inline per-component — avoids premature shared-util extraction"
  - "IntelligenceTab lookupValue does two passes: direct key match then case-insensitive scan — robust to any JSONB key casing"
  - "CommitmentsTab renders two-column structure even when empty — spec requires column headers to always show"
  - "RelationshipActionBar uses toast.info stubs for all actions — no real backend calls in this phase"
  - "RelationshipDetail uses explicit TabsContent per tab key (not map) — avoids rendering Intelligence tab content for advisor/investor (TAB_CONFIG still drives TabsTrigger visibility)"

duration: 12min
completed: 2026-03-27
---

# Phase 57 Plan 04: Relationship Surfaces — Tab Components and Action Bar Summary

**4 tab content components (Timeline, People, Intelligence, Commitments) plus sticky type-specific action bar wired into RelationshipDetail, completing the information architecture of the relationship detail page.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-27T00:00:00Z
- **Completed:** 2026-03-27
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Built TimelineTab with icon-per-source, direction arrows (inbound/outbound), contact name, time-ago, expand-on-click per entry, and "Show N more" truncation
- Built PeopleTab with 2-column grid of BrandedCards — 48px Avatar, initials, role badge with coral inline styles, mailto link, LinkedIn icon, "Added X ago" from `created_at`
- Built IntelligenceTab with 6 labeled JSONB fields (Pain, Budget, Competition, Champion, Blocker, Fit Reasoning), case-insensitive lookup, hover edit icon with toast stub, and empty state guard
- Built CommitmentsTab with two-column layout (What You Owe / What They Owe) with future-proofed overdue highlighting; renders column structure even when empty
- Built RelationshipActionBar as sticky bottom bar with ACTION_CONFIG driving type-specific buttons — all actions toast.info stubs
- Updated RelationshipDetail to import and render all 4 tab components plus action bar; Intelligence tab only visible for prospect/customer via TAB_CONFIG

## Task Commits

1. **Task 1: Timeline, People, Intelligence, Commitments tabs** — included in `1474ff3` (feat)
2. **Task 2: Action bar and wiring** — included in `1474ff3` (feat)

**Plan commit:** `1474ff3` feat(57-04): tab components and action bar for relationship detail

## Files Created/Modified
- `frontend/src/features/relationships/components/tabs/TimelineTab.tsx` — Annotated timeline with icon, direction, contact, time-ago, expand/collapse, show-more
- `frontend/src/features/relationships/components/tabs/PeopleTab.tsx` — Contact cards 2-col grid with avatar, role badge, email/LinkedIn links, "Added X ago"
- `frontend/src/features/relationships/components/tabs/IntelligenceTab.tsx` — 6-field JSONB grid with case-insensitive key lookup and hover-edit toast stubs
- `frontend/src/features/relationships/components/tabs/CommitmentsTab.tsx` — Two-column commitments layout with future-proof overdue highlighting
- `frontend/src/features/relationships/components/RelationshipActionBar.tsx` — Sticky bottom bar with type-specific action buttons (toast stubs)
- `frontend/src/features/relationships/components/RelationshipDetail.tsx` — Wired all 4 tabs + action bar; replaced placeholder "Coming soon..." divs

## Decisions Made
- `lookupValue` does two passes on the intel object (direct key match, then case-insensitive) — JSONB from the backend may use various casings depending on how notes were processed
- `CommitmentsTab` renders the two-column structure always (not a single empty state) — the column headers "What You Owe / What They Owe" provide UI affordance even before any data exists
- `RelationshipDetail` uses explicit `<TabsContent value="intelligence">` outside the `.map()` rather than mapping all tabs — ensures the Intelligence content node is never rendered for advisor/investor; TAB_CONFIG already excludes the trigger, but this makes the content-rendering boundary explicit

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Zero TypeScript errors on first compile pass.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- All 4 tab components are production-quality with proper empty states
- Action bar in place; ready for Phase 05 (AskPanel) to replace the left panel placeholder
- Intelligence tab properly gated to prospect/customer only via TAB_CONFIG + explicit TabsContent
- Toast stubs on action bar ready to be replaced with real actions in future phases

## Self-Check: PASSED

- All 6 files created/modified: FOUND
- Plan commit 1474ff3: FOUND
- TypeScript: 0 errors

---
*Phase: 57-relationship-surfaces*
*Completed: 2026-03-27*
