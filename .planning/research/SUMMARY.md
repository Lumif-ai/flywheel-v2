# Project Research Summary

**Project:** Broker Data Model Restructuring — Clients, Contacts, Context Store & Solicitation Workflow
**Domain:** Insurance broker platform — client/contact management, regulated communication workflows, CRM-intelligence bridge
**Researched:** 2026-04-14
**Confidence:** HIGH

## Executive Summary

This milestone adds the client/contact layer to an existing broker module (6 tables, 29 endpoints, 37 components already built) and restructures two core workflows — solicitation drafting and recommendation delivery — from ad-hoc column storage into proper first-class entities. The work requires zero new Python or npm dependencies. Every capability needed (SQLAlchemy 2.0 partial indexes, CHECK constraints, async upserts, context entity creation) exists in the current stack. The primary challenge is structural: carefully sequenced schema migrations, simultaneous replacement of 15+ column references, and strict migration execution discipline to work around Supabase PgBouncer's silent DDL rollback behavior.

The recommended approach is a 4-phase build: schema-first (new tables, then modifications with a mandatory data-seed step between creation and column drops), followed by a single atomic backend release that replaces all removed columns simultaneously, followed by a standalone frontend phase. The context store intelligence bridge — linking every broker entity to a ContextEntity — is the product's primary moat mechanism. No commercial AMS (Applied Epic, AMS360, BindHQ) combines placement workflow with accumulated relationship intelligence. This differentiator must be built into the data model from the start, not retrofitted later.

The biggest risk is the solicitation workflow restructure. The current code creates CarrierQuote rows at solicitation time; the new architecture defers quote creation until quote receipt and creates SolicitationDraft rows instead. At least 15 references across broker.py (task generation, follow-up detection, project status auto-transition, portal submission) depend on the current CarrierQuote-at-draft-time assumption. All must be updated simultaneously — incremental migration of this workflow is not safe. A secondary risk is the carrier email_address migration: the column must be seeded into carrier_contacts and verified before it is dropped, or carrier emails are permanently lost with no recovery path.

## Key Findings

### Recommended Stack

No new dependencies are required. The existing stack — SQLAlchemy 2.0 async, Alembic 1.14, FastAPI, Pydantic v2, PostgreSQL 15 (Supabase) — covers every capability needed. The one change to existing code is adding CheckConstraint to the sqlalchemy import in models.py (not currently imported). The codebase's existing entity_normalization.py covers name deduplication; it needs suffix list expansion for Mexican legal entity forms (S.A. de C.V., S.A.S., S. de R.L. de C.V.) but no new library. The existing partial unique index pattern (20+ instances in models.py) covers the two new partial indexes needed.

**Core technologies:**
- SQLAlchemy 2.0 async: ORM and model definitions — already in use; Mapped[]/mapped_column() syntax required for consistency with existing broker models
- Alembic 1.14: Migration state tracking — used for alembic stamp only; actual DDL executed via migration script (PgBouncer workaround)
- PostgreSQL CHECK constraints: Enum validation at DB level — CheckConstraint class, zero new library
- entity_normalization.py (custom): Name dedup — expand suffix list for MX/LATAM legal forms, no new library
- context_store_writer.py (custom): Context entity upsert — add create_context_entity() using existing pg_insert ON CONFLICT pattern

### Expected Features

**Must have (table stakes):**
- Client entity with normalized name dedup — brokers cannot answer "all projects for Alaya?" without this; RFC/EIN tax_id mandatory for Mexican SAT compliance
- Client contacts with roles — CFO, project manager, billing contact; is_primary flag for automated email routing
- Carrier contacts with roles — submissions vs account_manager vs underwriter; current single email_address string is inadequate for real brokerage workflow
- Client-project link — nullable FK on broker_projects; application gate requires client before status transitions past analyzing
- Solicitation approval workflow — separate approve from send; regulated insurance communications require compliance review before transmission
- Recommendation as proper entity — version history, audit trail, E&O liability protection; current column-on-project model is unacceptable in a regulated domain
- Project email thread tracking — replace TEXT[] array with proper table; enables timeline reconstruction and inbound/outbound filtering
- Audit columns on all tables — created_by_user_id/updated_by_user_id on 5 existing tables; "who did what when" is non-optional in regulated insurance
- Binding status — explicit binding workflow state between recommended and bound; BindHQ, Applied Epic, and ExpertInsured all model this as a distinct step

