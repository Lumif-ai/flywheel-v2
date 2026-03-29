# Flywheel V2

## What This Is

An AI-powered intelligence operating system for founders. Compounds knowledge from meetings, emails, companies, and relationships — then acts on it. Conversations automatically become tracked commitments and executed deliverables via a daily flywheel ritual. Ships email copilot, intelligence-first CRM, meeting intelligence pipeline, task extraction, and an automated daily operating loop.

## Core Value

Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system.

## Current State

All four milestones shipped. The platform is functionally complete for single-founder dogfooding.

**Shipped milestones:**
- **v1.0 Email Copilot** (2026-03-25) — Gmail sync, 5-tier scoring, voice-learned drafts, review UI, feedback loop
- **v2.0 AI-Native CRM** (2026-03-27) — Accounts/Pipeline/Pulse surfaces, REST APIs, seed CLI, auto-graduation
- **v2.1 CRM Redesign** (2026-03-27) — Pipeline grid, 4 relationship surfaces, AI synthesis, signal badges
- **v3.0 Intelligence Flywheel** (2026-03-28) — Team privacy, Granola adapter, meeting intelligence pipeline, prep loop
- **v4.0 Flywheel OS** (2026-03-29) — Unified meetings, task extraction, flywheel ritual engine, stabilization

**Codebase:** FastAPI + React, ~20K LOC backend, ~15K LOC frontend

## Requirements

### Validated

<!-- Shipped and confirmed valuable -->

- ✓ Gmail OAuth (send-only) — `services/google_gmail.py`
- ✓ Background sync loop pattern — `services/calendar_sync.py`
- ✓ Context store with full-text search + entity graph — `context_utils.py`
- ✓ Skill executor with async tool loop — `services/skill_executor.py`
- ✓ Email send dispatch — `services/email_dispatch.py`
- ✓ Tenant isolation via RLS — all tables
- ✓ AES-256-GCM credential encryption — `auth/encryption.py`
- ✓ Gmail read sync (expanded scopes, background polling) — v1.0 Phase 1-2
- ✓ Email scoring using context store — v1.0 Phase 3
- ✓ Draft reply generation with voice learning — v1.0 Phase 4
- ✓ Review UI (scored threads + draft approvals) — v1.0 Phase 5
- ✓ In-app critical email alerts — v1.0 Phase 5
- ✓ Feedback loop (approvals/edits improve scoring + voice) — v1.0 Phase 6
- ✓ CRM data model (accounts, account_contacts, outreach_activities with RLS) — v2.0 Phase 50
- ✓ ORM models for Account, AccountContact, OutreachActivity — v2.0 Phase 50
- ✓ Company name normalization utility — v2.0 Phase 50
- ✓ Data seeding CLI from existing GTM stack files — v2.0 Phase 51
- ✓ Accounts REST API (list, detail, create, update, graduate) — v2.0 Phase 52
- ✓ Account contacts REST API (CRUD) — v2.0 Phase 52
- ✓ Outreach activities REST API + pipeline view — v2.0 Phase 52
- ✓ Account timeline API (unified chronological feed) — v2.0 Phase 52
- ✓ Pulse signals API (prioritized intelligence feed) — v2.0 Phase 52
- ✓ Account graduation automation — v2.0 Phase 52
- ✓ Accounts list page at /accounts — v2.0 Phase 53
- ✓ Account detail page at /accounts/{id} — v2.0 Phase 53
- ✓ Pipeline page at /pipeline — v2.0 Phase 53
- ✓ Sidebar navigation updates (Accounts, Pipeline) — v2.0 Phase 53
- ✓ Pulse feed component on Briefing page — v2.0 Phase 53
- ✓ Data model evolution (relationship_type, entity_level, ai_summary) — v2.1 Phase 54
- ✓ Relationships API with partition predicate + rate limiting — v2.1 Phase 55
- ✓ Pipeline grid (AG Grid, filters, saved views, graduation) — v2.1 Phase 56
- ✓ Four relationship surfaces with AI context panel — v2.1 Phase 57
- ✓ Unified Company Intelligence Engine — v2.1 Phase 58
- ✓ Team Privacy Foundation (user-level RLS) — v3.0 Phase 59
- ✓ Meeting data model + Granola adapter — v3.0 Phase 60
- ✓ Meeting Intelligence Pipeline (9 insight types, auto-linking) — v3.0 Phase 61
- ✓ Meeting surfaces + relationship enrichment — v3.0 Phase 62
- ✓ Meeting Prep Loop (context-aware briefings) — v3.0 Phase 63
- ✓ Unified meetings (calendar + Granola dedup) — v4.0 Phase 64
- ✓ Task intelligence (extraction, API, signals) — v4.0 Phase 65
- ✓ Flywheel ritual engine (5-stage daily loop) — v4.0 Phase 66
- ✓ Flywheel stabilization (18 issues fixed) — v4.0 Phase 66.1

