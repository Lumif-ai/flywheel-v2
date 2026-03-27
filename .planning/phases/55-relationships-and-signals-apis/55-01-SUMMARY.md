---
phase: 55-relationships-and-signals-apis
plan: 01
subsystem: api

tags: [fastapi, sqlalchemy, alembic, postgres, crm, relationships]

requires:
  - phase: 54-data-model-foundation
    provides: "relationship_type, entity_level, ai_summary columns on accounts; relationship_status and pipeline_stage columns; GIN index on relationship_type"

provides:
  - "graduated_at nullable timestamptz column on accounts (migration 030)"
  - "Partial index idx_account_graduated_at for efficient partition queries"
  - "Relationships router with 4 endpoints: GET list, GET detail, PATCH type, POST graduate"
  - "Partition predicate (graduated_at IS NOT NULL) enforced on all read/write endpoints"
  - "_graduate_account() helper now sets graduated_at = now alongside status = engaged"

affects: [55-02, 55-03, 56-frontend-pipeline-relationships]

tech-stack:
  added: []
  patterns:
    - "Partition predicate pattern: graduated_at.isnot(None) always present in relationships queries"
    - "Type validation via Pydantic field_validator on list[str] fields"
    - "Correlated subqueries for signal_count and primary_contact_name to avoid N+1"
    - "AI summary returned from column as-is (NULL = NULL) — never triggers LLM on read"

key-files:
  created:
    - backend/alembic/versions/030_graduated_at.py
    - backend/src/flywheel/api/relationships.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/api/outreach.py
    - backend/src/flywheel/main.py

key-decisions:
  - "graduated_at partition predicate enforced on every relationships query (list, detail, type update) — POST /graduate is the only endpoint that intentionally skips it to target un-graduated accounts"
  - "_graduate_account() in outreach.py sets graduated_at = now so both auto-graduation (reply trigger) and manual graduation via the new POST /graduate endpoint always set the timestamp"
  - "Pydantic field_validator on UpdateTypeRequest.types and GraduateRequest.types rejects empty arrays and unknown type values at the serialization layer (before DB touch)"
  - "GET /relationships/{id} returns ai_summary directly from column — NULL is valid, LLM is never called"

patterns-established:
  - "Partition predicate pattern: include Account.graduated_at.isnot(None) in WHERE clause for all relationships queries"
  - "Graduate endpoint pattern: fetch without partition predicate, check graduated_at is None, return 409 if already graduated"
  - "Signal count via correlated subquery on context_entries WHERE deleted_at IS NULL"

duration: 3min
completed: 2026-03-27
---

# Phase 55 Plan 01: Relationships Router Summary

**Graduated-account partition predicate enforced on FastAPI relationships router — 4 endpoints (list/detail/type/graduate) with migration 030 adding graduated_at column and index**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-27T06:01:59Z
- **Completed:** 2026-03-27T06:05:06Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Migration 030 adds `graduated_at TIMESTAMPTZ NULL` column to accounts with partial index `idx_account_graduated_at WHERE graduated_at IS NOT NULL`
- `Account` ORM model updated with `graduated_at` mapped column and matching `__table_args__` index
- `_graduate_account()` in outreach.py now sets `account.graduated_at = now` so auto-graduation (reply trigger) and manual graduation both set the timestamp
- Relationships router created with 4 endpoints: GET `/relationships/` (list with partition predicate + type filter + correlated subqueries), GET `/relationships/{id}` (detail with contacts/timeline/cached ai_summary), PATCH `/relationships/{id}/type` (type validation), POST `/relationships/{id}/graduate` (graduate un-graduated accounts with 409 guard)
- Router registered in main.py at `/api/v1`

## Task Commits

Per-plan batch commit (commit_strategy=per-plan):

1. **Tasks 1+2 batch:** `2959dec` feat(55-01): add graduated_at migration and relationships router

## Files Created/Modified
- `backend/alembic/versions/030_graduated_at.py` — Migration 030: adds graduated_at column + partial index
- `backend/src/flywheel/db/models.py` — Account ORM: graduated_at column + idx_account_graduated_at in __table_args__
- `backend/src/flywheel/api/outreach.py` — _graduate_account(): sets account.graduated_at = now
- `backend/src/flywheel/api/relationships.py` — New: relationships router with RAPI-01 through RAPI-04
- `backend/src/flywheel/main.py` — Import + register relationships_router at /api/v1

## Decisions Made
- Used `field_validator` (Pydantic v2) rather than `validator` to validate relationship types — gives clear error messages at the serialization boundary
- `POST /relationships/{id}/graduate` returns 409 (Conflict) rather than 400 (Bad Request) for already-graduated accounts — semantically more accurate
- Correlated subqueries used for signal_count and primary_contact_name to avoid N+1 without requiring ORM eager loading on the list endpoint

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- Docker was not running when migration was first attempted — started Docker, postgres container spun up, migration applied cleanly on second attempt.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Migration 030 is applied — graduated_at is live in the database
- All 4 relationships endpoints available at `/api/v1/relationships/`
- Partition predicate established as a code pattern — Phase 55-02 (Signals API) can follow the same convention
- Phase 55-03 (Pipeline API) should reference the `Account.graduated_at.is_(None)` inverse predicate for prospect-only queries

---
*Phase: 55-relationships-and-signals-apis*
*Completed: 2026-03-27*