**Should have (competitive differentiators):**
- Context store intelligence bridge — every broker entity links to ContextEntity; meetings, emails, and signals surface where they matter; no AMS does this
- Normalized name dedup with Mexican legal suffix stripping — genuine competitive advantage in Mexico construction insurance market; no US-focused AMS handles S.A. de C.V. correctly
- Solicitation draft versioning with audit trail — immutable sent drafts; revision history for E&O defense
- AI-powered solicitation personalization from context — carrier relationship intelligence feeds solicitation drafts (defer until context data accumulates)

**Defer (v2+):**
- AI-powered solicitation personalization — requires accumulated context signals; build the bridge first
- Carrier response pattern tracking — requires historical data; instrument now, surface patterns later
- Client intelligence panel — requires accumulated context signals per entity
- Contact import from CSV/Excel, real-time enrichment, client portal, CRM sync — explicitly out of scope for this milestone

### Architecture Approach

The milestone restructures the broker module's data layer without changing its external shape. Two new service classes (broker_client_service.py, broker_contact_service.py) extract business logic from the router, keeping broker.py as thin HTTP wrappers. The context_store_writer.py gains a create_context_entity() function using upsert semantics. New models use SQLAlchemy 2.0 Mapped[]/mapped_column() style consistently with existing broker models. The router stays a single file — net growth is only ~200 lines because solicitation/recommendation endpoints are restructured, not purely added.

**Major components:**
1. broker_client_service.py (NEW) — Client CRUD, name normalization, dedup, synchronous context entity linking within the same transaction
2. broker_contact_service.py (NEW) — Contact CRUD for both client and carrier contacts; soft limits (20/client, 10/carrier)
3. create_context_entity() in context_store_writer.py (NEW function) — upsert ContextEntity via pg_insert ON CONFLICT DO UPDATE; returns existing or new entity
4. 6 new SQLAlchemy model classes — BrokerClient, BrokerClientContact, CarrierContact, BrokerRecommendation, SolicitationDraft, BrokerProjectEmail; all using Mapped[] syntax
5. broker_data_model_migration.py (NEW script) — each DDL statement as its own committed transaction (PgBouncer workaround); ~40-50 individual statements
6. broker.py router (MODIFIED) — restructured solicitation and recommendation flows; thin service wrappers for client/contact endpoints; net ~3100 lines

### Critical Pitfalls

1. **PgBouncer silently rolls back multi-statement DDL** — Supabase's pooler commits the alembic_version row but rolls back actual DDL. Each statement must run as its own await session.execute() + await session.commit(). Use alembic stamp after. Never use Alembic upgrade() directly for DDL on Supabase.

2. **Dropping carrier_configs.email_address before seeding carrier_contacts** — Migration must be three separate committed transactions: CREATE carrier_contacts, then INSERT INTO carrier_contacts SELECT from carrier_configs WHERE email_address IS NOT NULL, then verify count, then DROP COLUMN. Dropping first means permanent data loss with no recovery path.

3. **Solicitation workflow restructure breaks 15+ CarrierQuote assumptions** — Task generation, follow-up detection, project status auto-transition, portal submission, and the send endpoint all assume CarrierQuote exists after drafting. All 15+ references must be updated simultaneously to query SolicitationDraft. Cannot be done incrementally.

4. **CHECK constraints fail on tables with existing data** — Query DISTINCT values in existing rows before adding any CHECK constraint. Use NOT VALID + separate VALIDATE pattern. Each statement is its own committed transaction (Pitfall 1 compounds this). Wrong enum strings will fail silently under PgBouncer.

