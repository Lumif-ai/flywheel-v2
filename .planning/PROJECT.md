# Flywheel V2

## What This Is

An AI-powered intelligence platform for founders. Founders install Flywheel as an MCP server on Claude Code, get curated skills (meeting prep, sales collateral, outreach, legal review, etc.), and their business intelligence compounds automatically via a context store. Claude Code is the brain — all LLM reasoning runs through the user's Claude Code subscription. Flywheel is the data layer — context store, skill catalog, document library, meeting/task/account data.

## Core Value

Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system.

## Current State

Ten milestones shipped. The platform is functionally complete for single-founder dogfooding with Claude Code as the brain and Flywheel as the data layer. The CRM surface is now a unified pipeline — one table for all companies and people, with saved views, automatic lifecycle management, and full provenance tracking.

**Shipped milestones:**
- **v1.0 Email Copilot** (2026-03-25) — Gmail sync, 5-tier scoring, voice-learned drafts, review UI, feedback loop
- **v2.0 AI-Native CRM** (2026-03-27) — Accounts/Pipeline/Pulse surfaces, REST APIs, seed CLI, auto-graduation
- **v2.1 CRM Redesign** (2026-03-27) — Pipeline grid, 4 relationship surfaces, AI synthesis, signal badges
- **v3.0 Intelligence Flywheel** (2026-03-28) — Team privacy, Granola adapter, meeting intelligence pipeline, prep loop
- **v4.0 Flywheel OS** (2026-03-29) — Unified meetings, task extraction, flywheel ritual engine, stabilization
- **v5.0 Tasks UI** (2026-03-29) — Task triage, focus mode, quick-add, detail panel, briefing widget
- **v6.0 Email-to-Tasks** (2026-03-29) — Email action item extraction, task attribution, sync integration
- **v7.0 Email Voice & Intelligence Overhaul** (2026-03-30) — 10-field voice profiles, voice settings UI, draft regeneration, voice as context store asset, email context extractor, confidence-routed extraction pipeline
- **v8.0 Flywheel Platform Architecture** (2026-04-05) — 10 MCP data primitives, skill catalog seed, feature flags, CLAUDE.md template, leads pipeline frontend
- **v9.0 Unified Pipeline** (2026-04-06) — Unified schema (pipeline_entries + contacts + activities + sources), data migration, full pipeline API, multi-source integration, AG Grid with saved views, side panel + profile, retirement flow

**Codebase:** FastAPI + React, ~60K LOC backend, ~39K LOC frontend, ~800K LOC MCP CLI

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
- ✓ Tasks UI (triage, focus mode, quick-add, detail panel, briefing widget) — v5.0 Phase 67
- ✓ Email-to-tasks extraction — v6.0 Phase 68
- ✓ Configurable model per email engine (default Sonnet) — v7.0 Phase 69
- ✓ Richer voice extraction (50 samples, 10 fields, Sonnet) — v7.0 Phase 70
- ✓ Expanded EmailVoiceProfile schema (6 new columns) — v7.0 Phase 70
- ✓ Updated draft system prompt using all 10 voice fields — v7.0 Phase 70
- ✓ Incremental voice learning with Sonnet + expanded fields — v7.0 Phase 70
- ✓ Voice Profile settings page (read-mostly mirror card) — v7.0 Phase 71
- ✓ Voice influence annotations on drafts — v7.0 Phase 72
- ✓ Manual tone override / regenerate per draft — v7.0 Phase 72
- ✓ Voice profile written to context store (sender-voice.md) — v7.0 Phase 73
- ✓ Shared context store writer (direct I/O + MCP wrapper) — v7.0 Phase 74
- ✓ Email context extractor engine (contacts, topics, deals, relationships, action items) — v7.0 Phase 74
- ✓ Confidence-based routing with human review queue — v7.0 Phase 75
- ✓ Email extraction wired into gmail sync loop (200/day cap, 10/cycle) — v7.0 Phase 75

- ✓ 10 MCP data primitives on existing flywheel MCP server — v8.0 Phase 78-79
- ✓ GET /api/v1/skills/{name}/prompt endpoint (skill prompt access) — v8.0 Phase 76
- ✓ PATCH /api/v1/meetings/{id} endpoint (meeting summary write-back) — v8.0 Phase 76
- ✓ Markdown → HTML renderer for skill_run output — v8.0 Phase 76
- ✓ 20 founder-facing skills seeded with triggers, tags, contracts — v8.0 Phase 77
- ✓ Frontend feature flags (email=false, tasks=false) — v8.0 Phase 80
- ✓ CLAUDE.md integration rules template — v8.0 Phase 81

