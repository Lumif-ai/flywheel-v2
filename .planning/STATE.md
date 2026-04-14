# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v18.0 Broker Data Model v2 — Phase 131 (Backend -- Atomic Release)

## Current Position

Milestone: v18.0 Broker Data Model v2
Phase: 131 of 132 (Backend -- Atomic Release)
Plan: 2 of 4 in current phase (plan 02 complete — BrokerClientService, BrokerContactService, create_context_entity)
Status: In progress
Last activity: 2026-04-15 — Plan 02 complete (BrokerClientService + BrokerContactService created, create_context_entity added to context_store_writer.py)

Progress: [████░░░░░░] 45% (5/11 plans)

## Performance Metrics

**Previous milestones:**
- v15.0 Broker Module MVP: 8 phases, 25 plans
- v16.0 Briefing Intelligence Surface: 2 phases, 4 plans
- v17.0 Broker Frontend: 7 phases, 16 plans

**v18.0 Broker Data Model v2:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 129. Schema -- New Tables | 2/2 | — | — |
| 130. Schema -- Modifications | 2/2 | — | — |
| 131. Backend -- Atomic Release | 2/4 | — | — |
| 132. Frontend -- Clients | 0/3 | — | — |

## Accumulated Context

### Decisions

All v1.0-v17.0 decisions archived in PROJECT.md Key Decisions table.

**129-01 (2026-04-14):** metadata DB column name is 'metadata' not 'metadata_' — consistent with all existing broker tables; RLS deferred to plan 02
- [Phase 129]: Alembic stamp applied via SQLAlchemy UPDATE (not CLI) because alembic env.py targets port 5434 which is unavailable; get_session_factory() uses correct pooler URL
- [Phase 130]: broker_projects.client_id uses ON DELETE SET NULL — projects survive client deletion
- [Phase 130]: All 14 new columns nullable — existing application code runs unchanged
- [Phase 130-02]: ALLOWED_TRANSITIONS delivered->binding->bound; binding is intermediate state before bound
- [Phase 130-02]: broker_activities FK uses NOT VALID then VALIDATE — tolerates orphan rows gracefully
- [Phase 131-01]: 6 new models inserted between CarrierConfig and BrokerProject so BrokerClient is defined before BrokerProject FK client_id references it — avoids forward-ref issues
- [Phase 131-01]: broker.py preserved as backup; Python resolves package (broker/) over module (broker.py) for `from flywheel.api.broker import router`
- [Phase 131-01]: REQUIRES_CLIENT_STATES added to _shared.py — validate_transition enforces client_id must be set before advancing past 'analyzing' state
- [Phase 131-02]: create_context_entity uses local import for ContextEntity inside function body to avoid circular import risk
- [Phase 131-02]: BrokerContactService.delete_contact uses contact_type: str param to handle both BrokerClientContact and CarrierContact in one method

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
Stopped at: Completed 131-02-PLAN.md (BrokerClientService + BrokerContactService created, create_context_entity added to context_store_writer.py)
Resume file: None
