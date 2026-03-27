# Roadmap: Flywheel V2

## Milestones

- ✅ **v1.0 Email Copilot** — Phases 1–6 + patches 48, 49, 49.1 (shipped 2026-03-25)
- ✅ **v2.0 AI-Native CRM** — Phases 50–53 (shipped 2026-03-27)
- 🚧 **v2.1 CRM Redesign** — Phases 54–57 (in progress)

## Phases

<details>
<summary>✅ v1.0 Email Copilot (Phases 1–6, 48–49.1) — SHIPPED 2026-03-25</summary>

### Phase 1: Data Layer and Gmail Foundation

**Goal:** The database and Gmail read service are in place — the foundation every subsequent phase depends on. OAuth grants for Gmail read are architecturally separate from existing send-only credentials and can never break existing users.

**Depends on:** Nothing (first phase)

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, GMAIL-01, GMAIL-02

**Success Criteria** (what must be TRUE):
  1. Developer can run Alembic migration and confirm four new tables (`emails`, `email_scores`, `email_drafts`, `email_voice_profiles`) exist with RLS policies matching existing table patterns
  2. User can initiate a Gmail read OAuth flow and see a new Integration row with `provider="gmail-read"` in the database — the existing `gmail-send` Integration row is unmodified
  3. `gmail_read.py` can list message headers, fetch body on-demand, and fetch sent messages without touching `google_gmail.py`
  4. No email content appears in any application log at any level (verifiable by triggering a parse error and inspecting output)

**Plans:** 5 plans

Plans:
- [x] 01-01-PLAN.md — DB models and Alembic migration (emails, email_scores, email_drafts, email_voice_profiles with RLS) ✓
- [x] 01-02-PLAN.md — gmail_read.py service and separate gmail-read OAuth flow ✓

---

### Phase 2: Sync Worker and Voice Profile

**Goal:** Gmail is polling every 5 minutes, Email rows are being upserted, and the user's voice profile is populated from their sent mail before the first draft request ever arrives.

**Depends on:** Phase 1

**Requirements:** GMAIL-03, GMAIL-04, GMAIL-05, GMAIL-06, GMAIL-07, GMAIL-08, VOICE-01, VOICE-02, VOICE-03

**Success Criteria** (what must be TRUE):
  1. After connecting Gmail, Email rows appear in the database within 5 minutes, grouped by `gmail_thread_id`
  2. When Gmail `history.list` returns 404 (simulated), the system resets to full sync and recovers all emails — no silent data loss
  3. EmailVoiceProfile row exists for the user after first sync, populated from filtered substantive sent emails (auto-replies and one-liners excluded)
  4. With 5 simultaneous connected users, sync completes without timeout errors (asyncio.gather batch behavior visible in logs)
  5. Email bodies are fetched on-demand (visible in `gmail_read.py` call logs) and not stored in the `emails` table

**Plans:** 5 plans

Plans:
- [x] 02-01-PLAN.md — email_sync_loop() background worker with historyId incremental sync and 404 full-sync fallback ✓
- [x] 02-02-PLAN.md — voice_profile_init() with sent-mail filtering and EmailVoiceProfile persistence ✓

---

### Phase 3: Email Scorer Skill

**Goal:** Every newly synced email has a priority score (1-5), a category, a suggested action, and traceable reasoning with context references — making Flywheel's context store advantage visible for the first time.

**Depends on:** Phase 2

**Requirements:** SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05, SCORE-06, SCORE-07, SCORE-08, SCORE-09

**Success Criteria** (what must be TRUE):
  1. After sync, each email has an EmailScore row with priority 1-5, a category, a suggested action, and a non-empty reasoning string
  2. Scoring reasoning cites specific context references (e.g., "Matched context entry: Series A deal closing") when relevant context exists in the store
  3. An email from a known contact (present in context_entities) scores higher than an identical email from an unknown sender
  4. Thread-level priority reflects the highest unhandled message score in the thread, not a simple average
  5. Re-syncing a thread when a new message arrives produces an updated EmailScore for that message

**Plans:** 5 plans