- ✓ Unified pipeline schema (pipeline_entries + contacts + activities + pipeline_entry_sources) — v9.0 Phase 83
- ✓ ORM models for unified pipeline tables — v9.0 Phase 83
- ✓ Data migration from leads + accounts with dedup and UUID preservation — v9.0 Phase 84
- ✓ FK retargeting (meetings, tasks, context_entries → pipeline_entries) — v9.0 Phase 84
- ✓ Legacy table rename (*_legacy) with count verification — v9.0 Phase 84
- ✓ Pipeline CRUD API with dedup check, search, timeline — v9.0 Phase 85
- ✓ Legacy leads/accounts endpoint wrappers — v9.0 Phase 85
- ✓ Multi-source auto-creation (meetings, emails, GTM, manual) with provenance — v9.0 Phase 86
- ✓ AG Grid pipeline with inline editing, stage pills, fit tier, filters, keyboard nav — v9.0 Phase 87
- ✓ 7-section side panel (header, AI summary, insights, outreach, tasks, contacts, timeline) — v9.0 Phase 88
- ✓ Full profile page with scroll restoration on back-navigation — v9.0 Phase 88
- ✓ Saved views (JSONB filter/sort/columns persistence) — v9.0 Phase 89
- ✓ Unified MCP pipeline tools + deprecated lead wrappers — v9.0 Phase 89
- ✓ Sidebar restructure (single Pipeline section with built-in filters + saved views) — v9.0 Phase 89
- ✓ Legacy route redirects + graduation removal — v9.0 Phase 89
- ✓ Retirement scanner (60d stale, 90d retire, clear-on-activity) — v9.0 Phase 90
- ✓ Manual retire/reactivate with visual stale/retired indicators — v9.0 Phase 90

### Active

(No active requirements — next milestone not yet planned)

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
- `.planning/SPEC-flywheel-os.md` (v4.0)
- `.planning/SPEC-email-voice-intelligence.md` (v7.0 — shipped, 17 requirements across 3 tracks)
- `.planning/SPEC-flywheel-platform-architecture.md` (v8.0 — 10 MCP tools, 2 endpoints, feature flags, skill catalog)
**Concept briefs:**
- `.planning/CONCEPT-BRIEF-ai-native-crm.md` (v2.0)
- `.planning/CONCEPT-BRIEF-crm-redesign.md` (v2.1)
- `.planning/CONCEPT-BRIEF-flywheel-os.md` (v4.0 — 4-round brainstorm, 14 advisors)
- `.planning/CONCEPT-BRIEF-email-voice-intelligence.md` (v7.0 — 4-round brainstorm, 15 advisors)
- `.planning/CONCEPT-BRIEF-flywheel-platform-architecture.md` (v8.0 — 4-round brainstorm, 14 advisors)

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
| Pipeline separate from Accounts | Different JTBD: triage/execute vs nurture/track | ✓ Merged in v9.0 — unified pipeline_entries table |
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

| Voice profile as context store asset | Cross-skill voice consistency, switching cost moat | ✓ Good |
| Source-specific extractors + shared writer | Emails/meetings are different inputs, context store is shared brain | ✓ Good |
| Sonnet default everywhere | User pays via Claude Code subscription, cost is user-controlled | ✓ Good |
| Configurable models per engine | Power-user escape hatch, not business necessity | ✓ Good |
| Read-mostly voice settings | Mirror not mixing console — trust mechanism with light control | ✓ Good |
| Priority >= 3 guard rail for context extraction | Low-priority emails are noise, would poison context store | ✓ Good |
| Human review queue for low-confidence | Email is lower-signal than meetings, needs quality gate | ✓ Good |
| 200/day extraction cap hardcoded | YAGNI per-tenant config; easy to make configurable later | ✓ Good |
| 10/cycle batch limit | Prevents LLM timeout within 60s sync budget | ✓ Good |
| Approve upgrades confidence to medium | Human validation implies correctness; entry_date from original email | ✓ Good |

| Unified pipeline over leads+accounts+relationships | Double graduation UX is confusing; one table, one view, one stage progression | ✓ Good — shipped v9.0, eliminated graduation entirely |
| Person entries always get a contacts row | Uniform querying, outreach sequences target contacts not pipeline entries | ✓ Good — API-layer enforcement in Phase 85 |
| sources as junction table not array | Need provenance tracking (which meeting/email created this entry) | ✓ Good — pipeline_entry_sources with 3-column dedup |
| Context entity bridging via FK | Pipeline is CRM surface, context store is AI knowledge — share identity, not table | ✓ Good — context_entity_id on pipeline_entries |
| Fit tier renamed Strong/Medium/Weak | A/B/C not intuitive for non-technical founders | ✓ Good — shipped in v9.0 grid |

---
*Last updated: 2026-04-06 after v9.0 Unified Pipeline shipped*