5. **Context store entity upsert required, not insert** — ContextEntity has a unique constraint on (tenant_id, name, entity_type). A client named "Acme Corp" may already exist from email extraction. Use INSERT ON CONFLICT DO UPDATE, not INSERT. Wrap client + entity creation in a single transaction — if entity creation fails, client creation must roll back.

6. **15 column drops create ghost references across full stack** — carrier_configs.email_address has 12 backend refs (3 files) and 9 frontend refs (3 files). recommendation_* columns have 15+ broker.py refs. Run full-codebase grep for every dropped column before migration. Update all references before dropping any column.

## Implications for Roadmap

Based on the combined research, a 4-phase structure is strongly recommended. The ordering is driven by hard dependencies: schema must precede code, data seeds must precede column drops, and the solicitation restructure must be atomic.

### Phase 1: Schema — New Tables
**Rationale:** Zero application dependency. New tables can exist without any code referencing them. This phase establishes the foundation for all subsequent phases with no risk of breaking existing functionality.
**Delivers:** 6 new tables (broker_clients, broker_client_contacts, carrier_contacts, solicitation_drafts, broker_recommendations, broker_project_emails) + RLS policies for each table
**Addresses:** All table stakes features that require new tables — client entity, contacts, solicitation drafts, recommendation entity, email tracking
**Avoids:** PgBouncer silent rollback (Pitfall 1), missing RLS (Pitfall 11)

### Phase 2: Schema — Modifications + Data Seed
**Rationale:** Must follow Phase 1 (FK references to new tables). The carrier email seed MUST happen in this phase, between column additions and column drops. This is the most operationally risky phase because data loss is possible.
**Delivers:** 5 existing tables modified (audit columns, new FKs, CHECK constraints, binding status), carrier email data seeded into carrier_contacts, 15 columns dropped
**Addresses:** Audit columns, binding status lifecycle, FK cleanup (carrier_pipeline_entry_id)
**Avoids:** Lost email_address data (Pitfall 2), CHECK constraint failures on existing data (Pitfall 4), FK blocking column drop (Pitfall 10)

### Phase 3: Backend — Models, Services & Endpoints (Atomic Release)
**Rationale:** Column drops in Phase 2 mean the existing model code crashes immediately on any reference to removed columns. All model changes, service classes, new endpoints, and restructured endpoints must deploy together. Highest-complexity phase.
**Delivers:** 6 new SQLAlchemy model classes, broker_client_service.py, broker_contact_service.py, create_context_entity() function, 17 new endpoints, solicitation workflow restructured to SolicitationDraft, recommendation workflow restructured to BrokerRecommendation, gmail_sync updated for carrier contact JOIN
**Addresses:** Context store intelligence bridge, solicitation approval workflow, recommendation as proper entity, carrier contacts with roles, client-project linking
**Avoids:** Ghost references (Pitfall 6), solicitation workflow breakage (Pitfall 3), context entity upsert failure (Pitfall 5), name normalization failure (Pitfall 8), gmail sync breakage (Pitfall 13)

### Phase 4: Frontend — Clients & Contacts
**Rationale:** Pure frontend work, independently deployable after Phase 3. No backend changes required.
**Delivers:** Updated TypeScript types in broker.ts, 14 new API functions, Clients list page (ag-grid), Client detail page with contacts section, sidebar navigation update, CreateProjectDialog with client_id dropdown, CarrierForm contacts section
**Addresses:** Client entity visibility, contact management UI, client-project linking in UI
**Avoids:** TypeScript type drift (Pitfall 12)

### Phase Ordering Rationale

- Schema-before-code is non-negotiable: column drops in Phase 2 crash existing model code; new tables in Phase 1 are required by Phase 2 FKs
- The carrier email seed step must be within the same phase as the column drop — a separate phase creates risk of the drop executing without the seed
- The backend Phase 3 must be atomic with respect to column drops: partial deployment of model changes causes immediate runtime crashes
- Frontend (Phase 4) is decoupled from backend atomicity — it can be built and deployed independently after Phase 3 is stable
- The broker.py file split (noted in PITFALLS.md Pitfall 9) is recommended before adding new endpoints. ARCHITECTURE.md argues for staying single-file since net growth is only ~200 lines with service classes absorbing complexity. Validate team preference before starting Phase 3.

