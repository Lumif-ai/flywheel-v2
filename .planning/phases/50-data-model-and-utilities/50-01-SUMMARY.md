---
phase: 50-data-model-and-utilities
plan: 01
subsystem: database
tags: [alembic, postgres, rls, crm, accounts, contacts, outreach, migration]

# Dependency graph
requires:
  - phase: 026_docs_storage_nullable
    provides: Prior migration in chain (down_revision)
provides:
  - accounts table with tenant isolation, status tracking, fit scoring, intel JSONB
  - account_contacts table with account FK (CASCADE), dedup via email index
  - outreach_activities table with account + contact FKs, channel/direction/status tracking
  - account_id nullable FK column on context_entries for CRM linkage
  - 12 RLS policies (4 per new table) enforcing tenant isolation
  - Partial indexes for next_action_due, email, sent_at, account_id
affects: [51-seed-cli, 52-account-api, 53-crm-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CRM RLS loop: loop CRM_TABLES list and emit 4 RLS policy statements per table"
    - "Partial indexes via postgresql_where in op.create_index for sparse columns"
    - "Cascade deletes: account_contacts and outreach_activities cascade on account delete"
    - "SET NULL semantics: outreach contact_id and context_entries account_id use SET NULL"

key-files:
  created:
    - backend/alembic/versions/027_crm_tables.py
  modified: []

key-decisions:
  - "Used loop over CRM_TABLES list for RLS policy creation — consistent with migration 002 pattern, reduces copy-paste errors"
  - "UniqueConstraint on (tenant_id, normalized_name) in accounts table — enables dedup without separate lookup table"
  - "outreach_activities.contact_id is nullable with SET NULL — contacts can be deleted without losing outreach history"
  - "context_entries.account_id is nullable FK — allows retrospective linking without requiring account context on all entries"

patterns-established:
  - "RLS loop pattern: iterate table list, emit ENABLE/FORCE/GRANT/4-policies — use for any future batch of tenant-scoped tables"
  - "Partial index on nullable FK: WHERE col IS NOT NULL — avoids index bloat for sparse FKs"

# Metrics
duration: 2min
completed: 2026-03-26
---

# Phase 50 Plan 01: CRM Tables Migration Summary

**Three tenant-isolated CRM tables (accounts, account_contacts, outreach_activities) with 12 RLS policies, 7 indexes, and account_id FK on context_entries — full Alembic migration 027**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-26T15:22:05Z
- **Completed:** 2026-03-26T15:23:51Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Single migration file `027_crm_tables.py` creates all three CRM tables with correct column types, FK constraints, and server defaults
- 12 RLS policies applied via loop (4 per table: select/insert/update/delete) enforcing `app.tenant_id` tenant isolation
- 7 indexes including 3 partial indexes (next_action_due, email, account_id) for query efficiency
- Nullable `account_id` FK added to `context_entries` for linking context items to CRM accounts

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Create Alembic migration 027_crm_tables** - `7d0a239` (feat)

## Files Created/Modified

- `backend/alembic/versions/027_crm_tables.py` — Full CRM schema migration: accounts, account_contacts, outreach_activities tables with RLS; account_id column on context_entries

## Decisions Made

- Used a `CRM_TABLES` list + loop for RLS policy creation to avoid copy-paste errors and match the style established in migration 002
- `UniqueConstraint("tenant_id", "normalized_name")` on accounts for deduplication by normalized company name within a tenant
- `ondelete="SET NULL"` for `outreach_activities.contact_id` and `context_entries.account_id` — preserves history when child records are deleted
- `ondelete="CASCADE"` for `account_contacts.account_id` and `outreach_activities.account_id` — deleting an account cleans up all associated contacts and outreach records

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Verification check for "4 RLS policies per table" via string count was a false negative (policy name appears once in f-string loop, not 3 times in source text) — loop logic was correct as confirmed by code review.

## User Setup Required

None — no external service configuration required. Migration runs automatically via `alembic upgrade head`.

## Next Phase Readiness

- Migration 027 is ready to apply to the database via `alembic upgrade head`
- Phase 51 (Seed CLI) can now create accounts, contacts, and outreach records
- Phase 52 (Account API) can build CRUD endpoints against these tables
- Phase 53 (CRM UI) can build the frontend against the API

---
*Phase: 50-data-model-and-utilities*
*Completed: 2026-03-26*
