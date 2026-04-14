# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v18.0 Broker Data Model v2 — Phase 130 (Schema -- Modifications)

## Current Position

Milestone: v18.0 Broker Data Model v2
Phase: 130 of 132 (Schema -- Modifications)
Plan: 1 of 2 in current phase (plan 01 complete)
Status: In progress
Last activity: 2026-04-15 — Plan 01 complete (14 additive columns added to 5 broker tables, alembic stamped 060)

Progress: [███░░░░░░░] 27% (3/11 plans)

## Performance Metrics

**Previous milestones:**
- v15.0 Broker Module MVP: 8 phases, 25 plans
- v16.0 Briefing Intelligence Surface: 2 phases, 4 plans
- v17.0 Broker Frontend: 7 phases, 16 plans

**v18.0 Broker Data Model v2:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 129. Schema -- New Tables | 2/2 | — | — |
| 130. Schema -- Modifications | 1/2 | — | — |
| 131. Backend -- Atomic Release | 0/4 | — | — |
| 132. Frontend -- Clients | 0/3 | — | — |

## Accumulated Context

### Decisions

All v1.0-v17.0 decisions archived in PROJECT.md Key Decisions table.

**129-01 (2026-04-14):** metadata DB column name is 'metadata' not 'metadata_' — consistent with all existing broker tables; RLS deferred to plan 02
- [Phase 129]: Alembic stamp applied via SQLAlchemy UPDATE (not CLI) because alembic env.py targets port 5434 which is unavailable; get_session_factory() uses correct pooler URL
- [Phase 130]: broker_projects.client_id uses ON DELETE SET NULL — projects survive client deletion
- [Phase 130]: All 14 new columns nullable — existing application code runs unchanged

### Key Constraints (v18.0)

- PgBouncer workaround: each DDL statement as own committed transaction, then alembic stamp
- Alembic stamp workaround: `alembic stamp` CLI targets port 5434 (direct DB), unavailable; use `UPDATE alembic_version SET version_num = 'XXX'` via get_session_factory() instead
- Carrier email seed MUST happen BEFORE dropping email_address column (data loss risk)
- Phase 131 is atomic: all model changes, services, endpoints, workflow restructure deploy together
- Solicitation workflow restructure touches 15+ CarrierQuote refs -- all change simultaneously
- Models must use Mapped[] syntax (not Column())

### Pending Todos

- Title matching false positives in _filter_unprepped (deferred from 66.1)
- Private import coupling in flywheel_ritual.py (tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-15
Stopped at: Completed 130-01-PLAN.md (14 additive columns added to 5 broker tables, alembic stamped 060)
Resume file: None
