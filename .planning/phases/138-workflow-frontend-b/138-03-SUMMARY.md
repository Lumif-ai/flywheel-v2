---
phase: 138-workflow-frontend-b
plan: "03"
subsystem: broker-frontend
tags: [quote-tracking, ui, badges, expandable-rows, run-in-claude-code]
dependency_graph:
  requires: []
  provides: [QuoteTracking redesign, QUOT-01 through QUOT-05]
  affects: [frontend/src/features/broker/components/QuoteTracking.tsx]
tech_stack:
  added: []
  patterns: [expandable rows with state lifted to parent, single action button pattern]
key_files:
  created: []
  modified:
    - frontend/src/features/broker/components/QuoteTracking.tsx
decisions:
  - expandedQuoteId lifted to QuoteTracking parent (not per-row state) to allow single expansion at a time
  - allExtracted uses received+extracted (not extracted-only) to match QUOT-05 spec semantics
  - useExtractQuote removed entirely; RunInClaudeCodeButton is the sole extraction trigger
metrics:
  duration: "~10 minutes"
  completed: "2026-04-15"
  tasks_completed: 1
  files_changed: 1
---

# Phase 138 Plan 03: QuoteTracking Redesign Summary

Redesigned `QuoteTracking.tsx` satisfying all five QUOT requirements: received/pending summary badges, per-row carrier_type badge with premium display, expandable detail panels, single RunInClaudeCodeButton replacing per-row extract buttons, and an all-extracted completion card.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Redesign QuoteTracking with badges, expandable rows, single RunInClaudeCodeButton | 3380eda | frontend/src/features/broker/components/QuoteTracking.tsx |

## What Was Built

**QUOT-01 — Summary badges:** Header row now shows a green "X of Y received" badge and an orange animated-pulse "Z pending" badge when pending > 0. Counts computed from quote status array.

**QUOT-02 — Carrier type badge + premium:** Each QuoteRow header shows a blue "Insurance" or purple "Surety" badge after the carrier name. Premium is shown in emerald-700 bold when status is `extracted` and premium is non-null.

**QUOT-03 — Expandable detail panel:** `expandedQuoteId` state is managed in `QuoteTracking` (parent), passed to each `QuoteRow` as `isExpanded` + `onToggleExpand`. ChevronDown/ChevronUp button in each row header toggles the panel. Detail panel shows deductible, limit, exclusions, and source document when available.

**QUOT-04 — Single RunInClaudeCodeButton:** Placed below the header, above quote rows. Shown only when `quotes.some(q => q.status === 'received')`. Uses `variant="prominent"` (coral background). Per-row "Extract Quote" button and `useExtractQuote` hook removed entirely.

**QUOT-05 — Completion card:** When all quotes are in `extracted` or `received` status, a green card replaces the "Draft Follow-ups" button. Draft Follow-ups button still appears when `hasSolicited && !allExtracted`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `frontend/src/features/broker/components/QuoteTracking.tsx` — FOUND
- Commit 3380eda — FOUND (`git log --oneline | grep 3380eda`)
- `npx tsc --noEmit | grep QuoteTracking` — zero errors
- No `useExtractQuote` / `extractMutation` references remaining
- `RunInClaudeCodeButton` imported as named export from `./shared/RunInClaudeCodeButton`
- `animate-pulse` and received/pending badges present
