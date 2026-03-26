# Flywheel V2

## What This Is

An AI-powered work intelligence platform that compounds knowledge from meetings, companies, projects, and relationships — then surfaces it through action-oriented channels. Ships an email copilot (Gmail sync, scoring, draft replies) and a company-centric CRM that turns accumulated GTM intelligence into Accounts, Pipeline, and Pulse views. All data is populated automatically from skill runs — zero manual entry.

## Core Value

Founders never lose track of an account again. Every company they're engaging with — prospects, active deals, customers — has a single screen showing all contacts, interaction timeline, commitments, intel, and next actions. All populated automatically from skill runs.

## Current State

**Shipped milestones:**
- **v1.0 Email Copilot** (2026-03-25) — Gmail sync, 5-tier scoring, voice-learned drafts, review UI, feedback loop
- **v2.0 AI-Native CRM** (2026-03-27) — Accounts/Pipeline/Pulse surfaces, REST APIs, seed CLI, auto-graduation

**Codebase:** FastAPI + React, ~63 files changed in v2.0 (+7,866 lines), 206 seeded accounts from GTM stack

**Next milestone:** Not yet defined — run `/gsd:new-milestone` to plan

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

<!-- Next milestone scope — TBD -->

(None yet — define with `/gsd:new-milestone`)

### Out of Scope

- Custom pipeline stages — fixed: scored → sent → awaiting → replied → graduated
- Calendar integration for auto-detecting meetings with accounts
- Email sync / passive inbox capture — only skill-generated outreach
- Mobile-optimized views
- Slack/email notification delivery for Pulse signals
- Kanban drag-and-drop for Pipeline — table view only
- Bulk outreach sending from Pipeline UI
- Account merge/dedup UI — handled by normalization in seed command
- Auto-send / YOLO mode — trust must be earned first (v1.0 decision)

## Context

**Existing architecture:** FastAPI + PostgreSQL (async, tenant-isolated, RLS), Supabase Storage, multi-provider OAuth (Google, Microsoft, Slack), skill-based execution (async tool loops with context weighting), context store (atomic facts + full-text search + entity graph).

**CRM design principles:**
- Company-first, not person-first — B2B engagement is account-level
- View layer over accumulated intelligence — not a database to fill
- No manual data entry forms — accounts, contacts, outreach created by skills and seed commands
- Three distinct jobs: triage (Pipeline), execute (outreach), follow-up (Accounts + Pulse)

**Spec:** `.planning/SPEC-ai-native-crm.md`
**Concept brief:** `.planning/CONCEPT-BRIEF-ai-native-crm.md`

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

---
*Last updated: 2026-03-27 after v2.0 milestone completion*
