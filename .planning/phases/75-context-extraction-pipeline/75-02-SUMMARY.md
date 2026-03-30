---
phase: 75-context-extraction-pipeline
plan: 02
subsystem: api
tags: [gmail-sync, context-extraction, review-queue, fastapi, sqlalchemy, confidence-routing]

requires:
  - phase: 75-context-extraction-pipeline
    provides: EmailContextReview model, context_extracted_at column, confidence routing in extractor
  - phase: 74-email-context-extractor
    provides: extract_email_context with skip_low_confidence, shared context_store_writer functions
provides:
  - Context extraction step wired into both gmail sync paths (full + incremental)
  - Daily extraction cap enforcement (200/day per tenant)
  - Three review API endpoints (list, approve, reject) on /email router
affects: [email-review-ui, context-extraction-pipeline]

tech-stack:
  added: []
  patterns: [post-draft-extraction-pattern, daily-cap-with-per-cycle-limit, review-queue-approval-flow]

key-files:
  created: []
  modified:
    - backend/src/flywheel/services/gmail_sync.py
    - backend/src/flywheel/api/email.py

key-decisions:
  - "Per-cycle extraction limit set to 10 (prevents timeout from too many LLM calls in a single sync)"
  - "Approve endpoint upgrades confidence to medium and uses parent email received_at as entry_date for correct dedup"

patterns-established:
  - "Post-draft extraction: extraction runs after scoring+drafting in both sync paths, non-fatal failure"
  - "Review approval flow: approve writes via shared context_store_writer, reject sets status only"

duration: 3min
completed: 2026-03-30
---

# Phase 75 Plan 02: Context Extraction Pipeline Wiring Summary

**Gmail sync loop wired with context extraction (200/day cap, 10/cycle limit), confidence routing to review queue, and three review API endpoints (list/approve/reject)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T04:47:08Z
- **Completed:** 2026-03-30T04:50:25Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Context extraction runs automatically after scoring+drafting in both _full_sync and incremental sync_gmail paths
- Daily 200/day per-tenant cap with 10/cycle batch limit prevents runaway costs; low-confidence items routed to email_context_reviews for human approval
- Three review endpoints: GET /context-reviews (filtered by status, newest first), POST approve (writes items to context store with entry_date from parent email), POST reject (marks rejected without writing)
- EmailContextReview cleanup added to both reconciliation paths (full sync stale removal, incremental label removal)

## Task Commits

All tasks committed as single plan-level commit (per-plan strategy):

1. **Task 1: Wire extraction into gmail_sync.py** - `a3445f4` (feat)
2. **Task 2: Add review API endpoints** - `a3445f4` (feat)

## Files Created/Modified
- `backend/src/flywheel/services/gmail_sync.py` - Added _check_daily_extraction_cap, _extract_email_contexts, wired into both sync paths, added EmailContextReview cleanup in reconciliation
- `backend/src/flywheel/api/email.py` - Added ContextReviewOut model, three review endpoints (list, approve, reject), context_store_writer imports

## Decisions Made
- Per-cycle extraction limit set to 10 to prevent timeout from too many LLM calls in a single sync cycle
- Approve endpoint upgrades confidence to "medium" (human validated) and uses parent email's received_at.date() as entry_date for correct dedup in context store

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Context extraction pipeline is fully wired: sync -> score -> draft -> extract -> review
- Review UI can now be built against the three endpoints
- Phase 75 complete pending verification

---
*Phase: 75-context-extraction-pipeline*
*Completed: 2026-03-30*