Plans:
- [x] 03-01-PLAN.md — SKILL.md definition + email_scorer.py Python engine (scoring prompt, context lookups, EmailScore upsert) ✓
- [x] 03-02-PLAN.md — Sync loop integration: score after upsert, daily cap, thread priority helper, skill_executor dispatch ✓

---

### Phase 4: Email Drafter Skill

**Goal:** Emails scored as important have draft replies waiting — written in the user's voice, assembled with relevant context, and never storing the raw email body beyond draft generation.

**Depends on:** Phase 3

**Requirements:** DRAFT-01, DRAFT-02, DRAFT-03, DRAFT-04, DRAFT-05, DRAFT-06, DRAFT-07, DRAFT-08

**Success Criteria** (what must be TRUE):
  1. Emails with priority 3+ have an EmailDraft row within the configurable visibility delay window (immediately for `delay=0`)
  2. Draft body reflects the user's characteristic tone, sign-off style, and typical length drawn from their voice profile
  3. Draft reasoning lists which context entries were assembled for the reply (traceable to specific meetings, deals, or entity notes)
  4. After draft is sent, `EmailDraft.draft_body` is nulled — the full body is not retained
  5. When Gmail API returns 401/403 during on-demand body fetch, the system falls back to snippet and surfaces a structured error (not a silent empty draft)

**Plans:** 5 plans

Plans:
- [x] 04-01-PLAN.md — email_drafter.py engine with voice injection, context assembly, on-demand body fetch, and SKILL.md ✓
- [x] 04-02-PLAN.md — Sync loop drafting integration, REST API (approve/edit/dismiss), gmail-read send_reply, dispatch fix ✓

---

### Phase 5: Review API and Frontend

**Goal:** The user has a working inbox: a prioritized thread list, per-thread scores with reasoning, and one-tap approve/edit/dismiss for drafts. Critical emails surface as in-app alerts before the user even opens the inbox.

**Depends on:** Phase 4

**Requirements:** API-01, API-02, API-03, API-04, API-05, API-06, API-07, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06

**Success Criteria** (what must be TRUE):
  1. User opens the Email page and sees threads sorted by priority tier (critical at top), with score badges and draft-ready indicators visible without opening any thread
  2. User opens a thread and sees individual message scores, full reasoning text, and context references that link to the underlying context entries
  3. User approves a draft and the email is sent via existing dispatch — the draft status updates to "sent" in the UI without a page refresh
  4. User receives an in-app alert for a priority-5 email even when the Email page is not open
  5. Thread list with 500+ emails scrolls without jank (virtual scrolling active, no DOM node bloat)

**Plans:** 4 plans

Plans:
- [x] 05-01-PLAN.md — Backend read API: GET threads, GET thread detail, GET digest, POST manual sync + api.ts put method ✓
- [x] 05-02-PLAN.md — Email inbox frontend: types, Zustand store, React Query hooks, EmailPage with virtualized ThreadList, ThreadDetail sheet, DraftReview ✓
- [x] 05-03-PLAN.md — In-app critical email alerts (Sonner), daily digest view, sidebar nav link ✓
- [x] 05-04-PLAN.md — Gap closure: fix priority filter values, wire thread auto-open from alert, dynamic badge colors, guard standalone API calls ✓

---

### Phase 6: Feedback Flywheel

**Goal:** The system learns from the user's corrections — draft edits improve future voice profile accuracy, and re-scoring keeps thread priorities fresh as conversations evolve.

**Depends on:** Phase 5

**Requirements:** VOICE-04, FEED-01, FEED-02, FEED-03

**Success Criteria** (what must be TRUE):
  1. After the user edits and approves 5 drafts, the voice profile `samples_analyzed` count increases and at least one phrase/pattern field reflects the new signal
  2. When a new message arrives in an existing thread, that thread's priority score updates to reflect the latest message (not locked to original score)
  3. After dismissing several drafts for a sender category, subsequent emails from similar senders score lower (observable over 10+ interactions)

**Plans:** 5 plans

Plans:
- [x] 06-01-PLAN.md — Voice updater engine (diff analysis + Haiku profile merge), dismiss tracker engine, approve endpoint wiring, scorer dismiss injection ✓
- [x] 06-02-PLAN.md — Thread re-scoring verification (FEED-03 docs), config wiring for dismiss parameters ✓

