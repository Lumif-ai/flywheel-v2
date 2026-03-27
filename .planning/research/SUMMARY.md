# Project Research Summary

**Project:** Flywheel v2.1 — Intelligence-First CRM Redesign
**Domain:** Brownfield CRM migration — multi-type relationships, AI synthesis, configurable pipeline grid
**Researched:** 2026-03-27
**Confidence:** HIGH (stack + architecture verified against codebase; features MEDIUM from industry survey)

## Executive Summary

Flywheel v2.1 adds an intelligence surface layer on top of a functioning v2.0 CRM. The core design decision is a two-paradigm layout: a configurable data grid for pipeline triage (Airtable-style) and intelligence journals for graduated relationships (cards with AI panels, type-driven tabs, commitment tracking). No competitor cleanly separates these two modes — Attio and Folk use uniform record layouts; Airtable feels clinical for investor journals. This separation is the product's conceptual differentiator and must be preserved as a design constraint throughout implementation.

The recommended approach is strictly additive. The existing FastAPI + SQLAlchemy + React + Supabase stack is sound and must not be disrupted. New stack additions are minimal: AG Grid Community for the configurable pipeline grid, Motion for spring animations, react-dropzone for file attachments, pgvector for future embeddings (deferred past MVP), and openai for text-embedding-3-small if and when RAG quality requires it. The AI synthesis layer uses vanilla Python over the existing Anthropic SDK — LangChain and LlamaIndex are explicitly rejected as bloated for this use case.

The biggest risk is the `status` to `pipeline_stage` column rename. This is a brownfield migration with 206 live accounts and existing API code that references `Account.status` on every request. A naive single-phase rename causes a complete API outage during the deploy gap. The mitigation is mandatory: a two-phase migration where the new column is added and data is copied before the old column is ever dropped. The second critical risk is AI synthesis cost runaway — the synthesis endpoint must never auto-trigger on page load, must rate-limit at the DB level, and must return `null` (not call the LLM) when `ai_summary` is NULL. These two risks are architectural, not implementation details, and must be designed in before any code is written.

---

## Key Findings

### Recommended Stack

The existing stack (React 19, Vite, Tailwind v4, shadcn/ui, TanStack Query v5, Zustand, FastAPI, SQLAlchemy 2.0 async, Alembic, Anthropic SDK) requires four targeted additions. Nothing should be replaced.

**New dependencies — frontend:**
- `ag-grid-community` + `ag-grid-react` v35.2.0 — configurable pipeline grid with column resize, reorder, hide, inline editing, and filters; the only community-edition library providing all these without an enterprise license; React 19 compatible since v34.3.0
- `motion` v12 — spring animations and micro-interactions; Framer Motion is now deprecated (`framer-motion` package abandoned); import from `motion/react` exclusively
- `react-dropzone` — headless file drop zone hook; integrates with existing Supabase Storage and FastAPI `/files/upload` endpoint without new upload infrastructure

**New dependencies — backend:**
- `pgvector>=0.4.2` — vector storage in Supabase PostgreSQL; sufficient for CRM scale (<100k documents per tenant); integrates with SQLAlchemy 2.0 async via `Vector` type; avoids separate vector DB infrastructure
- `openai>=1.0` — embeddings only (`text-embedding-3-small`); Anthropic SDK does not provide embeddings; needed only if full-text search proves insufficient for Q&A retrieval (deferred to post-MVP)

**Explicitly rejected:** LangChain (bloated, conflicts with existing Anthropic SDK), LlamaIndex (overkill for per-relationship summaries), Pinecone/Qdrant (unnecessary infrastructure at CRM scale), `framer-motion` (deprecated).

See `.planning/research/STACK.md` for full rationale and version verification.

### Expected Features

The feature landscape divides into three tiers. The table stakes are non-negotiable for the product to feel complete. The differentiators are what justify adoption over Attio or Folk. The anti-features are explicitly out of scope and must not be built.

**Must have (table stakes):**
- Separate list pages per relationship type (Prospects, Customers, Advisors, Investors) — every CRM since Salesforce segments by type; founders cannot manage advisors and prospects in a single table
- AI summary on relationship detail page (cached, not on-demand) — users expect synthesis; raw timeline is too slow to read
- Graceful degradation when AI summary is empty — never show a blank panel; return template string when context entries < 3
- Configurable Pipeline columns (show/hide) — any power user of CRMs expects Airtable-style column management
- Signal count badges on sidebar — users need ambient awareness of where attention is needed
- Graduation flow with type selection modal — the explicit promotion action from prospect to relationship
- Commitments tab (What You Owe / What They Owe) — the primary founder cognitive burden after a meeting that no existing tool addresses

