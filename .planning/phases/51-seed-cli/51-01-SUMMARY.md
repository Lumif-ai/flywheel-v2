---
phase: 51-seed-cli
plan: 01
subsystem: database
tags: [openpyxl, csv, sqlalchemy, asyncpg, crm, seed, idempotent, upsert]

requires:
  - phase: 50-data-model-and-utilities
    provides: Account, AccountContact, OutreachActivity ORM models + normalize_company_name utility + CRM migration 027

provides:
  - seed_crm CLI: python -m flywheel.seed_crm populates 3 CRM tables from GTM stack files
  - 206 real accounts, 235 contacts, 81 outreach activities seeded in Supabase
  - Idempotent upsert pattern for CRM seed operations

affects:
  - 52-accounts-api (reads from tables seeded by this plan)
  - Any phase that depends on CRM tables having data

tech-stack:
  added: [openpyxl==3.1.5 for xlsx parsing]
  patterns:
    - "Per-plan commit: all tasks committed together after verification"
    - "Idempotent upsert: pg INSERT ON CONFLICT for accounts, SELECT-then-INSERT for contacts/activities"
    - "Multi-source merge: AccountData accumulates intel across xlsx+csv+json sources, higher fit_score wins"
    - "GTM pipeline: xlsx(Company Summary + All Leads Scored) + outreach-tracker.csv + scored CSVs via pipeline-runs.json"

key-files:
  created:
    - backend/src/flywheel/seed_crm.py
    - backend/alembic/versions/025_uploaded_files_metadata.py
  modified:
    - backend/pyproject.toml (added openpyxl dependency)
    - backend/uv.lock

key-decisions:
  - "openpyxl added as project dependency (was pre-installed system-wide but not in pyproject.toml)"
  - "Migration 025 fixed with IF NOT EXISTS guard — column already existed in DB but revision hadn't been stamped"
  - "SELECT-then-INSERT for contacts/activities (no unique constraint exists) instead of ON CONFLICT"
  - "In-memory deduplication before DB hits reduces round trips when same company appears across multiple sources"
  - "Activities skipped if sent_at is NULL — no date = no trackable event"

patterns-established:
  - "GTM seed pattern: parse-all-then-upsert (not streaming) for predictable memory usage at ~500 contact scale"
  - "AccountData dataclass accumulates from N sources; merge_account() applies priority rules (longer name wins, higher score wins, first domain wins)"

duration: 7min
completed: 2026-03-26
---

# Phase 51 Plan 01: Seed CLI Summary

**CLI tool seeding 206 real accounts, 235 contacts, and 81 outreach activities from xlsx/csv/json GTM stack files — idempotent, normalized, multi-source merged**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-26T16:01:50Z
- **Completed:** 2026-03-26T16:09:31Z
- **Tasks:** 2
- **Files created:** 2 (seed_crm.py, 025 migration fix)
- **Files modified:** 2 (pyproject.toml, uv.lock)

## Accomplishments

- `backend/src/flywheel/seed_crm.py` (450+ lines): CLI with 4 file parsers, idempotent upserts, dry-run mode, --force mode
- 206 accounts seeded with normalized_name dedup — zero duplicates confirmed by SQL check
- Idempotency confirmed: second run produces 0 new inserts (235 contacts skipped, 92 activities skipped)
- All three CRM tables populated with real GTM data from day one

## Task Commits

Both tasks covered in a single per-plan commit:

1. **Task 1: seed_crm.py with file parsing, normalization, and idempotent upserts** — `b196626` (feat)
2. **Task 2: Verify idempotent seeding against live database** — `b196626` (included above)

## Files Created/Modified

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/seed_crm.py` — CLI tool: 4 file parsers, idempotent upserts, dry-run/force/verbose flags
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/025_uploaded_files_metadata.py` — Fixed: added IF NOT EXISTS guard for metadata column
- `/Users/sharan/Projects/flywheel-v2/backend/pyproject.toml` — Added openpyxl dependency
- `/Users/sharan/Projects/flywheel-v2/backend/uv.lock` — Lock file updated

## Decisions Made

- **openpyxl added as explicit dependency**: Was pre-installed system-wide but absent from pyproject.toml. Added via `uv add openpyxl` for reproducibility.
- **SELECT-then-INSERT for contacts/activities**: No unique constraint on those tables, so ON CONFLICT unavailable. SELECT first avoids duplicates on re-runs.
- **In-memory dedup before DB calls**: Contacts list deduplicated by (company, email/name) in Python before touching DB — reduces queries on re-runs.
- **Source string merging**: Multiple sources comma-concatenated into `accounts.source`; ON CONFLICT DO UPDATE appends new sources only when not already present.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] openpyxl missing from project dependencies**
- **Found during:** Task 1 (xlsx file parsing)
- **Issue:** openpyxl not in pyproject.toml, import raised "not installed" error at runtime
- **Fix:** `uv add openpyxl` added package + updated lock file
- **Files modified:** backend/pyproject.toml, backend/uv.lock
- **Verification:** Import succeeded, xlsx parsed returning 206 accounts + 455 contacts
- **Committed in:** b196626

**2. [Rule 1 - Bug] Migration 025 duplicate column failure**
- **Found during:** Task 2 (running `alembic upgrade head` before live seeding)
- **Issue:** Migration 024 stamped but 025 not applied; DB already had the `metadata` column from prior manual work, causing `DuplicateColumnError`
- **Fix:** Added IF NOT EXISTS check via `information_schema.columns` query before `op.add_column`
- **Files modified:** backend/alembic/versions/025_uploaded_files_metadata.py
- **Verification:** `alembic upgrade head` succeeded, applying 025, 026, and 027
- **Committed in:** b196626

---

**Total deviations:** 2 auto-fixed (1 missing dependency, 1 migration bug)
**Impact on plan:** Both fixes required to reach live database. No scope creep — seed_crm.py is exactly what the plan specified.

## Issues Encountered

- Database was at migration 024; CRM tables (027) hadn't been applied. Resolved by running `alembic upgrade head` after fixing the 025 conflict.
- The last entry in pipeline-runs.json uses `scored_csv` and `run_id` keys instead of `csv_path` and `id` (different format). Handled by checking both key names.

## Next Phase Readiness

- All three CRM tables have real data: 206 accounts, 235 contacts, 81 outreach activities
- `normalize_company_name` proved effective — 0 duplicate normalized_name values despite variant company names across sources
- Phase 52 (Accounts API) can now query against populated tables

---
*Phase: 51-seed-cli*
*Completed: 2026-03-26*

## Self-Check: PASSED

- FOUND: backend/src/flywheel/seed_crm.py (1079 lines, exceeds 200-line minimum)
- FOUND: backend/alembic/versions/025_uploaded_files_metadata.py
- FOUND: .planning/phases/51-seed-cli/51-01-SUMMARY.md
- FOUND: commit b196626