---

### Phase 48: Auth Foundation and Session Resilience (INSERTED)

**Goal:** Auth is solid — tenant resolution works, sessions survive refresh, and no user hits a silent 401 loop.

**Depends on:** Phase 6

**Plans:** 1 plan

Plans:
- [x] 48-01-PLAN.md ✓

---

### Phase 49: Living Company Profile (INSERTED)

**Goal:** The Company Profile document is auto-generated and stays current — no manual effort to maintain the anchor context document.

**Depends on:** Phase 48

**Plans:** 1 plan

Plans:
- [x] 49-01-PLAN.md ✓

---

### Phase 49.1: Web Research Enrichment on Document Upload (INSERTED)

**Goal:** When a document is uploaded, the system auto-enriches related company context with fresh web intelligence.

**Depends on:** Phase 49

**Plans:** 1 plan

Plans:
- [x] 49.1-01-PLAN.md ✓

</details>

---

<details>
<summary>✅ v2.0 AI-Native CRM (Phases 50–53) — SHIPPED 2026-03-27</summary>

- [x] Phase 50: Data Model and Utilities (2/2 plans) — completed 2026-03-26
- [x] Phase 51: Seed CLI (1/1 plan) — completed 2026-03-27
- [x] Phase 52: Backend APIs (3/3 plans) — completed 2026-03-27
- [x] Phase 53: Frontend (3/3 plans) — completed 2026-03-27

</details>

---

### 🚧 v2.1 CRM Redesign — Intelligence-First Relationships (In Progress)

**Milestone Goal:** Replace the flat accounts table with five distinct surfaces (Pipeline grid + Prospects/Customers/Advisors/Investors relationship pages), each with AI synthesis, interactive context panels, premium UI/UX, and a signal layer with badge counts. The product should feel like a $10M intelligence tool, not a database viewer.

---

### Phase 54: Data Model Foundation

**Goal:** The schema evolution is complete and safely deployed — new relationship columns exist with correct indexes, the two-phase status rename is underway with zero API outage, and AI synthesis cache fields are in place. Every subsequent phase builds on a stable schema.

**Depends on:** Phase 53

**Requirements:** DM-01, DM-02, DM-03, DM-04

**Success Criteria** (what must be TRUE):
  1. Developer runs migration and confirms `relationship_type text[]` column exists on accounts with GIN index — `WHERE 'advisor' = ANY(relationship_type)` uses index scan (verifiable via EXPLAIN)
  2. All 206 existing accounts have `relationship_type = '{prospect}'` after migration — no accounts lost or corrupted
  3. `entity_level` column exists with `DEFAULT 'company'` — existing accounts unaffected, no null values present
  4. Phase A of status rename complete: `relationship_status` and `pipeline_stage` columns exist alongside old `status` column, data copied — APIs still read `status` without error
  5. `ai_summary` and `ai_summary_updated_at` columns exist on accounts — detail endpoint returns null summary without triggering any LLM call

**Plans:** 5 plans

Plans:
- [x] 54-01-PLAN.md — Alembic migrations: relationship_type array + GIN index (DM-01), entity_level (DM-02), ai_summary fields (DM-04), ORM model updates ✓
- [x] 54-02-PLAN.md — Two-phase status rename Phase A: add relationship_status + pipeline_stage, copy data from status (DM-03) ✓

---

### Phase 55: Relationships and Signals APIs

**Goal:** The backend API surface is complete — every relationship surface and signal badge has a stable endpoint. The partition predicate preventing accounts from leaking across Pipeline and Relationships surfaces is enforced at the query level. AI synthesis is rate-limited and never auto-triggered.

**Depends on:** Phase 54

