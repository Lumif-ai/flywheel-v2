---
phase: 129-schema-new-tables
plan: "02"
subsystem: database

tags: [postgres, rls, supabase, pgbouncer, tenant-isolation, broker]

requires:
  - phase: 129-01
    provides: broker_data_model_migration.py DDL script, 6 tables scripted and ready

provides:
  - All 6 broker data model v2 tables live in Supabase (broker_clients, broker_client_contacts, carrier_contacts, broker_recommendations, solicitation_drafts, broker_project_emails)
  - 42 RLS policy statements applied (7 per table × 6 tables: ENABLE, FORCE, GRANT, 4 policies)
  - alembic_version stamped to 059_broker_data_model_tables
  - run_rls() function in broker_data_model_migration.py for idempotent re-application

affects: [130-schema-modifications, 131-backend-atomic-release, 132-frontend-clients]

tech-stack:
  added: []
  patterns:
    - "RLS separation pattern: --rls flag runs RLS loop after DDL succeeds, avoids mixed-concern scripts"
    - "Alembic stamp via SQLAlchemy UPDATE: alembic env.py cannot reach Supabase direct port; UPDATE alembic_version via get_session_factory() instead"

key-files:
  created: []
  modified:
    - backend/scripts/broker_data_model_migration.py

key-decisions:
  - "Alembic stamp applied via direct SQLAlchemy UPDATE (not CLI) because alembic env.py targets port 5434 which is not available; get_session_factory() uses the correct pooler URL"
  - "RLS runner added as --rls flag on existing migration script rather than separate file — keeps all migration logic in one place"

patterns-established:
  - "Broker RLS pattern: ENABLE + FORCE + GRANT + 4 policies per table using current_setting('app.tenant_id', true)::uuid"
  - "Alembic stamp workaround: UPDATE alembic_version SET version_num = 'XXX' via session.execute() + session.commit()"

duration: 12min
completed: 2026-04-15
---

# Phase 129 Plan 02: Schema New Tables (RLS + Migration Execution) Summary

**All 6 broker data model v2 tables live in Supabase with 42 RLS policy statements enforcing tenant isolation via current_setting('app.tenant_id', true)::uuid; alembic stamped to 059_broker_data_model_tables**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-15T00:18:00Z
- **Completed:** 2026-04-15T00:30:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `_rls_statements()`, `run_rls()`, `NEW_TABLES` list, and `--rls` CLI flag to `broker_data_model_migration.py` — keeping all migration logic in one script
- Ran DDL migration: 17 statements succeeded (6 CREATE TABLE + 11 CREATE INDEX), all committed individually via PgBouncer workaround
- Applied 42 RLS policy statements across 6 tables: ENABLE RLS, FORCE RLS, GRANT to app_user, and 4 tenant-isolation policies (select/insert/update/delete) per table
- Stamped alembic to `059_broker_data_model_tables` via direct SQLAlchemy UPDATE (alembic CLI could not connect to Supabase direct port)

## Task Commits

Both tasks committed as one per-plan commit:

1. **Task 1: Add RLS runner to broker_data_model_migration.py** - `b68e596` (feat)
2. **Task 2: Execute migration and stamp alembic** - `b68e596` (feat)

**Plan commit:** `b68e596` feat(129-02): add RLS runner to broker data model migration and apply to live DB

## Files Created/Modified

- `backend/scripts/broker_data_model_migration.py` — Added `_rls_statements()` generator, `NEW_TABLES` list, `run_rls()` async function, and updated `__main__` block with `--rls` flag

## Decisions Made

- **Alembic stamp via SQLAlchemy UPDATE** — `alembic stamp` CLI failed because `alembic/env.py` tries to connect to port 5434 (direct Postgres) which is not accessible; applied stamp by executing `UPDATE alembic_version SET version_num = '059_broker_data_model_tables'` via `get_session_factory()` which uses the correct PgBouncer pooler URL
- **Single script, --rls flag** — Added RLS runner as `--rls` CLI argument to existing migration script rather than creating a separate file, keeping all migration logic for these 6 tables in one place

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Alembic stamp CLI failed; applied via SQLAlchemy instead**
- **Found during:** Task 2 (Execute migration and stamp alembic)
- **Issue:** `uv run alembic stamp 059_broker_data_model_tables` failed with `OSError: Connect call failed ('127.0.0.1', 5434)` — alembic env.py uses `DATABASE_URL` which resolves to a direct port unavailable locally
- **Fix:** Applied stamp directly via `UPDATE alembic_version SET version_num = '059_broker_data_model_tables'` using `get_session_factory()` session — same approach used throughout this project for DDL
- **Files modified:** None (runtime operation only)
- **Verification:** Confirmed with `SELECT version_num FROM alembic_version` — returns `059_broker_data_model_tables`
- **Committed in:** `b68e596` (plan commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Stamp achieved with equivalent result; alembic_version table shows correct revision. No scope changes.

## Issues Encountered

- `alembic stamp` CLI unavailable via `uv run alembic` due to env.py attempting connection to local port 5434; resolved via direct SQLAlchemy UPDATE on `alembic_version` table — consistent with existing project workaround pattern for Supabase PgBouncer constraints.

## User Setup Required

None — migration has been fully applied to the live database.

## Next Phase Readiness

- All 6 tables live in Supabase with full tenant isolation enforced
- Phase 130 (Schema Modifications) can proceed — `carrier_configs` email_address column changes, existing table alterations
- Phase 131 (Backend Atomic Release) can proceed — ORM models can now reference all 6 new tables
- Phase 132 (Frontend Clients) can proceed — broker_clients and broker_client_contacts are queryable

---
*Phase: 129-schema-new-tables*
*Completed: 2026-04-15*
