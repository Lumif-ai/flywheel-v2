---
phase: 59-team-privacy-foundation
plan: 01
subsystem: database
tags: [postgres, rls, row-level-security, alembic, privacy, multi-tenant]

# Dependency graph
requires:
  - phase: 020_email_models
    provides: email, email_scores, email_drafts, email_voice_profiles tables with tenant-only RLS
  - phase: 002_enable_rls_policies
    provides: work_items, skill_runs, integrations tables with tenant-only RLS
  - phase: 030_grad_at
    provides: current migration head (030_grad_at)
provides:
  - Alembic migration 031_user_level_rls.py replacing tenant-only RLS with user-level RLS on 7 tables
  - user_isolation policies on emails, email_scores, email_drafts, email_voice_profiles, integrations, work_items, skill_runs
affects: [59-02-api-ownership-guards, phase-60, phase-61, phase-62, phase-63]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three RLS policy upgrade patterns: direct user_id (Pattern 1), nullable user_id (Pattern 2), subquery via FK (Pattern 3)"
    - "integrations table uses policy name 'integrations_tenant_isolation' (not generic 'tenant_isolation') — must match in any future policy work"

key-files:
  created:
    - backend/alembic/versions/031_user_level_rls.py
  modified: []

key-decisions:
  - "integrations table policy name is 'integrations_tenant_isolation' not 'tenant_isolation' — SPEC referenced wrong name; correct name used in migration"
  - "user_id IS NULL rows in work_items/skill_runs remain visible tenant-wide — system-generated items treated as shared"
  - "email_scores and email_drafts use subquery ownership (email_id IN SELECT FROM emails WHERE user_id=...) — avoids adding redundant user_id columns to child tables"

patterns-established:
  - "Pattern 1 (direct user_id): DROP 4 per-operation tenant_isolation_* policies, CREATE single user_isolation FOR ALL with tenant_id AND user_id"
  - "Pattern 2 (nullable user_id): DROP single tenant_isolation, CREATE user_isolation FOR ALL with tenant_id AND (user_id IS NULL OR user_id = current_setting(...))"
  - "Pattern 3 (FK subquery): DROP 4 per-operation tenant_isolation_* policies, CREATE user_isolation using email_id IN (SELECT id FROM emails WHERE user_id = ...)"
  - "downgrade() must restore exact original policy names per table, not generic names"

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 59 Plan 01: User-Level RLS Migration Summary

**Alembic migration replacing tenant-only RLS with user_isolation policies on 7 tables using 3 patterns: direct user_id, nullable user_id, and FK subquery ownership**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-27T17:16:58Z
- **Completed:** 2026-03-27T17:22:00Z
- **Tasks:** 1/1
- **Files modified:** 1

## Accomplishments

- Created Alembic migration `031_user_level_rls.py` with correct revision chain (`031_user_level_rls -> 030_grad_at`)
- 7 `user_isolation` CREATE POLICY statements covering all 7 tables
- Correct DROP statements per table: 4 per-operation drops for email-family tables, 1 single-policy drop for integrations/work_items/skill_runs
- Complete `downgrade()` restoring exact original policy names per table
- Valid Python syntax confirmed

## Task Commits

1. **Task 1: Create user-level RLS migration for all 7 tables** - `298c509` (feat)

## Files Created/Modified

- `backend/alembic/versions/031_user_level_rls.py` - Alembic migration with 7 user_isolation policies (upgrade) and full policy restoration (downgrade)

## Decisions Made

- **integrations policy name correction:** The SPEC said `DROP POLICY IF EXISTS tenant_isolation ON integrations` but the actual policy name in migration 005 is `integrations_tenant_isolation`. Used the correct name to ensure the DROP actually removes the old policy. Using the wrong name would silently no-op due to `IF EXISTS` and leave both the old tenant-only policy and the new user-level policy active simultaneously.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected integrations policy name in DROP statement**
- **Found during:** Task 1 (reading migration 005_add_integrations_table.py)
- **Issue:** SPEC specified `DROP POLICY IF EXISTS tenant_isolation ON integrations` but the actual policy name created in migration 005 is `integrations_tenant_isolation` — a different name. Using the SPEC's name would silently no-op and leave the tenant-only policy active.
- **Fix:** Used `DROP POLICY IF EXISTS integrations_tenant_isolation ON integrations` matching the actual policy name. Downgrade also restores `integrations_tenant_isolation` name correctly.
- **Files modified:** `backend/alembic/versions/031_user_level_rls.py`
- **Verification:** grep confirms `integrations_tenant_isolation` used for both DROP and CREATE in downgrade
- **Committed in:** 298c509

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug/incorrect policy name from spec)
**Impact on plan:** Essential correctness fix. Without it, the integrations table would retain its old tenant-only policy, silently failing the user isolation requirement for that table.

## Issues Encountered

None beyond the integrations policy name mismatch documented above.

## User Setup Required

None — migration-only change. No external service configuration required. Run `alembic upgrade head` to apply.

## Next Phase Readiness

- Migration is ready to apply; user-level DB enforcement is in place for all 7 tables
- Plan 59-02 (API ownership guards) can now add defense-in-depth application-layer filters on top of this DB enforcement
- All 7 tables will enforce `app.user_id` session variable — the existing `get_tenant_session()` helper already sets this on every request

---
*Phase: 59-team-privacy-foundation*
*Completed: 2026-03-28*