**Should have (differentiators):**
- Multi-type account (one entity = Advisor + Investor simultaneously) — Attio's primary differentiator for startup use cases; no other lightweight CRM does this cleanly
- Interactive AI panel with Q&A about a relationship — RAG over account context; Folk offers draft-from-thread but not open Q&A
- Type-specific tab sets per relationship (Advisor tabs differ from Investor tabs differ from Prospect tabs) — Attio and Folk use uniform layouts for all types
- Stale relationship detection with ambient visual tint — glanceable staleness signals rather than disruptive notifications
- File attachment on relationship (investor deck to investor record, NDA to customer record) — neither Attio nor Folk have this natively; Supabase Storage already exists

**Defer to patch/v2.2:**
- File attachments (API-06) — note capture delivers higher value per effort; files add storage wiring that should not block main surfaces
- Full signal taxonomy beyond `stale_relationship` — `reply_received` and `commitment_due` require richer event wiring
- Column drag-to-reorder — show/hide is sufficient for v2.1; reorder is polish
- Action bar skill triggers — stubs with "Coming soon" toasts acceptable in v2.1

**Anti-features (do not build):**
- Custom pipeline stages, kanban drag-and-drop, bulk outreach sending, NLP auto-extraction of commitments from freeform notes, free-text contact creation from UI, mobile-responsive layout, Slack/email notification delivery — all explicitly out of scope per PROJECT.md

See `.planning/research/FEATURES.md` for full feature dependency graph and complexity assessment.

### Architecture Approach

The architecture is strictly additive to the existing system. Every new capability integrates into existing infrastructure (FastAPI router pattern, SQLAlchemy models, React Query + Zustand state management, Supabase Realtime) rather than introducing parallel systems. Three schema additions power the feature: `account_syntheses` table, `relationship_types` array column on accounts, and `account_id` FK on uploaded_files. All follow established Alembic migration patterns. The AI synthesis engine is a new service module (`services/synthesis_engine.py`) that hooks into two existing write paths to invalidate its cache automatically.

**Major components:**
1. **SynthesisEngine** (`services/synthesis_engine.py`) — generates, caches (24h TTL), and invalidates account summaries; hooks into `storage.append_entry()` and outreach status writes; uses Haiku-4-5 at ~300 token budget per synthesis
2. **AccountQA endpoint** (`POST /accounts/{id}/ask`) — RAG Q&A using existing full-text search on `context_entries` (TSVECTOR already indexed); vanilla Python + Anthropic SDK; no orchestration framework needed
3. **GridView** (`features/accounts/components/GridView.tsx`) — TanStack Table v8 wrapper or AG Grid wrapper with column state persisted to localStorage; Zustand store for in-memory column state between navigations
4. **Signal computation** — stays real-time SQL on GET /pulse for v2.1 at 206 accounts; background job pre-computation deferred until >1,000 accounts or push notifications are needed
5. **Multi-type relationship model** — `accounts.relationship_types text[]` with GIN index; partition predicate between Pipeline (un-graduated) and Relationships (graduated) defined once and enforced in both endpoints

**Key patterns:**
- Synthesis is never auto-triggered on page load — NULL summary returns NULL, not an LLM call
- Two-phase migration for `status` to `pipeline_stage` rename — additive first, cleanup after stable deploy
- Query key factory in `queryKeys.ts` — graduation invalidates pipeline + relationships + signals simultaneously
- `fromType` URL parameter drives tab config and back-link on the shared relationship detail page

See `.planning/research/ARCHITECTURE.md` for component boundary tables, data flow diagrams, and suggested build order.

### Critical Pitfalls

1. **Atomic column rename causes API outage** — Never rename `status` to `pipeline_stage` in a single migration. Use two phases: add `pipeline_stage`, copy data, deploy code that reads from `pipeline_stage`, then drop `status` in a follow-up migration. A single-phase rename causes a complete API outage during the deploy gap for all CRM endpoints.