### Active

<!-- Next milestone scope — TBD -->

(No active requirements — next milestone not yet defined)

### Out of Scope

- Auto-send / YOLO mode — email sending NEVER automatic (hard constraint)
- Multi-user task assignment — tasks are Zone 1 (user-private)
- Mobile-optimized views
- Task extraction from Slack — deferred
- Granola webhook/polling sync — remains on-demand

## Context

**Existing architecture:** FastAPI + PostgreSQL (async, tenant-isolated, RLS), Supabase Storage, multi-provider OAuth (Google, Microsoft, Slack), skill-based execution (async tool loops with context weighting), context store (atomic facts + full-text search + entity graph).

**CRM design principles (evolved in v2.1 brainstorm):**
- Company-first for Prospects/Customers, person-first for Advisors/Angel investors
- Five distinct JTBD: triage (Pipeline), nurture prospects, manage customers, maintain advisors, manage investors
- View layer over accumulated intelligence — not a database to fill
- Manual context capture allowed (notes, files) alongside skill-generated data
- Two paradigms: Pipeline is a data grid (Airtable), Relationships are intelligence journals (warmth)
- AI synthesis is the product differentiator, not just the UI

**Specs:**
- `.planning/SPEC-ai-native-crm.md` (v2.0)
- `.planning/SPEC-crm-redesign.md` (v2.1)
- `.planning/SPEC-flywheel-os.md` (v4.0 — current, reviewed)
**Concept briefs:**
- `.planning/CONCEPT-BRIEF-ai-native-crm.md` (v2.0)
- `.planning/CONCEPT-BRIEF-crm-redesign.md` (v2.1)
- `.planning/CONCEPT-BRIEF-flywheel-os.md` (v4.0 — 4-round brainstorm, 14 advisors)

## Constraints

- **Stack**: FastAPI + PostgreSQL + SQLAlchemy 2.0 (async) — existing backend
- **Frontend**: React + Vite + Tailwind v4 — existing frontend
- **No manual entry**: Accounts/contacts/outreach created by skills, not user forms
- **Company-first**: Every contact belongs to an account. No standalone contact view.
- **Existing patterns**: All new endpoints follow established pagination (offset/limit), auth (require_tenant + get_tenant_db), RLS (ENABLE + FORCE + policy + GRANT)
- **Design system**: Inter font, #E94D35 coral accent, 12px radius, warm tints

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Extract + discard email body | PII minimization, scoring needs signals only | ✓ Good |
| Three-entity email model | Simple, decomplected, each entity has clear purpose | ✓ Good |
| Thread-level display, message-level scoring | Matches human mental model | ✓ Good |
| Company-first not person-first | B2B engagement is account-level, matches how founders talk | ✓ Good |
| Accounts as top-level nav | Investors/partners aren't revenue, need cross-focus visibility | ✓ Good |
| Pipeline separate from Accounts | Different JTBD: triage/execute vs nurture/track | ✓ Good |
| Clean break migration + seed | 3 users, no legacy debt, can afford to break | ✓ Good |
| CSV outreach → database | Relational joins, timeline, multi-founder visibility required | ✓ Good |
| Feed + Table (Pulse + Pipeline/Accounts) | Different temporal needs: daily signals vs portfolio assessment | ✓ Good |
| Correlated subquery for contact_count | Avoids left join complexity when counting | ✓ Good |
| 3-source timeline merged in Python | Simpler than UNION ALL with mismatched column shapes | ✓ Good |
| ActionBar buttons as toast stubs | Skill integration deferred — keep UI shippable now | — Pending |
| Five separate relationship surfaces | Different JTBD and emotional registers per type | ✓ Good |
| Advisors are people-first | Advisors/angels are individuals, not company-level | ✓ Good |
| Multi-type relationships | A person/company can hold multiple types simultaneously | ✓ Good |
| AI synthesis from day one | 8-10 relationships have deep data; graceful degradation for sparse | ✓ Good |
| Auto-materialization for prospects | Reply/meeting signal promotes from Pipeline | ✓ Good |
| Pipeline as Airtable grid | 200+ companies need spreadsheet-density triage | ✓ Good |
| Interactive AI panel | Chat + notes + files in one panel per relationship | ✓ Good |
| Unified meetings table | Calendar + Granola in one table with fuzzy dedup | ✓ Good |
| Task extraction via Haiku | Cheap/fast classification, full context from transcript + intel | ✓ Good |
| Flywheel as backend engine | Same architecture as meeting-prep/processor, not standalone CLI | ✓ Good |
| trust_level='confirm' for all tasks | Founder reviews everything, no auto-execution | ✓ Good |
| Execution caps (20 process, 15 prep) | Prevents MCP timeout on large batches | ✓ Good |

---
*Last updated: 2026-03-29 after v4.0 Flywheel OS milestone completion*
