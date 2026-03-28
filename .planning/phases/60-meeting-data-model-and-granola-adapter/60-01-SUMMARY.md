---
phase: 60-meeting-data-model-and-granola-adapter
plan: 01
subsystem: database
tags: [alembic, postgresql, rls, sqlalchemy, meetings, crm]

# Dependency graph
requires:
  - phase: 59-team-privacy-foundation
    provides: user-level RLS pattern using current_setting('app.user_id', true) — applied to meetings table
  - phase: 54-data-model-foundation
    provides: accounts table (FK target for account_id), alembic revision ID length constraint
  - phase: 55-relationships-and-signals-apis
    provides: skill_runs table (FK target for skill_run_id)
provides:
  - meetings table with 20 columns (UUID PK, tenant/user ownership, provider+external_id, meeting metadata, JSONB attendees/summary, FK to accounts/skill_runs, processing lifecycle)
  - Split-visibility RLS: tenant_read (SELECT) and owner_write (ALL) — two-policy pattern for shared-read + private-write
  - Meeting ORM class in flywheel.db.models with all 20 Mapped[] fields and 4 index definitions
affects: [60-02-granola-adapter, 60-03-meetings-api, all future meeting ingestion plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Split-visibility RLS: separate SELECT policy (tenant-scoped) + ALL policy (user-scoped) for tables where metadata is shared but writes are private"
    - "Partial dedup index: UNIQUE ON (tenant_id, provider, external_id) WHERE external_id IS NOT NULL — allows NULL external_id rows while preventing duplicate synced records"

key-files:
  created:
    - backend/alembic/versions/032_create_meetings_table.py
  modified:
    - backend/src/flywheel/db/models.py

key-decisions:
  - "Split-visibility RLS uses two policies (tenant_read FOR SELECT + owner_write FOR ALL) not four per-operation policies — cleaner and matches MDE-01 design intent"
  - "current_setting('app.tenant_id', true) with missing_ok=true — consistent with Pattern established in 031_user_level_rls, avoids errors when session variable not set"
  - "account_id FK uses ON DELETE SET NULL — meeting remains even if account is deleted; skill_run_id FK has no cascade (orphan tolerated)"
  - "processing_status server_default 'pending' with NOT NULL constraint — every ingested meeting enters processing queue automatically"

patterns-established:
  - "Split-visibility table pattern: tenant_read FOR SELECT + owner_write FOR ALL — use for any future table where team shares visibility but users own their data"

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 60 Plan 01: Meetings Table Foundation Summary

**Alembic migration creating meetings table with split-visibility RLS (tenant_read SELECT + owner_write ALL) and SQLAlchemy Meeting ORM model with 20 columns and 4 partial indexes**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-28T00:45:02Z
- **Completed:** 2026-03-28T00:50:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Meetings table created via Alembic migration (032) with unbroken revision chain (031 -> 032), all 20 columns from MDE-01 spec, 4 partial indexes including unique dedup index
- Split-visibility RLS established: `meetings_tenant_read` FOR SELECT (tenant-wide visibility) and `meetings_owner_write` FOR ALL with USING + WITH CHECK (user-scoped writes)
- Meeting ORM class added to models.py CRM TABLES section — importable, all 20 Mapped[] fields, account and skill_run relationships, module docstring updated to 4 tables

## Task Commits

Plan committed atomically (per-plan strategy):

1. **Task 1: Alembic migration + Task 2: Meeting ORM model** - `7243b71` (feat)

## Files Created/Modified
- `backend/alembic/versions/032_create_meetings_table.py` - Migration: meetings table, 4 partial indexes, split-visibility RLS, GRANT to app_user
- `backend/src/flywheel/db/models.py` - Meeting class added after OutreachActivity, module docstring updated to CRM tables (4 tables)

## Decisions Made
- Split-visibility uses exactly 2 policies (not 4 per-operation) — FOR SELECT covers reads tenant-wide; FOR ALL covers writes (PostgreSQL applies USING for SELECT too in FOR ALL, so owner_write's ALL doesn't conflict with tenant_read SELECT because both USING clauses are satisfied for the owning user's SELECT queries)
- `missing_ok=true` in `current_setting('app.tenant_id', true)` — consistent with 031_user_level_rls pattern, avoids PostgreSQL errors on unauthenticated connections
- Dedup index partial predicate `external_id IS NOT NULL` allows multiple manually-uploaded meetings (no external_id) without colliding

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Migration will be applied on next `alembic upgrade head` deploy.

## Next Phase Readiness
- Meetings table and ORM model are in place — Plan 02 (Granola adapter) can import Meeting and write rows
- Plan 03 (meetings API endpoints) can import Meeting for query/mutation operations
- RLS is live: app must set both `app.tenant_id` and `app.user_id` session variables before DML on meetings table

---
*Phase: 60-meeting-data-model-and-granola-adapter*
*Completed: 2026-03-28*