2. **AI synthesis cost runaway** — NULL `ai_summary` must return NULL, not trigger an LLM call. Synthesis must be explicit (user action or background job trigger), never from a `useEffect` or query lifecycle hook. Rate limit at the DB level (`synthesis_requested_at`; return 429 within 5 minutes). Context under 3 meaningful entries gets a template string, not an LLM call.

3. **Missing GIN index on relationship_types array** — Without a GIN index, `WHERE 'advisor' = ANY(relationship_types)` is a full table scan. At 206 rows it is invisible; at 5,000 rows it is visibly slow. The GIN index must ship in the same migration that adds the column — not as a follow-up optimization.

4. **Account leaks across Pipeline and Relationships surfaces** — After graduation, an account can appear in both surfaces if the partition predicate is not precisely defined. Define the predicate once; add `graduated_at` timestamp as the cleanest partition signal. Test both endpoints after every graduation.

5. **React Query key collision after graduation** — The graduation mutation must invalidate `['pipeline']`, `['relationships']` (all type variants), and `['signals']` simultaneously. Use a query key factory; invalidate with `exact: false` for the relationships key.

---

## Implications for Roadmap

Based on combined research, the build order is dictated by three rules: (1) schema migrations before service or API code, (2) backend before frontend, (3) independent features before integrated features. The suggested phase structure below respects all feature dependency constraints from FEATURES.md and the pitfall mitigation requirements from PITFALLS.md.

### Phase 1: Data Model Foundation

**Rationale:** Every other feature blocks on the schema. The column rename, new columns, and new table must be stable before any API code is written. This is also where the two most critical pitfalls are addressed — the atomic rename risk and the missing GIN index.
**Delivers:** `pipeline_stage` column via two-phase migration, `relationship_types text[]` with GIN index, `account_syntheses` table, `entity_level` column, `primary_contact_id` FK on accounts, `account_id` FK on uploaded_files, ORM model updates for all changes
**Addresses:** DM-01 through DM-04 from FEATURES.md (all data model work)
**Avoids:** Pitfall 1 (atomic rename outage), Pitfall 2 (missing GIN index), Pitfall 4 (self-contact trap on person-level accounts)
**Research flag:** Standard Alembic patterns — skip research-phase. Use the two-phase migration template documented in PITFALLS.md.

### Phase 2: Relationship and Signals APIs

**Rationale:** Backend API contracts must be stable before any frontend component is built. This phase also defines the partition predicate that prevents accounts leaking across surfaces (Pitfall 3) and enforces the synthesis rate limiting that prevents cost runaway (Pitfall 5).
**Delivers:** `GET /relationships/?type=` (filtered by type, tenant-scoped), `PATCH /accounts/{id}` with relationship_types, `GET /relationships/{id}` with synthesis + files, `POST /relationships/{id}/synthesize` (explicit trigger only, rate-limited), `POST /relationships/{id}/ask` (Q&A), signals count endpoint, graduation endpoint with type assignment and self-contact creation
**Uses:** FastAPI router pattern (existing), SynthesisEngine service (new), full-text search on context_entries (existing TSVECTOR)
**Avoids:** Pitfall 3 (dual-surface account appearance), Pitfall 5 (synthesis cost runaway), Pitfall 13 (RLS bypass on signals)
**Research flag:** Standard FastAPI patterns — skip research-phase. Synthesis rate limiting and partition predicate require careful implementation review before the endpoints are declared done.

### Phase 3: Pipeline Grid (Frontend)

**Rationale:** The configurable pipeline grid is self-contained and does not depend on relationship surfaces. It can ship independently and unblock founder use of the pipeline before relationship views are complete. The query key factory (Pitfall 7 mitigation) must be established in this phase before any mutation hooks are written.
**Delivers:** AG Grid-based Pipeline page with column show/hide, filter tabs (All / Strong Fit / Needs Follow-up / Stale), stale relationship ambient tint, graduation modal with type selection, localStorage column state persistence
**Uses:** ag-grid-community, motion (entrance animations), query key factory (`queryKeys.ts`)
**Avoids:** Pitfall 7 (React Query key collision), Pitfall 9 (column state lost on navigation), Pitfall 10 (drag/resize conflict)
**Research flag:** AG Grid CSS variable overrides against Tailwind v4 may need a 1-hour implementation spike. Tailwind v4's new Vite-plugin architecture (no config file) has not been tested against AG Grid's class-based theme system. Spike before committing to the theming approach.

