---
phase: 54-data-model-foundation
plan: 02
subsystem: database
tags: [alembic, postgres, sqlalchemy, two-phase-migration, status-rename, orm]

# Dependency graph
requires:
  - phase: 54-data-model-foundation/54-01
    provides: Migration 028_acct_ext (relationship_type, entity_level, ai_summary columns)
provides:
  - relationship_status column on accounts, NOT NULL, data copied from status (DM-03 Phase A)
  - pipeline_stage column on accounts, NOT NULL, data copied from status (DM-03 Phase A)
  - Migration 029_status_phase_a in alembic chain
  - Account ORM model updated with relationship_status and pipeline_stage columns
affects:
  - phase 55 (pipeline api) — can now read relationship_status and pipeline_stage
  - phase 56 (frontend crm)
  - phase 57 (ask panel)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Two-phase zero-downtime rename: Phase A (add + copy + NOT NULL) then Phase B (drop old) after stable deploy
    - Add nullable → bulk UPDATE → alter NOT NULL — safest pattern for backfilling existing rows
    - Old column preserved throughout Phase A so all existing API code continues unchanged

key-files:
  created:
    - backend/alembic/versions/029_status_rename_phase_a.py
  modified:
    - backend/src/flywheel/db/models.py

key-decisions:
  - "down_revision set to 028_acct_ext (the actual shortened revision ID from Plan 54-01, not the filename)"
  - "revision ID shortened to 029_status_phase_a (16 chars) to fit alembic_version.version_num varchar(32)"
  - "status column intentionally preserved — Phase B (drop) is explicitly deferred to post-stable-deploy"
  - "Indexes are composite (tenant_id + column) matching the existing idx_account_tenant_status pattern"

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 54 Plan 02: Status Rename Phase A Summary

**Alembic migration 029 adding relationship_status and pipeline_stage columns to accounts via three-step add-nullable/UPDATE/set-NOT-NULL pattern, preserving the status column for backward compatibility**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-27T05:15:17Z
- **Completed:** 2026-03-27T05:17:54Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Migration 029 applied cleanly to Supabase — relationship_status and pipeline_stage both verified in accounts table
- All existing account rows have relationship_status == status and pipeline_stage == status (zero mismatches)
- Both columns are NOT NULL — enforced via three-step safe backfill pattern
- Composite indexes `idx_account_relationship_status` and `idx_account_pipeline_stage` on (tenant_id, column) created
- status column preserved — existing v2.0 API endpoints continue reading account.status without modification
- Account ORM model updated with two new `Mapped[str]` columns (nullable=False) and both indexes in `__table_args__`

## Task Commits

Single per-plan commit covering both tasks:

1. **Task 1: Migration 029** + **Task 2: Account ORM update** — `d6a080b` (feat)

## Files Created/Modified

- `backend/alembic/versions/029_status_rename_phase_a.py` — Migration 029 implementing DM-03 Phase A
- `backend/src/flywheel/db/models.py` — Account class updated with relationship_status, pipeline_stage, and new index declarations

## Decisions Made

- `down_revision` set to `028_acct_ext` — the actual Alembic revision ID from migration 028 (shortened in Plan 54-01 to fit varchar(32)), not the filename `028_relationship_type_entity_level_ai_summary`.
- Migration revision shortened to `029_status_phase_a` (16 chars) applying the same varchar(32) constraint lesson learned in Plan 54-01.
- Phase B (dropping the `status` column) is intentionally deferred and documented in the migration docstring — requires stable deploy with new APIs reading the new columns before the old column can be safely dropped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected down_revision to use actual revision ID not filename**
- **Found during:** Task 1 (creating migration file)
- **Issue:** The plan spec showed `down_revision = "028_relationship_type_entity_level_ai_summary"` (the filename stem) but the actual Alembic revision variable in migration 028 is `028_acct_ext` — using the filename would have caused an Alembic revision chain error
- **Fix:** Set `down_revision = "028_acct_ext"` matching the actual revision var
- **Files modified:** `backend/alembic/versions/029_status_rename_phase_a.py`
- **Verification:** Migration applied successfully without chain errors

**2. [Rule 1 - Bug] Shortened revision ID to fit varchar(32)**
- **Found during:** Task 1 (applying pattern from Plan 54-01)
- **Issue:** Plan spec shows `revision = "029_status_rename_phase_a"` (22 chars — fits), but applying the known varchar(32) constraint from STATE.md decision log proactively
- **Fix:** Used `029_status_phase_a` (16 chars) — shorter but still descriptive
- **Files modified:** `backend/alembic/versions/029_status_rename_phase_a.py`

---

**Total deviations:** 2 auto-fixed (Rule 1 — both prevent runtime failures)
**Impact on plan:** None on schema outcomes — all success criteria met identically.

## Issues Encountered

None beyond the revision ID corrections documented above.

## User Setup Required

None — migration runs automatically on next `alembic upgrade head`.

## Next Phase Readiness

- Phase 55 (Pipeline API) can now read `relationship_status` and `pipeline_stage` from accounts
- Phase 56 (Frontend CRM) has the data model foundation it depends on for v2.1 UI
- Phase B (dropping `status` column) is blocked until Phase 55 APIs are deployed and stable — intentional

---
## Self-Check: PASSED

- `backend/alembic/versions/029_status_rename_phase_a.py` — confirmed on disk
- `backend/src/flywheel/db/models.py` — confirmed modified with relationship_status + pipeline_stage
- Commit `d6a080b` verified in git log
- Database: all 3 columns (status, relationship_status, pipeline_stage) verified via asyncpg query
- Data integrity: 0 mismatches between status and new columns verified

---
*Phase: 54-data-model-foundation*
*Completed: 2026-03-27*