**Requirements:** RAPI-01, RAPI-02, RAPI-03, RAPI-04, RAPI-05, RAPI-06, RAPI-07, RAPI-08, SIG-01, SIG-02

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/relationships/?type=advisor` returns only graduated advisor accounts — a prospect account with no `graduated_at` does not appear even if it has `advisor` in `relationship_type`
  2. `POST /api/v1/relationships/{id}/synthesize` called twice within 5 minutes returns 429 on the second call — the LLM is not invoked; called with null `ai_summary` returns cached null, not a new LLM invocation
  3. `POST /api/v1/relationships/{id}/ask` returns an answer with at least one source attribution citing the specific context entry — does not call LLM when account has fewer than 3 context entries
  4. `GET /api/v1/signals/` returns per-type badge counts (prospects/customers/advisors/investors separately) — counts are non-zero when stale accounts or overdue follow-ups exist
  5. `PATCH /api/v1/relationships/{id}/type` rejects an empty type array and rejects unknown type values — minimum-one-type validation enforced at API layer

**Plans:** 3 plans

Plans:
- [x] 55-01-PLAN.md — Relationships router: GET list (filtered + partition predicate), GET detail (contacts + timeline + cached summary), PATCH type, POST graduate ✓
- [x] 55-02-PLAN.md — SynthesisEngine service: generate, cache (24h TTL), rate-limit (5-min DB-level), graceful degradation for sparse data; POST synthesize + POST ask endpoints ✓
- [x] 55-03-PLAN.md — Notes, files, and signals: POST notes (ContextEntry link), POST files (Supabase Storage), GET signals (per-type badge counts + SIG-02 signal taxonomy) ✓

---

### Phase 56: Pipeline Grid

**Goal:** The Pipeline page is a configurable Airtable-style data grid with filters, saved view tabs, and a graduation flow. The design system tokens powering this phase are also established here — shadows, badges, avatars, transitions — so Phase 57 inherits them without rework.

**Depends on:** Phase 55

**Requirements:** DS-01, DS-02, DS-03, DS-04, GRID-01, GRID-02, GRID-03, GRID-04, GRID-05

**Success Criteria** (what must be TRUE):
  1. Design tokens are applied globally — card shadows render without borders, translucent badge opacity-10 style is visible, avatar component renders initials at 32px and 48px, interactive elements transition in 150ms, skeleton shimmer loading states appear on initial grid load
  2. Pipeline grid loads with 8 default columns at 56px row height, columns are resizable and reorderable, column visibility state persists across page navigations (localStorage)
  3. Filter bar narrows the grid in real time — Fit Tier multi-select, Outreach Status multi-select, and text search all reduce visible rows within 300ms debounce; "Stale" saved view tab shows only accounts with >14 days since last action
  4. Stale rows render with warm tint background, new replies float to top with coral accent — both visible without any filter interaction
  5. Clicking "Graduate" on a row opens the type-selection modal, submitting the modal calls the graduate API, the row slides out with animation, and the sidebar badge count for the selected type increments

**Plans:** 3 plans

Plans:
- [x] 56-01-PLAN.md — Design system: token updates (shadows, badges, avatar component, status dots, transitions), skeleton shimmer component, empty state component; emotional register CSS for Pipeline vs Relationships ✓
- [x] 56-02-PLAN.md — AG Grid pipeline page: column definitions (Company+avatar, Contact+title, Email, LinkedIn, Fit Tier badge, Outreach Status dot, Last Action, Days Stale), column resize/reorder/visibility, localStorage state persistence ✓
- [x] 56-03-PLAN.md — Filter bar + saved view tabs + pagination (25/50/100), stale row tint, reply float-to-top, graduation modal with type selection + slide-out animation + sidebar badge increment ✓

---

### Phase 57: Relationship Surfaces

**Goal:** All four relationship surfaces are live — Prospects, Customers, Advisors, and Investors each have a card-grid list page and a shared detail page with type-driven tabs, an AI context panel, and a full action bar. The sidebar shows badge counts. A founder can open any relationship and immediately understand the full state.

**Depends on:** Phase 56

**Requirements:** REL-01, REL-02, REL-03, REL-04, REL-05, REL-06, REL-07, REL-08, REL-09

**Success Criteria** (what must be TRUE):
  1. Sidebar shows RELATIONSHIPS section with Prospects, Customers, Advisors, Investors links — each has a coral badge count reflecting the signal count for that type; Pipeline appears below the four relationship links
  2. Each relationship type list page renders as a card grid (3-col desktop) — cards are sorted by urgency, warm tint background visible; empty state with type-specific illustration and CTA appears when no relationships of that type exist
  3. Clicking a card opens the detail page — left AI panel (320px) shows cached AI summary (or graceful placeholder when null), input accepts both notes (saved as ContextEntry) and Q&A questions (calls ask API); source citations appear with Q&A answers
  4. Detail page tab set is type-driven: Prospects and Customers show an Intelligence tab with labeled data points (Pain, Budget, Competition, Champion, Blocker, Fit Reasoning); Advisors and Investors do not show this tab
  5. Commitments tab shows two-column layout (What You Owe / What They Owe) with overdue entries highlighted; Timeline tab shows annotated entries with icon, direction, contact, and time-ago; People tab shows contact cards with 48px avatars, role badges, and last-contacted date

**Plans:** 5 plans

Plans:
- [ ] 57-01-PLAN.md — Sidebar redesign: RELATIONSHIPS section header, four type links with badge counts (React Query from signals endpoint), Pipeline repositioned below; query key factory (queryKeys.ts) for cross-surface invalidation
- [ ] 57-02-PLAN.md — Relationship list pages: card grid component (3-col/2-col/1-col responsive), type-specific card content, urgency sort, warm tint register, empty states per type
- [ ] 57-03-PLAN.md — Shared RelationshipDetail page: fromType URL param routing, left AI panel + main area layout, header card with avatar + type badges, tab navigation with type-driven config map
- [ ] 57-04-PLAN.md — Detail tabs: Timeline (annotated entries, expandable, paginated), People (contact cards), Intelligence (Prospects/Customers only — labeled data points, editable), Commitments (two-column, overdue highlight), action bar (type-specific buttons with toast stubs)
- [ ] 57-05-PLAN.md — AI context panel: cached summary display, skeleton on load, note capture (ContextEntry POST), Q&A input (ask endpoint), source attribution display, graceful degradation for thin context

---

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 48 → 49 → 49.1 → 50 → 51 → 52 → 53 → 54 → 55 → 56 → 57

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data Layer and Gmail Foundation | v1.0 | 2/2 | ✓ Complete | 2026-03-24 |
| 2. Sync Worker and Voice Profile | v1.0 | 2/2 | ✓ Complete | 2026-03-24 |
| 3. Email Scorer Skill | v1.0 | 2/2 | ✓ Complete | 2026-03-24 |
| 4. Email Drafter Skill | v1.0 | 2/2 | ✓ Complete | 2026-03-24 |
| 5. Review API and Frontend | v1.0 | 4/4 | ✓ Complete | 2026-03-25 |
| 6. Feedback Flywheel | v1.0 | 2/2 | ✓ Complete | 2026-03-25 |
| 48. Auth Foundation and Session Resilience | v1.0 | 1/1 | ✓ Complete | — |
| 49. Living Company Profile | v1.0 | 1/1 | ✓ Complete | — |
| 49.1. Web Research Enrichment on Document Upload | v1.0 | 1/1 | ✓ Complete | — |
| 50. Data Model and Utilities | v2.0 | 2/2 | ✓ Complete | 2026-03-26 |
| 51. Seed CLI | v2.0 | 1/1 | ✓ Complete | 2026-03-27 |
| 52. Backend APIs | v2.0 | 3/3 | ✓ Complete | 2026-03-27 |
| 53. Frontend | v2.0 | 3/3 | ✓ Complete | 2026-03-27 |
| 54. Data Model Foundation | v2.1 | 2/2 | ✓ Complete | 2026-03-27 |
| 55. Relationships and Signals APIs | v2.1 | 3/3 | ✓ Complete | 2026-03-27 |
| 56. Pipeline Grid | v2.1 | 3/3 | ✓ Complete | 2026-03-27 |
| 57. Relationship Surfaces | v2.1 | 0/5 | Not started | — |

---
*Roadmap created: 2026-03-24*
*v2.0 milestone added: 2026-03-26*
*v2.0 shipped: 2026-03-27*
*v2.1 milestone added: 2026-03-27*
