---
phase: 01-data-layer-and-gmail-foundation
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, postgresql, rls, orm, email]

# Dependency graph
requires: []
provides:
  - "Email ORM model (emails table): gmail message metadata, no body, RLS enforced"
  - "EmailScore ORM model (email_scores table): AI priority scores 1-5, category, context_refs"
  - "EmailDraft ORM model (email_drafts table): reply drafts with PII minimization (body nulled after send)"
  - "EmailVoiceProfile ORM model (email_voice_profiles table): per-user writing voice, one per tenant"
  - "Alembic migration 020_email_models: creates all four tables with RLS, grants, policies, triggers"
affects:
  - 01-02
  - 01-03
  - 02-gmail-sync
  - 03-email-scoring
  - 04-draft-generation
  - 05-email-copilot-ui

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Email models follow existing Mapped[T]/mapped_column() SQLAlchemy 2.0 pattern"
    - "Hand-written Alembic migrations with raw op.execute() SQL for full RLS control"
    - "Per-operation RLS policies (SELECT/INSERT/UPDATE/DELETE) using current_setting('app.tenant_id')"
    - "set_updated_at() trigger attached to tables with updated_at column"

key-files:
  created:
    - backend/alembic/versions/020_email_models.py
  modified:
    - backend/src/flywheel/db/models.py

key-decisions:
  - "No body column on emails table — PII minimization; body fetched on-demand for drafting only"
  - "UniqueConstraint on (tenant_id, gmail_message_id) prevents duplicate gmail syncs"
  - "UniqueConstraint on (tenant_id, user_id) for email_voice_profiles enforces one profile per user per tenant"
  - "Migration chains via down_revision = '019_documents' — verified alembic heads shows 020_email_models"
  - "RLS FORCE enabled on all four tables — superuser bypass not permitted at application layer"

patterns-established:
  - "EMAIL COPILOT TABLES section added to models.py after DOCUMENT TABLES"
  - "Migration uses op.execute() for each DDL statement — consistent with 019_documents.py pattern"
  - "Verification DO block in upgrade() asserts RLS enabled before migration finishes"

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 1 Plan 01: Email Copilot Data Foundation Summary

**Four SQLAlchemy 2.0 ORM models and Alembic migration 020_email_models creating emails, email_scores, email_drafts, and email_voice_profiles tables with per-operation RLS policies, tenant isolation, and set_updated_at triggers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T09:23:51Z
- **Completed:** 2026-03-24T09:27:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Four ORM model classes added to `models.py` following existing SQLAlchemy 2.0 mapped_column() patterns
- Alembic migration `020_email_models` chains from `019_documents` and creates all four tables with complete RLS setup
- All four tables verified with RLS enabled (`relrowsecurity=True`) and forced (`relforcerowsecurity=True`) in the local dev DB
- No body column on emails table confirmed — sender metadata only, snippet for preview

## Task Commits

Each task was committed atomically:

1. **Task 1: Add four email ORM models to models.py** - `7932615` (feat)
2. **Task 2: Create Alembic migration 020_email_models.py with RLS** - `8773cb6` (feat)

**Plan metadata:** (docs commit — see final_commit)

## Files Created/Modified
- `backend/src/flywheel/db/models.py` - Added Email, EmailScore, EmailDraft, EmailVoiceProfile ORM classes under EMAIL COPILOT TABLES section
- `backend/alembic/versions/020_email_models.py` - Hand-written migration creating four tables with RLS, grants, policies, and triggers

## Decisions Made
- No body column on emails — explicit project decision to minimize PII storage; body fetched on-demand for draft generation only
- Used `TEXT[]` array for labels with `DEFAULT '{}'::text[]` — no separate join table needed for Gmail label sync
- `context_refs JSONB DEFAULT '[]'` on email_scores — stores references to context entries that influenced scoring
- Migration uses flat `op.execute()` calls rather than `op.create_table()` helper — consistent with 019_documents.py pattern for full DDL control

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Python version mismatch during verification:** Initial import test ran system Python 3.9 instead of project Python 3.12 venv. System Python 3.9 doesn't support `str | None` union syntax. The project's `.venv/bin/python3` resolved the issue — models import cleanly with `from __future__ import annotations` and Python 3.12.

**Alembic connected to local dev DB (not Supabase):** The `alembic.ini` default URL points to `localhost:5434`. Without `DATABASE_URL` env var in shell, alembic used the local DB. The migration was verified against the local dev DB (`localhost:5434`) which is the correct target for local development. Supabase is the production database — migration will apply there during deployment.

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness
- Data layer foundation is complete — all four email tables exist and are ready for writes
- Plan 01-02 can now build the Gmail OAuth integration (`gmail-read` provider) using the `integrations` table that already exists
- Plan 01-03 can build the history-based sync engine writing to the new `emails` table
- No blockers for Phase 1 continuation

---
*Phase: 01-data-layer-and-gmail-foundation*
*Completed: 2026-03-24*
