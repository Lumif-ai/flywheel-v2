---
phase: 65-task-intelligence
plan: 02
subsystem: api
tags: [anthropic, haiku, meeting-processor, task-extraction, sse]

requires:
  - phase: 65-01
    provides: "Task ORM model, tasks migration 034, task signal counts"
provides:
  - "extract_tasks() async helper for Haiku-based commitment classification"
  - "write_task_rows() async helper for creating Task ORM rows with RLS context"
  - "Stage 7 extracting_tasks in 8-stage meeting processor pipeline"
affects: [65-03, 65-task-intelligence]

tech-stack:
  added: []
  patterns:
    - "Haiku task extraction with post-processing trust_level enforcement"
    - "Best-effort pipeline stage wrapped in try/except (non-fatal)"

key-files:
  created: []
  modified:
    - "backend/src/flywheel/engines/meeting_processor_web.py"
    - "backend/src/flywheel/services/skill_executor.py"

key-decisions:
  - "Email tasks forced to trust_level='confirm' via post-processing (not prompt-only)"
  - "Task extraction is best-effort -- failures logged but do not crash meeting pipeline"
  - "extract_tasks receives both transcript and Stage 4 extracted intelligence for full context"

patterns-established:
  - "Best-effort pipeline stage: wrap in try/except, log warning, continue to done"
  - "Post-processing enforcement: LLM output validated/corrected after parsing"

duration: 3min
completed: 2026-03-28
---

# Phase 65 Plan 02: Task Extraction Pipeline Stage Summary

**Haiku-based commitment classification as Stage 7 in meeting processor, creating Task rows with skill mapping and trust levels**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-28T12:34:31Z
- **Completed:** 2026-03-28T12:37:40Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- extract_tasks() calls Haiku with TASK_EXTRACTION_PROMPT to classify commitments into 5 directions (yours/theirs/mutual/signal/speculation)
- write_task_rows() creates Task ORM instances with full RLS context (both app.tenant_id and app.user_id)
- Stage 7 "extracting_tasks" inserted into pipeline between context writing and done stage
- Hard safety rule: email-related tasks always forced to trust_level='confirm' via post-processing
- Task extraction wrapped in try/except so failures never crash the meeting pipeline

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **All tasks** - `e7d2e7a` (feat: extract_tasks + write_task_rows helpers, Stage 7 pipeline insertion)

## Files Created/Modified
- `backend/src/flywheel/engines/meeting_processor_web.py` - Added TASK_EXTRACTION_PROMPT, extract_tasks(), write_task_rows()
- `backend/src/flywheel/services/skill_executor.py` - Added Stage 7 extracting_tasks, updated imports and docstring

## Decisions Made
- Email tasks forced to trust_level='confirm' via post-processing enforcement (not relying solely on LLM prompt instruction) -- defense-in-depth safety rule
- Task extraction is best-effort: wrapped in try/except so meeting processing continues even if Haiku call fails or JSON parsing fails
- extract_tasks receives both transcript AND Stage 4 extracted intelligence, giving Haiku full context without additional LLM cost for content retrieval
- Due date parsing uses datetime.fromisoformat with Z-to-+00:00 replacement -- handles both ISO and Zulu formats without additional dependencies

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Task extraction pipeline is complete and will create Task rows on every meeting processing run
- Ready for Plan 03: Tasks CRUD API at /api/v1/tasks

---
*Phase: 65-task-intelligence*
*Completed: 2026-03-28*