### Phase 4: Relationship Surfaces (Frontend)

**Rationale:** After the relationship APIs are stable (Phase 2), the four relationship list pages and the shared detail page can be built. The `fromType` URL parameter pattern must be established before the detail page is built to avoid the multi-type tab/back-link confusion (Pitfall 8).
**Delivers:** Sidebar with 5 sections and signal badge counts (Supabase Realtime), 4 relationship type list pages (card grid), shared RelationshipDetail with type-driven tab configs (Advisor / Investor / Customer / Prospect), AI synthesis panel (read-only display with skeleton on load, never auto-triggered), Commitments tab (two-column What You Owe / What They Owe), Timeline renderer with optimistic note-add
**Uses:** motion (card entrance animations), react-dropzone (file attachment panel), `fromType` URL param routing
**Avoids:** Pitfall 8 (multi-type detail page tab confusion), Pitfall 5 (synthesis auto-trigger on load), Pitfall 14 (stale sidebar badge after in-page action)
**Research flag:** Standard React patterns for type-driven component config maps. The AskPanel conversational UI is the highest-complexity component in the milestone — consider a focused implementation spike before building.

### Phase 5: AI Q&A Panel

**Rationale:** Q&A depends on Phase 2 (the ask endpoint) and Phase 4 (the detail page it lives in). It also benefits from Phase 4's relationship surfaces being stable so the panel has rich account data to query. Q&A is a differentiator, not table stakes — it can slip to v2.2 if Phase 4 is late without blocking the core product.
**Delivers:** AskPanel component with conversational Q&A, source citations showing which context entries informed the answer, question history (local state, not persisted), graceful degradation when context is thin (< 3 entries shows a "not enough context yet" state)
**Uses:** `POST /relationships/{id}/ask` endpoint (Phase 2), existing Anthropic SDK, TSVECTOR full-text retrieval
**Avoids:** Pitfall 5 (cost runaway — same discipline applies to Q&A call volume; never auto-trigger)
**Research flag:** RAG retrieval quality needs validation mid-phase. TSVECTOR full-text search is the MVP strategy, but its adequacy for temporal questions ("what did we discuss last month") against 20-100 context entries per account is MEDIUM confidence. Plan a quality checkpoint at mid-phase; pgvector embeddings are the verified fallback.

### Phase Ordering Rationale

- Schema-first is non-negotiable: the `status` rename affects every existing API endpoint and must be stable before any new code references account fields
- Phase 2 (APIs) before Phases 3 and 4 (frontends): stable API contracts prevent frontend rework when response shapes change
- Phases 3 and 4 can overlap if two engineers are available — Pipeline grid has no dependency on relationship surfaces
- Phase 5 (Q&A) is last because it benefits from rich context data accumulated across other phases, and it can be deferred without blocking the core product

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 3 (Pipeline Grid):** AG Grid CSS variable theming against Tailwind v4 Vite plugin architecture — integration is documented but the combination has not been tested in this codebase. Recommend a 1-hour spike before committing to the theming approach.
- **Phase 5 (AI Q&A):** RAG retrieval quality with TSVECTOR for temporal and conceptual questions — MEDIUM confidence. Plan a quality review checkpoint mid-phase before completing the frontend integration.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Data Model):** Standard Alembic two-phase migration pattern; all SQL is documented in PITFALLS.md
- **Phase 2 (APIs):** Standard FastAPI CRUD patterns; existing codebase has 8 endpoints to reference
- **Phase 4 (Relationship Surfaces):** Standard React Query + Zustand patterns; motion animations follow existing project conventions

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against npm registry and PyPI. AG Grid React 19 compatibility confirmed in changelog. Motion rebranding verified from official blog. pgvector SQLAlchemy integration verified from GitHub. |
| Features | MEDIUM | Table stakes derived from Attio, Folk, HubSpot, Zoho comparison (credible industry sources). Differentiator value claims are practitioner consensus, not quantitative user research. Anti-features verified against PROJECT.md decisions. |
| Architecture | HIGH | Based on direct codebase inspection of models.py, storage.py, skill_executor.py, existing API routers, and migration 027. Integration points are grounded in actual code, not assumptions. |
| Pitfalls | HIGH (backend) / MEDIUM (frontend) | Backend pitfalls (column rename, GIN index, RLS) verified against PostgreSQL docs and actual codebase. Frontend pitfalls (TanStack Table interaction, React Query keys) from official docs and community patterns. |

