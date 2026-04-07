---
phase: 082-leads-pipeline-frontend
plan: 03
subsystem: ui
tags: [react, side-panel, accordion, timeline, graduation, dialog, navigation]

requires:
  - phase: 82-02
    provides: LeadsPage orchestrator with selectedLead/graduatingId states, ag-grid table, funnel, filters
provides:
  - LeadSidePanel with company info, contacts accordion, and graduate button
  - ContactCard expandable accordion with message threads
  - MessageThread vertical timeline with expand/collapse per message
  - Graduation confirmation dialog wired in LeadsPage
  - Leads nav item in sidebar above Pipeline
affects: [leads-feature-complete]

tech-stack:
  added: []
  patterns: [CSS grid expand trick, focus trap via ref, escape key handler, dialog with mutation guard]

key-files:
  created:
    - frontend/src/features/leads/components/MessageThread.tsx
    - frontend/src/features/leads/components/ContactCard.tsx
    - frontend/src/features/leads/components/LeadSidePanel.tsx
  modified:
    - frontend/src/features/leads/components/LeadsPage.tsx
    - frontend/src/features/navigation/components/AppSidebar.tsx

key-decisions:
  - "Focus trap via panelRef + previous focus restore on unmount (lightweight, no dependency)"
  - "Dialog open guard excludes isPending state to prevent re-trigger during mutation"
  - "Graduating lead name resolved from items array OR selectedLead for both table and panel trigger paths"
  - "Sidebar Leads item uses Users icon (same as Prospects) — distinct by label and position"

duration: 4min
completed: 2026-04-01
---

# Phase 82 Plan 03: Side Panel, Contacts, Messages, Graduation Summary

**Lead detail panel with contacts accordion and message timelines, graduation confirmation dialog, and Leads sidebar navigation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-01T08:05:30Z
- **Completed:** 2026-04-01T08:09:05Z
- **Tasks:** 2
- **Files created:** 3
- **Files modified:** 2

## Accomplishments
- MessageThread component: vertical timeline with numbered circles, connecting lines, channel icons (Mail/Linkedin), status dots, expand/collapse per message with CSS grid trick, prefers-reduced-motion support
- ContactCard component: expandable accordion item with avatar initials, name/title/role, per-contact StageBadge, ChevronDown rotation, email/linkedin links, embedded MessageThread
- LeadSidePanel component: fixed right panel (440px) with slide-in animation, header with company name + close button, company info section (domain link, stage/fit/purpose badges, fit rationale), contacts section with accordion (one expanded at a time), loading skeleton, error/retry, empty state, graduate button with coral gradient, Escape key handler, focus management (save/restore previous focus)
- Graduation confirmation dialog wired into LeadsPage: Dialog with title/description showing lead name (resolved from items or selectedLead), Cancel + Graduate buttons, mutation triggers useLeadGraduate hook with panel close + row animation timeout
- Leads nav item added to AppSidebar above Pipeline with Users icon

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **Task 1: ContactCard, MessageThread, LeadSidePanel** - `8da7c81` (feat)
2. **Task 2: Wire side panel, graduation dialog, sidebar nav** - `8da7c81` (feat)

## Files Created/Modified
- `frontend/src/features/leads/components/MessageThread.tsx` - Vertical timeline with numbered nodes, status colors, expand/collapse, channel icons
- `frontend/src/features/leads/components/ContactCard.tsx` - Accordion contact card with avatar, details, embedded message thread
- `frontend/src/features/leads/components/LeadSidePanel.tsx` - Right detail panel with company info, contacts list, graduate button, focus trap, animations
- `frontend/src/features/leads/components/LeadsPage.tsx` - Added side panel rendering, graduation dialog, useLeadGraduate hook, removed void suppressors
- `frontend/src/features/navigation/components/AppSidebar.tsx` - Added Leads nav item with Users icon above Pipeline

## Decisions Made
- Focus trap implemented via panelRef.focus() on mount + previousFocusRef restore on unmount (no external focus-trap library needed)
- Dialog open state guards against isPending to prevent re-opening during mutation execution
- Graduating lead name resolved from both items array and selectedLead to handle table-button and panel-button trigger paths
- Sidebar Leads item placed above Pipeline using Users icon, matching the outbound flow order (leads precede pipeline)

## Deviations from Plan

None - plan executed exactly as written. Route registration and sidebar were already partially addressed in plan 02 (route), so only sidebar nav item was added in this plan.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete leads pipeline feature is now functional end-to-end
- All 5 success criteria from the phase verification are addressed:
  1. /leads route renders funnel with clickable stage segments
  2. ag-grid table with 8 columns and server-side pagination
  3. Row click opens side panel with company info, contacts accordion, message threads
  4. Funnel clicks, filter dropdowns, and search all sync and filter the table
  5. Graduate button in both table and panel triggers confirmation dialog + mutation

---
*Phase: 082-leads-pipeline-frontend*
*Completed: 2026-04-01*
