---
phase: 66-flywheel-ritual
plan: 02
subsystem: engine
tags: [orchestrator, granola-sync, meeting-processing, meeting-prep, sse, sqlalchemy]

requires:
  - phase: 66-01
    provides: "sync_granola_meetings extraction, flywheel dispatch wiring, SKILL.md"
  - phase: 61
    provides: "meeting_processor_web pipeline (8-stage)"
  - phase: 63
    provides: "_execute_meeting_prep and _execute_account_meeting_prep"
provides:
  - "execute_flywheel_ritual() engine with Stages 1-3 (sync, process, prep)"
  - "stage_results dict structure for Plan 04 HTML brief consumption"
affects: [66-03, 66-04]

tech-stack:
  added: []
  patterns: ["Stage-based orchestrator with per-item error isolation", "NULL-title guard for SkillRun.input_text.contains() queries"]

key-files:
  created:
    - backend/src/flywheel/engines/flywheel_ritual.py
  modified: []

key-decisions:
  - "Refactored stages into private async functions (_stage_1_sync, _stage_2_process, _stage_3_prep) for readability and future testability"
  - "Extracted _set_rls_context and _accumulate_usage helpers to reduce duplication"
  - "NULL title meetings treated as unprepped without querying skill_runs -- prevents contains('') matching all completed preps"

patterns-established:
  - "Stage isolation: each stage is a private async function, orchestrator calls sequentially"
  - "Per-item error isolation: one meeting failing does not block others"
  - "stage_results dict collects outputs across stages for downstream consumption (Plan 04 HTML brief)"

duration: 3min
completed: 2026-03-29
---

# Phase 66 Plan 02: Flywheel Ritual Engine Summary

**Flywheel ritual orchestrator engine with Stages 1-3: Granola sync, meeting processing (all unprocessed), and today's meeting prep with NULL-title guard**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T00:33:17Z
- **Completed:** 2026-03-29T00:36:45Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- Stage 1 syncs from Granola via shared sync_granola_meetings(), continues gracefully on failure
- Stage 2 processes ALL unprocessed meetings (no caps) via _execute_meeting_processor, with per-meeting error isolation
- Stage 3 preps today's unprepped external meetings (NULL meeting_type = external), dispatches to account-scoped or standard prep
- NULL title guard prevents false-positive prep detection from contains("") matching all SkillRun rows
- All SSE events stream to parent run via _append_event_atomic
- Token usage aggregated across all sub-engine calls

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Create flywheel_ritual.py engine with Stages 1-3** - `5bb7409` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/flywheel_ritual.py` - Flywheel ritual orchestrator engine (Stages 1-3: sync, process, prep)

## Decisions Made
- Refactored inline stages into private async functions for readability -- plan showed monolithic function, split into _stage_1_sync, _stage_2_process, _stage_3_prep
- Extracted _set_rls_context() helper to DRY RLS session config across stages
- Extracted _accumulate_usage() helper for token usage aggregation

## Deviations from Plan

None - plan executed exactly as written. The refactoring into helper functions is a structural improvement that preserves all specified behavior.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Stage 4 (task execution) ready for Plan 03 to add
- Stage 5 (HTML brief) ready for Plan 04 to add
- stage_results dict structure established for Plan 04 consumption

---
*Phase: 66-flywheel-ritual*
*Completed: 2026-03-29*