**Overall confidence:** HIGH for technical approach; MEDIUM for feature prioritization (user value ranking is informed judgment, not user research data)

### Gaps to Address

- **Q&A retrieval quality:** TSVECTOR full-text search adequacy for temporal and conceptual Q&A questions is assumed based on the small context size (20-100 entries per account). Validate with real account data during Phase 5 implementation before committing to the retrieval architecture. pgvector is the verified fallback.
- **AG Grid + Tailwind v4 theming:** Tailwind v4 uses a fundamentally different configuration model (Vite plugin, CSS-first config). AG Grid's theming uses CSS custom properties, which should be compatible, but the interaction with Tailwind v4's build pipeline has not been tested in this codebase. Spike before Phase 3 implementation.
- **Synthesis quality at thin context:** The template-string fallback for accounts with fewer than 3 context entries is the right UX decision, but the threshold of 3 entries is an estimate. Adjust based on early synthesis output quality during Phase 2 API development.
- **Signal computation at scale:** Current real-time SQL computation is adequate at 206 accounts. The scale threshold (>500 accounts triggers background job pre-computation) is documented in ARCHITECTURE.md but the migration path has not been designed. Low urgency for v2.1, but should be addressed before any significant customer onboarding.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `backend/src/flywheel/db/models.py` — Account model, column names, existing indexes
- `backend/src/flywheel/storage.py` — `append_entry()` signature; invalidation hook location
- `backend/src/flywheel/services/skill_executor.py` — Anthropic SDK usage pattern, BYOK context
- `backend/src/flywheel/api/accounts.py`, `outreach.py`, `timeline.py` — existing endpoint patterns, Pydantic models
- `backend/alembic/versions/027_crm_tables.py` — current schema, index definitions
- `frontend/src/features/accounts/` — existing component structure, React Query hooks, TypeScript types

### Primary (HIGH confidence — official documentation)
- [AG Grid React Compatibility](https://www.ag-grid.com/react-data-grid/compatibility/) — React 19 support from v34.3.0
- [Motion Installation Docs](https://motion.dev/docs/react-installation) — v12, import from `motion/react`
- [pgvector Python PyPI](https://pypi.org/project/pgvector/) — v0.4.2, SQLAlchemy 2.0 integration
- [TanStack Table Column Visibility API](https://tanstack.com/table/v8/docs/api/features/column-visibility)
- [PostgreSQL GIN Indexes — pganalyze](https://pganalyze.com/blog/gin-index) — update cost analysis

### Secondary (MEDIUM confidence — industry survey and community patterns)
- [Attio CRM Review 2026 — Authencio](https://www.authencio.com/blog/attio-crm-review-features-pricing-customization-alternatives) — multi-type account differentiator
- [Folk CRM AI Features](https://www.folk.app/articles/folk-crm-ai-features) — AI enrichment patterns, Q&A comparison
- [Zoho CRM Signals Overview](https://help.zoho.com/portal/en/kb/crm/experience-center/salessignals/articles/signals-an-overview) — signal taxonomy reference
- [React Query Cache Invalidation — tkdodo](https://tkdodo.eu/blog/concurrent-optimistic-updates-in-react-query) — query key factory pattern
- [LLM Cost Optimization — Koombea AI](https://ai.koombea.com/blog/llm-cost-optimization) — runaway cost patterns
- [PostgreSQL backward-compatible migration — Ovrsea/Medium](https://medium.com/ovrsea/using-postgresql-views-to-ensure-backwards-compatible-non-breaking-migrations-017288e77f06) — two-phase rename pattern

### Tertiary (MEDIUM confidence — practitioner consensus)
- [LangChain too complex for simple RAG — GitHub discussion #182015](https://github.com/orgs/community/discussions/182015) — community consensus 2025; no single authoritative reference
- [Personal CRM Guide 2025 — folk.app](https://www.folk.app/articles/personal-crm-guide) — stale contact detection patterns
- [4Degrees CRM Features for PE](https://www.4degrees.ai/blog/essential-crm-features-for-private-equity-firms-in-2025-streamline-deal-flow-relationships-and-data-driven-decisions) — founder/VC segmentation best practices

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
