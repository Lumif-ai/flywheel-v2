---
phase: 75-context-extraction-pipeline
plan: 01
subsystem: database
tags: [alembic, postgresql, rls, sqlalchemy, context-extraction, confidence-routing]

requires:
  - phase: 74-email-context-extractor
    provides: email_context_extractor.py with _write_extracted_context and extract_email_context
provides:
  - Alembic migration 037 with context_extracted_at column and email_context_reviews table
  - EmailContextReview ORM model
  - Confidence-based routing in _write_extracted_context (skip_low_confidence parameter)
affects: [75-02, context-extraction-pipeline, email-review-ui]

tech-stack:
  added: []
  patterns: [confidence-routing-pattern, low-confidence-review-queue]

key-files:
  created:
    - backend/alembic/versions/037_context_extraction_pipeline.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/engines/email_context_extractor.py

key-decisions:
  - "Low-confidence items returned as list in results dict rather than written to separate table directly -- keeps writer stateless, caller decides storage"
  - "ON DELETE CASCADE on email_id FK prevents orphaned reviews when emails are deleted"

patterns-established:
  - "Confidence routing: skip_low_confidence param on writer functions to separate low-confidence items for human review"

duration: 3min
completed: 2026-03-30
---

# Phase 75 Plan 01: Context Extraction Pipeline DB Foundation Summary

**Alembic migration for email_context_reviews table with RLS, EmailContextReview ORM model, and confidence-based routing in email context extractor**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T04:42:06Z
- **Completed:** 2026-03-30T04:45:09Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Migration 037 adds context_extracted_at nullable timestamp on emails table with partial index for efficient "not yet extracted" queries
- email_context_reviews table with full RLS (4 policies matching email_scores pattern) for human review of low-confidence extractions
- Confidence routing in _write_extracted_context: when skip_low_confidence=True, low-confidence items are collected separately instead of written to context store

## Task Commits

All tasks committed as single plan-level commit (per-plan strategy):

1. **Task 1: Alembic migration** - `0835097` (feat)
2. **Task 2: ORM models** - `0835097` (feat)
3. **Task 3: Confidence routing** - `0835097` (feat)

## Files Created/Modified
- `backend/alembic/versions/037_context_extraction_pipeline.py` - Migration adding context_extracted_at column and email_context_reviews table with RLS
- `backend/src/flywheel/db/models.py` - EmailContextReview model + context_extracted_at on Email
- `backend/src/flywheel/engines/email_context_extractor.py` - skip_low_confidence parameter on _write_extracted_context and extract_email_context

## Decisions Made
- Low-confidence items returned in results dict as list rather than written to review table directly -- keeps the writer function stateless; the caller (pipeline orchestrator in 75-02) decides how to store them
- ON DELETE CASCADE on email_id FK to prevent orphaned review records

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Database foundation ready for 75-02 pipeline orchestrator
- email_context_reviews table ready for review queue API
- Confidence routing ready for integration with pipeline batch processor

---
*Phase: 75-context-extraction-pipeline*
*Completed: 2026-03-30*