### Research Flags

No phases require /gsd:research-phase. All research is complete and HIGH confidence throughout.

Phases with standard patterns (skip research-phase):
- **Phase 1:** DDL migration follows existing broker_migration.py pattern exactly. RLS template is established.
- **Phase 2:** Column additions, CHECK constraints, FK drops are all established patterns. Execution verification steps are the key risk mitigation, not additional research.
- **Phase 3:** All patterns are direct codebase derivations. The solicitation restructure reference map (15+ sites) is the critical pre-work, not a research gap.
- **Phase 4:** ag-grid, shared module toolkit, and existing broker component patterns are all well-established in this codebase.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations from direct codebase inspection of models.py, pyproject.toml, entity_normalization.py. Zero external library decisions. |
| Features | HIGH | Grounded in approved spec (SPEC-BROKER-DATA-MODEL.md, PROPOSAL-BROKER-DATA-MODEL.md) plus industry research across Applied Epic, BindHQ, BrokerEdge, ExpertInsured. Advisory board analysis (14 advisors, 4 rounds). |
| Architecture | HIGH | All architectural decisions from reading actual broker.py (2900 lines), models.py (2397 lines), context_store_writer.py (373 lines). Specific line numbers cited throughout. |
| Pitfalls | HIGH | PgBouncer behavior proven in production via existing broker_migration.py. CHECK constraint behavior verified against PostgreSQL docs. Column reference counts from direct codebase grep. |

**Overall confidence:** HIGH

### Gaps to Address

- **broker.py file split decision:** ARCHITECTURE.md recommends keeping broker.py as a single file (~3100 lines with service classes). PITFALLS.md recommends splitting before adding endpoints (Pitfall 9). Both positions are defensible. Validate team preference before Phase 3 planning.

- **Exact carrier email_address row count:** Run `SELECT COUNT(*) FROM carrier_configs WHERE email_address IS NOT NULL` before writing Phase 2 migration. This is the verification target for the seed step in Phase 2.

- **Existing data for CHECK constraint validation:** Before Phase 2, run `SELECT DISTINCT analysis_status FROM broker_projects`, `SELECT DISTINCT status FROM carrier_quotes`, and similar for every column receiving a CHECK constraint. The allowed value lists in the spec must match actual live data exactly.

## Sources

### Primary (HIGH confidence)
- backend/src/flywheel/db/models.py — SQLAlchemy model definitions, existing patterns, import structure
- backend/src/flywheel/api/broker.py — 2900 lines, 29 endpoints, solicitation/recommendation workflows
- backend/src/flywheel/services/entity_normalization.py — existing normalization logic and find_or_create_entity
- backend/src/flywheel/services/context_store_writer.py — existing context entry writing patterns
- backend/pyproject.toml — dependency versions
- SPEC-BROKER-DATA-MODEL.md — full spec (10 sections, reviewed by advisory board)
- PROPOSAL-BROKER-DATA-MODEL.md — board-reviewed schema proposal
- CONCEPT-BRIEF-BROKER-DATA-MODEL.md — advisory board analysis (14 advisors, 4 rounds)
- Project memory (MEMORY.md, CLAUDE.md) — Supabase DDL workaround, FK limitations, established conventions

### Secondary (MEDIUM confidence)
- BindHQ (bindhq.com) — submission-to-binding automation, workflow stages
- BrokerEdge (damcogroup.com) — contact management, task workflow
- ExpertInsured (expertinsured.com) — intake-to-bind workflow stages
- GenasysTech AI Insurance 2026 — speed-to-quote as competitive moat
- McKinsey AI in Insurance — data ownership differentiation
- Mexico RFC Guide (signzy.com) — SAT requirements, CFDI validation

### Tertiary (supporting context)
- Applied Epic / AMS360 / HawkSoft feature comparisons — table stakes expectations
- Deloitte commercial insurance AI transformation — data ownership as competitive moat

---
*Research completed: 2026-04-14*
*Ready for roadmap: yes*
