---
phase: 57-relationship-surfaces
plan: 05
subsystem: ui
tags: [react, tanstack-query, sonner, lucide-react, date-fns]

# Dependency graph
requires:
  - phase: 57-03
    provides: RelationshipDetail two-panel shell with left panel placeholder slot
  - phase: 57-01
    provides: useCreateNote, useAsk, useSynthesize hooks + AskResponse type
provides:
  - AskPanel component — AI context panel with dual-mode input (note vs Q&A), synthesis refresh, source citations
  - RelationshipDetail left panel slot replaced with live AskPanel
affects: [57-04, any future phases extending AI panel functionality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "4-state panel mode machine (idle/asking/saving_note/synthesizing) for input routing"
    - "Intent heuristic: text.trim().endsWith('?') routes to ask API, all other text saves as note"
    - "Per-plan commit strategy: single atomic commit after all tasks complete"

key-files:
  created:
    - frontend/src/features/relationships/components/AskPanel.tsx
  modified:
    - frontend/src/features/relationships/components/RelationshipDetail.tsx

key-decisions:
  - "lastAnswer is ephemeral (most recent Q&A only, lost on unmount) — stateless per locked design decision"
  - "Synthesis never auto-triggered on mount — null aiSummary shows graceful placeholder only"
  - "Auto-resize textarea capped at 6 rows (overflow hidden, height set via scrollHeight calculation)"
  - "Source citations rendered as left-bordered cards below Q&A answer for visual distinction"

patterns-established:
  - "AskPanel: useMutation callbacks (onSuccess/onError) passed inline to mutate() call — not on hook definition — for per-submission mode reset"

# Metrics
duration: 2min
completed: 2026-03-27
---

# Phase 57 Plan 05: AskPanel — AI Context Panel Summary

**AskPanel React component with 4-mode state machine routing ? input to ask API (with source citations) and all other text to note creation, wired into the RelationshipDetail left panel 320px slot.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T12:50:29Z
- **Completed:** 2026-03-27T12:52:05Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- AskPanel with explicit idle/asking/saving_note/synthesizing state machine — no implicit loading flags
- Dual-mode input: trailing ? routes to ask endpoint with source citations + insufficient_context warning; everything else saves as a ContextEntry note with "Note saved" toast
- Synthesis refresh button with animated RefreshCw spinner while pending; 429 rate limit handled in useSynthesize hook as user-friendly toast
- AI summary shows in brand-tint-colored card with relative "Updated X ago" timestamp; null summary shows italic placeholder (never auto-triggers synthesis)
- RelationshipDetail left panel placeholder div replaced with AskPanel wired to account.id, ai_summary, ai_summary_updated_at

## Task Commits

Plan batch commit (per-plan strategy — single commit after all tasks):

1. **Task 1 + Task 2** - `2ff0a39` (feat) — AskPanel + RelationshipDetail wiring

## Files Created/Modified
- `frontend/src/features/relationships/components/AskPanel.tsx` — AI context panel component (232 lines): state machine, intent heuristic, source citation cards, synthesis refresh
- `frontend/src/features/relationships/components/RelationshipDetail.tsx` — replaced AI Panel placeholder with live AskPanel component

## Decisions Made
- `lastAnswer` holds only the most recent Q&A response (ephemeral, lost on unmount) — stateless per design decision from 57-RESEARCH
- Synthesis never auto-triggered on mount — null `aiSummary` renders graceful italic placeholder text
- `onSuccess`/`onError` callbacks passed directly into `mutate()` call (not on hook definition) so mode resets correctly for each individual submission
- Auto-resize textarea capped at 6 rows via `scrollHeight` comparison in a `useEffect`

## Deviations from Plan

None — plan executed exactly as written. All must-have truths met:
- Left panel shows cached AI summary or graceful placeholder when null
- Input accepts both notes and Q&A questions
- Questions ending in ? route to ask endpoint; everything else saves as note
- Source citations appear with Q&A answers
- Rate limit (429) on synthesize surfaces as user-friendly toast via useSynthesize hook

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 57 Plan 05 complete — all 5 plans in Phase 57 now complete
- AskPanel is the final component in the v2.1 Relationship Surfaces milestone
- Full detail page is live: RelationshipHeader + AskPanel (left) + tab shell (right)
- Plan 04 tab content (Timeline, People, Intelligence, Commitments) is the remaining tab implementation if needed

---
*Phase: 57-relationship-surfaces*
*Completed: 2026-03-27*
