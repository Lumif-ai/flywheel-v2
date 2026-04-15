---
phase: 137-workflow-frontend-a
plan: "03"
subsystem: broker-frontend
tags: [requirements-panel, step-indicator, analysis-tab, stagger-animation]
dependency_graph:
  requires: [broker.ts types (ProjectCoverage, AnalysisStatus), ShimmerSkeleton, AnalysisTab (137-02)]
  provides: [RequirementCard, RequirementsPanel, updated AnalysisTab right pane, 6-step StepIndicator]
  affects: [AnalysisTab layout, StepIndicator dot count]
tech_stack:
  added: []
  patterns: [60ms per-card stagger via inline animationDelay, Intl.NumberFormat for currency formatting]
key_files:
  created:
    - frontend/src/features/broker/components/RequirementCard.tsx
    - frontend/src/features/broker/components/RequirementsPanel.tsx
  modified:
    - frontend/src/features/broker/components/tabs/AnalysisTab.tsx
    - frontend/src/features/broker/components/StepIndicator.tsx
decisions:
  - RequirementsPanel owns all state rendering (running/failed/empty/populated) — AnalysisTab right pane is a thin wrapper with header + scroll container
  - 60ms stagger applied via inline animationDelay (not staggerDelay() util which uses 50ms) — spec-mandated value
  - isFailed variable removed from AnalysisTab after delegating to RequirementsPanel to avoid unused variable TS warning
metrics:
  duration: ~10min
  completed: "2026-04-15"
  tasks_completed: 2
  files_changed: 4
---

# Phase 137 Plan 03: RequirementsPanel and 6-step StepIndicator — Summary

**One-liner:** RequirementCard with ANAL-04 fields (type, limit, confidence bar, clause, critical badge, gap status), RequirementsPanel with 60ms stagger + shimmer states, wired into AnalysisTab right pane, and StepIndicator extended to 6 steps with Analysis amber/green state machine.

## Tasks Completed

| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Create RequirementCard and RequirementsPanel | RequirementCard.tsx, RequirementsPanel.tsx | Done |
| 2 | Wire RequirementsPanel into AnalysisTab + update StepIndicator to 6 steps | AnalysisTab.tsx, StepIndicator.tsx | Done |

## What Was Built

### RequirementCard
Single `ProjectCoverage` as a card. Fields rendered:
- Display name / coverage_type (heading, truncated)
- Category badge (pill, muted)
- Critical badge (`ai_critical_finding === true` → red "Critical" pill)
- Gap status badge (covered=green, insufficient=amber, missing=red, unknown=muted)
- Confidence bar (coral `#E94D35` fill, width from CONFIDENCE_PCT map: high=90%, medium=60%, low=30%)
- Required limit formatted via `Intl.NumberFormat` as currency (hidden when null)
- Contract clause text (small, muted, line-clamp-2, shown when non-null)

### RequirementsPanel
List renderer with state branching:
- `running`: 4x ShimmerSkeleton placeholders
- `failed`: destructive error message with re-upload guidance
- `coverages.length === 0`: empty state prompting upload + analysis
- Populated: `RequirementCard` list with `animationDelay: index * 60ms` stagger (not the 50ms staggerDelay util)

### AnalysisTab right pane
Replaced inline shimmer/failed/empty/placeholder conditional block with a single `<RequirementsPanel>` call. Removed unused `isFailed` variable. Right pane is now a thin wrapper: header + scrollable container.

### StepIndicator
- WORKFLOW_STEPS extended from 5 to 6 entries: `overview → analysis → coverage → carriers → quotes → compare`
- `case 'analysis'` added to `getStepState`: grey (default) → amber (analyzing or running) → green (gaps_identified or beyond)
- Array literal edited directly (not `.push()`) to preserve `as const` typing

## Decisions Made

1. **RequirementsPanel owns all states** — right pane in AnalysisTab is a thin header + scroll wrapper; all state logic delegated to the panel. Keeps AnalysisTab presentation-only.
2. **60ms stagger is spec-mandated inline** — not via `staggerDelay()` util (which is 50ms). Applied as `animationDelay: \`${index * 60}ms\`` directly on the style prop.
3. **isFailed removed** — after delegating to RequirementsPanel the variable was unused; removed to keep TypeScript clean.

## Deviations from Plan

None — plan executed exactly as written.

## Success Criteria Met

- [x] ANAL-04: Requirement cards with all fields (type, limit, confidence bar, clause, critical badge, gap status)
- [x] ANAL-05: 60ms stagger animation (inline animationDelay, not staggerDelay)
- [x] ANAL-06: Shimmer in requirements panel during running state
- [x] ANAL-07: StepIndicator 5→6 steps with Analysis step state machine (grey→amber→green)

## Commit

`3659e93` — feat(137-03): RequirementsPanel with stagger cards, 6-step StepIndicator with Analysis state

## Self-Check: PASSED

- frontend/src/features/broker/components/RequirementCard.tsx — FOUND (created)
- frontend/src/features/broker/components/RequirementsPanel.tsx — FOUND (created)
- frontend/src/features/broker/components/tabs/AnalysisTab.tsx — FOUND (modified)
- frontend/src/features/broker/components/StepIndicator.tsx — FOUND (modified)
- Commit 3659e93 — FOUND
- `npx tsc --noEmit` — PASSED (zero errors)
