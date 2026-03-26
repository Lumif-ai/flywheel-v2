---
phase: 50
plan: 02
subsystem: backend/data-model
tags: [orm, crm, models, normalization, utility]
dependency_graph:
  requires: [50-01-migrations]
  provides: [Account ORM model, AccountContact ORM model, OutreachActivity ORM model, normalize_company_name utility]
  affects: [Phase 51 seed CLI, Phase 52 account views API]
tech_stack:
  added: [flywheel.utils.normalize]
  patterns: [SQLAlchemy 2.0 Mapped[], mapped_column, relationship with back_populates and cascade]
key_files:
  modified: [backend/src/flywheel/db/models.py]
  created:
    - backend/src/flywheel/utils/__init__.py
    - backend/src/flywheel/utils/normalize.py
    - backend/src/tests/test_normalize.py
decisions:
  - "Single pass for space-suffix stripping before period removal; loop allowed only after period removal changed the string — prevents over-stripping 'Boston Consulting' while still stripping 'AI Solutions Inc.' fully"
  - "_bare_suffixes check applied only when period removal changed string — 'The Company' returns 'company' (no periods) but 'Inc.' returns '' (period removed)"
metrics:
  duration: "6 min"
  completed: "2026-03-26"
  tasks_completed: 2
  files_changed: 4
---

# Phase 50 Plan 02: CRM ORM Models and normalize_company_name Summary

**One-liner:** SQLAlchemy 2.0 ORM models for Account/AccountContact/OutreachActivity CRM tables plus a battle-tested normalize_company_name utility with period-aware suffix stripping.

## What Was Built

### Task 1: CRM ORM Models

Added three new model classes to `backend/src/flywheel/db/models.py` in a new `# CRM TABLES` section:

- **Account** — prospect/customer company with `contacts` and `outreach_activities` relationships, tenant-scoped with `uq_account_tenant_normalized` unique constraint and conditional indexes for status and next_action_due.
- **AccountContact** — person at an account, FK to `accounts.id` with CASCADE delete, partial index on email.
- **OutreachActivity** — outreach touchpoint (email, call, LinkedIn), FK to both `accounts.id` and optional `account_contacts.id`.

Updated `ContextEntry` to add optional `account_id` FK (`ForeignKey("accounts.id", ondelete="SET NULL")`) and `account` relationship.

Updated module docstring to mention CRM tables.

### Task 2: normalize_company_name Utility

Created `backend/src/flywheel/utils/normalize.py` with `normalize_company_name(name: str) -> str`.

Algorithm (handles period-based abbreviations correctly):
1. Strip/lowercase
2. Remove "the " prefix
3. Strip comma-separated suffixes (one match)
4. Strip space-separated suffixes (single pass — prevents over-stripping)
5. Remove all periods
6. If period removal changed the string: loop space-suffix stripping + bare-suffix check

Key contract satisfied: `normalize_company_name("Acme Corp., Inc.") == normalize_company_name("acme corp") == normalize_company_name("The Acme Corporation") == normalize_company_name("ACME") == "acme"`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] normalize_company_name required period-aware two-phase suffix stripping**

- **Found during:** Task 2 — running tests after initial implementation
- **Issue:** Initial plan description specified a simple loop for suffix stripping, but this caused over-stripping: `"Boston Consulting Group"` → `"boston"` instead of `"boston consulting"`. Simultaneously, `"A.I. Solutions Inc."` needed multi-pass stripping to reach `"ai"` (stripping both `inc.` and `solutions`).
- **Fix:** Split suffix stripping into two phases: (a) single pass before period removal to handle plain names, (b) loop + bare-suffix check ONLY when period removal changed the string. This handles period-based abbreviations aggressively while leaving plain names intact.
- **Files modified:** `backend/src/flywheel/utils/normalize.py`
- **Commit:** 85b0df9

## Verification

All 5 success criteria confirmed:

1. `python -c "from flywheel.db.models import Account, AccountContact, OutreachActivity"` — import succeeds
2. Account has `contacts` and `outreach_activities` relationships
3. ContextEntry has `account_id` column and `account` relationship
4. `uv run python -m pytest src/tests/test_normalize.py -v` — 20/20 passed
5. `normalize_company_name("Acme Corp., Inc.") == normalize_company_name("acme corp")` — True

## Self-Check: PASSED

- `backend/src/flywheel/db/models.py` — exists, CRM models appended
- `backend/src/flywheel/utils/normalize.py` — exists, normalize_company_name implemented
- `backend/src/flywheel/utils/__init__.py` — exists (package marker)
- `backend/src/tests/test_normalize.py` — exists, 20 tests
- Commit 85b0df9 — verified in git log
