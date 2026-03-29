# Flywheel V2

## What This Is

An AI-powered work intelligence platform that compounds knowledge from meetings, companies, projects, and relationships — then surfaces it through action-oriented channels. Ships an email copilot (Gmail sync, scoring, draft replies) and a company-centric CRM that turns accumulated GTM intelligence into Accounts, Pipeline, and Pulse views. All data is populated automatically from skill runs — zero manual entry.

## Core Value

Founders never lose track of an account again. Every company they're engaging with — prospects, active deals, customers — has a single screen showing all contacts, interaction timeline, commitments, intel, and next actions. All populated automatically from skill runs.

## Current Milestone: v4.0 Flywheel OS — Intelligence Operating System for Founders

**Goal:** Transform the intelligence layer into a founder's daily operating system. Conversations automatically become tracked commitments and executed deliverables. Unified meetings timeline (Google Calendar + Granola), automatic task extraction from transcripts, and a `/flywheel` CLI ritual that ties everything together.

**Three-layer architecture:**
- **Layer 1 (Intelligence):** Exists — meetings, emails, context store (v1.0-v3.0)
- **Layer 2 (Autopilot):** NEW — detect commitments from conversations, map to skills, confirm before executing
- **Layer 3 (Ritual):** NEW — `/flywheel` CLI + `/brief` web page as daily cockpit

**Target features (Phases A-C):**
- Unified meetings table: Google Calendar events + Granola transcripts in one timeline with dedup
- Task extraction: Stage 7 in meeting processor, 5-category commitment classification via Haiku
- Tasks CRUD API with status state machine and trust ladder
- `/flywheel` CLI skill with 5 subcommands (full brief, sync, tasks, prep, process)
- Meetings page redesign: Upcoming + Past tabs

**Shipped milestones:**
- **v1.0 Email Copilot** (2026-03-25) — Gmail sync, 5-tier scoring, voice-learned drafts, review UI, feedback loop
- **v2.0 AI-Native CRM** (2026-03-27) — Accounts/Pipeline/Pulse surfaces, REST APIs, seed CLI, auto-graduation
- **v2.1 CRM Redesign** (2026-03-27) — Pipeline grid, 4 relationship surfaces, AI synthesis, signal badges
- **v3.0 Intelligence Flywheel** (2026-03-28) — Team privacy, Granola adapter, meeting intelligence pipeline, prep loop

**Codebase:** FastAPI + React, 206 seeded accounts from GTM stack

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

### Active

<!-- v4.0 Flywheel OS scope (Phases A-C) -->

- [ ] Unified meetings: Calendar sync writes Meeting rows, dedup with Granola, lifecycle status (UNI-01 through UNI-08)
- [ ] Tasks table: ORM model, RLS, 7-status state machine, commitment_direction, trust_level (TASK-01)
- [ ] Task extraction: Stage 7 in meeting processor, Haiku 5-category classification (TASK-02)
- [ ] Tasks CRUD API: paginated list, filters, status transitions, confirm/dismiss shortcuts (TASK-03)
- [ ] Task signals: counts in signals endpoint for sidebar badges (TASK-04)
- [ ] /flywheel CLI: daily brief, sync, tasks, prep, process subcommands (FLY-01 through FLY-06)
- [ ] Meetings page redesign: Upcoming + Past tabs (UNI-05)

### Out of Scope

- Auto-skill execution of detected tasks — Phase E (v4.0 detects only, doesn't execute)
- Task extraction from emails — Phase F
- Task extraction from Slack — deferred
- Contact discovery (web research for unknown attendees) — Phase D
- GTM outreach integration in /flywheel — Phase G
- Web UI for /brief and /tasks pages — Phase H
- Auto-send / YOLO mode — email sending NEVER automatic (hard constraint)
- Multi-user task assignment — tasks are Zone 1 (user-private)
- Mobile-optimized views
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
| Five separate relationship surfaces | Different JTBD and emotional registers per type | — Pending |
| Advisors are people-first | Advisors/angels are individuals, not company-level | — Pending |
| Multi-type relationships | A person/company can hold multiple types simultaneously | — Pending |
| AI synthesis from day one | 8-10 relationships have deep data; graceful degradation for sparse | — Pending |
| Auto-materialization for prospects | Reply/meeting signal promotes from Pipeline | — Pending |
| Pipeline as Airtable grid | 200+ companies need spreadsheet-density triage | — Pending |
| Interactive AI panel | Chat + notes + files in one panel per relationship | — Pending |

---
*Last updated: 2026-03-28 after v4.0 Flywheel OS milestone initialization*
