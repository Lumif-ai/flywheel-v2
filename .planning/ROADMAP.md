# Roadmap: Flywheel V2

## Milestones

- ✅ **v1.0 Email Copilot** — Phases 1–6 + patches 48, 49, 49.1 (shipped 2026-03-25)
- ✅ **v2.0 AI-Native CRM** — Phases 50–53 (shipped 2026-03-27)
- ✅ **v2.1 CRM Redesign** — Phases 54–58 (shipped 2026-03-27)
- ✅ **v3.0 Intelligence Flywheel** — Phases 59–63 (shipped 2026-03-28)
- ✅ **v4.0 Flywheel OS** — Phases 64–66 (shipped 2026-03-28)

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

### ✅ v2.1 CRM Redesign — Intelligence-First Relationships (Shipped 2026-03-27)

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
- [x] 57-01-PLAN.md — Sidebar redesign: RELATIONSHIPS section header, four type links with badge counts (React Query from signals endpoint), Pipeline repositioned below; query key factory (queryKeys.ts) for cross-surface invalidation ✓
- [x] 57-02-PLAN.md — Relationship list pages: card grid component (3-col/2-col/1-col responsive), type-specific card content, urgency sort, warm tint register, empty states per type ✓
- [x] 57-03-PLAN.md — Shared RelationshipDetail page: fromType URL param routing, left AI panel + main area layout, header card with avatar + type badges, tab navigation with type-driven config map ✓
- [x] 57-04-PLAN.md — Detail tabs: Timeline (annotated entries, expandable, paginated), People (contact cards), Intelligence (Prospects/Customers only — labeled data points, editable), Commitments (two-column, overdue highlight), action bar (type-specific buttons with toast stubs) ✓
- [x] 57-05-PLAN.md — AI context panel: cached summary display, skeleton on load, note capture (ContextEntry POST), Q&A input (ask endpoint), source attribution display, graceful degradation for thin context ✓

---

### Phase 58: Unified Company Intelligence Engine

**Goal:** Document uploads and URL crawls flow through a single skill engine with intelligence-driven enrichment. The document upload parallel path is eliminated. Founders can refresh or reset their company profile from the profile page.

**Depends on:** Phase 57

**Success Criteria** (what must be TRUE):
  1. `_execute_company_intel()` accepts both URLs and document text — document text skips crawl, goes straight to structuring
  2. `POST /profile/analyze-document` creates a SkillRun and routes through the existing company-intel engine — no more background enrichment side path
  3. Enrichment prompt reads existing profile entries and focuses research on gaps — not the same 10 generic searches every time
  4. `POST /profile/refresh` re-runs the skill with tenant URL + all linked document content, dedup merges with existing data
  5. `POST /profile/reset` soft-deletes all `company-intel-onboarding` entries, then runs the same refresh flow
  6. Frontend profile page shows Refresh and Reset buttons — both display the existing SSE discovery streaming UI during execution

**Plans:** 3 plans

Plans:
- [x] 58-01-PLAN.md — Engine extension: detect URL vs document text input, skip crawl for documents, gap-aware enrichment prompt that reads existing profile before researching ✓
- [x] 58-02-PLAN.md — Route document uploads through skill engine: POST /profile/analyze-document creates SkillRun, remove background enrichment path; add POST /profile/refresh and POST /profile/reset endpoints ✓
- [x] 58-03-PLAN.md — Frontend: Refresh and Reset buttons on CompanyProfilePage, confirmation modal for reset, SSE streaming reuse from onboarding ✓

---

### ✅ v3.0 Intelligence Flywheel — Conversations Become CRM Intelligence (Shipped 2026-03-28)

**Milestone Goal:** Every conversation source (meetings, emails, Slack) flows through a unified intelligence pipeline that extracts structured insights, auto-links to accounts/contacts, and enriches relationship surfaces. The flywheel loop: Ingest → Enrich → Prepare. User-level privacy ensures raw content stays private while extracted intelligence benefits the whole team.

---

### Phase 59: Team Privacy Foundation

**Goal:** User-level RLS policies enforce that personal data (emails, integrations, calendar, skill runs) is invisible to other team members. This is the security prerequisite for any multi-user or team feature.

**Depends on:** Phase 58

**Requirements:** PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06, PRIV-07

**Success Criteria** (what must be TRUE):
  1. User B in the same tenant calls `GET /email/threads` and gets zero results (not User A's emails)
  2. User B calls `DELETE /integrations/{user_a_id}` and gets 404 Not Found (avoids leaking resource existence)
  3. User B calls `GET /skills/runs` and sees only their own runs
  4. All 7 tables have user-level RLS policies enforced at the database level
  5. Existing single-user functionality is unaffected

**Plans:** 2 plans

Plans:
- [x] 59-01-PLAN.md — Alembic migration: user-level RLS policies on emails, email_scores, email_drafts, email_voice_profiles, integrations, work_items, skill_runs ✓
- [x] 59-02-PLAN.md — API-level ownership guards: email endpoint user_id filters, integration DELETE/sync ownership checks, skill_runs list user scoping ✓

---

### Phase 60: Meeting Data Model and Granola Adapter

**Goal:** The meetings table exists with split-visibility RLS, Granola is connected as an integration with encrypted API key, and meetings can be synced from Granola into the database with dedup. No processing yet — just the data foundation and sync pipeline.

**Depends on:** Phase 59

**Requirements:** MDE-01, MDE-02, GRA-01, GRA-02, GRA-03

**Success Criteria** (what must be TRUE):
  1. `meetings` table exists with tenant-level RLS for metadata, transcript stored in Supabase Storage with user-level access
  2. User can connect Granola via API key in Settings — key is encrypted in Integration table
  3. `POST /meetings/sync` pulls meetings from Granola, dedup by external_id, creates meeting rows with `processing_status='pending'`
  4. Synced meetings show title, date, attendees, provider — no processing yet

**Plans:** 3 plans

Plans:
- [x] 60-01-PLAN.md — Alembic migration: meetings table with split-visibility RLS, ORM model, indexes ✓
- [x] 60-02-PLAN.md — Granola adapter: GranolaAdapter (list_meetings, get_meeting_content, test_connection), Integration flow (API key encrypt/store/validate) ✓
- [x] 60-03-PLAN.md — Sync endpoint: POST /meetings/sync, dedup logic, meeting row creation, auto-filter with processing rules from Integration settings ✓

---

### Phase 61: Meeting Intelligence Pipeline

**Goal:** Synced meetings are automatically processed — classified by type, intelligence extracted across 9 insight types, written to 7 context store files, and auto-linked to accounts and contacts. The extraction step transforms private transcripts into shared team intelligence.

**Depends on:** Phase 60

**Requirements:** MPP-01, MPP-02, MPP-03, MPP-04, MPP-05, AAL-01, AAL-02, AAL-03

**Success Criteria** (what must be TRUE):
  1. `_execute_meeting_processor()` fetches transcript, classifies type (8 types via Haiku), extracts insights (9 types via Sonnet), writes to context store
  2. After processing, meeting row has `summary` JSONB populated with tldr, key_decisions, action_items, and `processing_status='complete'`
  3. Attendee email domains auto-match to existing accounts — `meeting.account_id` is set
  4. Unknown attendee domains auto-create prospect accounts with contacts
  5. Processing rules (skip internal, skip by domain, skip by type) correctly filter meetings to `processing_status='skipped'`
  6. SSE events stream during processing (reuses existing SkillRun event pattern)

**Plans:** 3 plans

Plans:
- [x] 61-01-PLAN.md — Meeting processor engine: 7-stage pipeline (fetch → store → classify → extract → link → write → done), meeting_processor_web.py helpers ✓
- [x] 61-02-PLAN.md — Account auto-linking: domain matching, contact upsert, prospect auto-creation for unknown domains ✓
- [x] 61-03-PLAN.md — Processing rules: skip_internal/skip_domains/skip_types/skip_meetings + batch/list/detail endpoints ✓

---

### Phase 62: Meeting Surfaces and Relationship Enrichment

**Goal:** Meetings have a dedicated page with list/detail views. Processed meetings enrich relationship surfaces — timeline shows meeting entries, intelligence tabs show extracted insights, people tabs show discovered contacts, signal badges reflect meeting activity. The CRM surfaces built in v2.1 now fill with real conversation intelligence.

**Depends on:** Phase 61

**Requirements:** FE-01, FE-02, FE-03, FE-04, RSE-01, RSE-02, RSE-03

**Success Criteria** (what must be TRUE):
  1. Meetings page shows synced meetings with status badges (pending/processing/complete/skipped), sync button triggers Granola pull
  2. Meeting detail shows metadata for all team members, transcript only for the meeting owner (403 for others)
  3. Granola API key connection in Settings page with test/disconnect flow
  4. Relationship timeline tab shows meeting entries with date, type badge, attendees, tldr
  5. Relationship intelligence tab includes pain points, buying signals, competitor mentions extracted from meetings
  6. Sidebar signal badges increment when new meetings are processed for an account

**Plans:** 3 plans

Plans:
- [x] 62-01-PLAN.md — Meetings page: list view with meeting cards, status badges, sync button, processing SSE feedback; meeting detail view with privacy enforcement (transcript owner-only) ✓
- [x] 62-02-PLAN.md — Granola settings: API key input in SettingsPage, connection status indicator, test/disconnect flow, sync controls ✓
- [x] 62-03-PLAN.md — Relationship enrichment: meeting entries in timeline tab, intelligence tab data from meeting context entries, people tab contacts from meeting attendees, signal badge integration ✓

---

### Phase 63: Meeting Prep Loop

**Goal:** The flywheel closes — meeting prep reads the enriched context store and produces intelligence briefings for upcoming meetings. A founder preparing for a call with Acme sees full relationship history, known pain points, open action items, and competitive positioning. The prep makes the meeting more productive, which produces richer intelligence for next time.

**Depends on:** Phase 62

**Requirements:** PREP-01, PREP-02

**Success Criteria** (what must be TRUE):
  1. User can trigger meeting prep from meetings page or relationship page — "Prep for meeting with Acme"
  2. Prep reads context store entries linked to the account (pain points, competitor intel, action items, contacts, timeline)
  3. Briefing is rendered as HTML with structured sections (relationship summary, known pain points, open action items, competitive landscape, suggested questions)
  4. Prep is user-initiated only (no auto-trigger in v1)
  5. Briefing is private to the requesting user (Zone 1)

**Plans:** 2 plans

Plans:
- [x] 63-01-PLAN.md — Meeting prep engine: web-adapted prep skill, context reader (account-scoped entries from 7 files), LLM briefing generation, HTML rendering ✓
- [x] 63-02-PLAN.md — Prep frontend: trigger from meetings page and relationship page, SSE streaming during generation, briefing viewer ✓

---

### 🚧 v4.0 Flywheel OS — Intelligence Operating System for Founders (In Progress)

**Milestone Goal:** Transform the intelligence layer into a founder's daily operating system. Conversations automatically become tracked commitments. Unified meetings timeline (Calendar + Granola), automatic task extraction from transcripts, and a `/flywheel` CLI ritual. The flywheel closes: better prep → richer meetings → more detected tasks → auto-executed deliverables.

---

### Phase 64: Unified Meetings

**Goal:** Google Calendar events and Granola transcripts live in one table with dedup and lifecycle status. The meetings page shows upcoming and past meetings in a unified timeline. Calendar sync writes to the meetings table instead of WorkItems.

**Depends on:** Phase 63

**Requirements:** UNI-01, UNI-02, UNI-03, UNI-04, UNI-05, UNI-06, UNI-08

**Success Criteria** (what must be TRUE):
  1. Calendar sync creates Meeting rows with `processing_status='scheduled'` — no new WorkItems created for calendar events
  2. A meeting that exists in both Google Calendar and Granola appears as ONE row (dedup by time+title+attendees)
  3. Meetings page shows Upcoming and Past tabs, with calendar events in Upcoming and processed meetings in Past
  4. User can trigger prep from a scheduled meeting that has a linked account
  5. `get_meeting_prep_suggestions()` queries the meetings table (not WorkItems)

**Plans:** 3 plans ✓ **COMPLETE** (2026-03-28)

Plans:
- [x] 64-01-PLAN.md — Migration 033 + calendar sync rewrite + Granola fuzzy dedup + lifecycle state machine
- [x] 64-02-PLAN.md — Time-based listing API + meeting prep endpoint + suggestions migration
- [x] 64-03-PLAN.md — Frontend Upcoming/Past tabs + new status values + scheduled meeting prep trigger


---

### Phase 65: Task Intelligence ✅ (completed 2026-03-28)

**Goal:** Meeting transcripts automatically produce task rows. The intelligence pipeline gains a Stage 7 that classifies commitments (yours/theirs/mutual) and maps them to executable skills. A tasks API exposes the full lifecycle. Signal counts reflect pending tasks.

**Depends on:** Phase 64

**Requirements:** TASK-01, TASK-02, TASK-03, TASK-04

**Success Criteria** (what must be TRUE):
  1. After processing a meeting where the founder says "we'll send a one-pager", a Task row exists with `suggested_skill='sales-collateral'` and `trust_level='review'`
  2. After processing a meeting where the other party says "I'll send the requirements", a Task row exists with `commitment_direction='theirs'`
  3. `GET /tasks/` returns detected tasks with full CRUD, status transition validation, and user-scoped privacy
  4. `GET /signals/` includes `tasks_detected`, `tasks_in_review`, `tasks_overdue` counts
  5. All tasks with email-related skills have `trust_level='confirm'` (NEVER auto-send)

**Plans:** 3 plans — all verified (17/17 must-haves passed)

Plans:
- [x] 65-01-PLAN.md — Tasks table migration (20 cols, 3 indexes, user-level RLS), Task ORM model, signal counts extension (tasks_detected, tasks_in_review, tasks_overdue) ✓
- [x] 65-02-PLAN.md — Stage 7 task extraction in meeting processor: Haiku commitment classification, extract_tasks() + write_task_rows() helpers, pipeline insertion ✓
- [x] 65-03-PLAN.md — Tasks CRUD API: 7 endpoints (list, summary, detail, create, update, status transition, delete), status validation, router registration ✓

---

### Phase 66: /flywheel Ritual (Rearchitected)

**Goal:** The flywheel ritual is a backend orchestrator engine — same architecture as meeting-prep and meeting-processor. One MCP invocation syncs meetings from Granola, processes unprocessed recordings into intelligence, prepares briefings for upcoming external meetings, and returns a rich HTML daily brief. Invoked via `flywheel_run_skill("flywheel")` — no separate installation, no env vars, no curl.

**Depends on:** Phase 65

**Requirements:** FLY-01, FLY-02, FLY-03, FLY-04, FLY-05, FLY-06

**Spec:** `.planning/SPEC-flywheel-ritual-rearchitect.md` (reviewed, 14 findings addressed)

**Success Criteria** (what must be TRUE):
  1. `flywheel_run_skill("flywheel")` via MCP creates a SkillRun, job queue dispatches to the dedicated engine, and returns a link to the HTML daily brief in the document library
  2. Engine Stage 1 syncs from Granola using extracted shared `sync_granola_meetings()` function (same dedup logic as POST /meetings/sync)
  3. Engine Stage 2 processes up to 5 unprocessed meetings by calling `_execute_meeting_processor()` directly (function call, not HTTP)
  4. Engine Stage 3 preps up to 3 upcoming external meetings by calling `_execute_meeting_prep()` directly
  5. HTML daily brief contains 5 sections (sync summary, processing summary, prep cards, pending tasks read-only, remaining items) and renders in the document library
  6. All SSE events stream to the parent run's events_log — one run, one stream
  7. SKILL.md has `engine: flywheel_ritual` and `web_tier: 1` frontmatter, seeded to `skill_definitions` table

**Plans:** 4 plans (replanned from spec — includes task execution)

Plans:
- [x] 66-01-PLAN.md — Extract sync logic, replace SKILL.md with engine frontmatter, add dispatch ✓
- [x] 66-02-PLAN.md — Flywheel ritual engine Stages 1-3 (sync, process, prep) ✓
- [x] 66-03-PLAN.md — Stage 4: LLM-powered task execution (context + web search + invoke skills) ✓
- [x] 66-04-PLAN.md — HTML daily brief, MCP update, wiring ✓

---

### Phase 66.1: Flywheel Stabilization (INSERTED)

**Goal:** Fix all 18 issues discovered during Phase 66 end-to-end testing. The flywheel engine code is structurally complete but cannot run successfully due to: (1) env var naming mismatch blocking all Supabase Storage operations, (2) migration 034 FK failure preventing tasks table creation, (3) timezone bugs causing wrong-day prep, (4) title matching false positives, (5) unguarded error paths that crash the engine, and (6) architecture issues creating fragility under load.

**Depends on:** Phase 66

**Success Criteria** (what must be TRUE):
  1. `flywheel_run_skill("flywheel")` completes all 5 stages without crashing — sync, process, prep, execute, compose — and returns an HTML daily brief
  2. Meeting processing successfully uploads transcripts to Supabase Storage (env var naming fixed)
  3. `alembic upgrade head` succeeds — migrations 033 and 034 both apply cleanly
  4. Stage 3 preps the correct day's meetings regardless of server timezone
  5. Stage 4 gracefully handles missing tasks table, None user_id, and DB errors
  6. `_compose_daily_brief()` never crashes the engine — all render helpers tolerate None/empty inputs
  7. `_filter_unprepped()` uses a single batch query (no N+1)
  8. Meeting processing has a configurable cap to prevent runaway execution

**Plans:** 3 plans

Plans:
- [ ] 66.1-01-PLAN.md — Infrastructure & Migrations: env var fix, migration 034 rewrite, migration chain, updated_at triggers
- [ ] 66.1-02-PLAN.md — Engine Correctness: timezone fix, title matching, user_id None guards, compose guard, N+1 fix, model constant, HTTPException cleanup
- [ ] 66.1-03-PLAN.md — Robustness & Architecture: append_event_atomic guard, execution caps, race condition guard, private import cleanup, SKILL.md engine field, MCP timeout

---

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 48 → 49 → 49.1 → 50 → 51 → 52 → 53 → 54 → 55 → 56 → 57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65 → 66 → 66.1

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
| 57. Relationship Surfaces | v2.1 | 5/5 | ✓ Complete | 2026-03-27 |
| 58. Unified Company Intelligence Engine | v2.1 | 3/3 | ✓ Complete | 2026-03-27 |
| 59. Team Privacy Foundation | v3.0 | 2/2 | ✓ Complete | 2026-03-28 |
| 60. Meeting Data Model and Granola Adapter | v3.0 | 3/3 | ✓ Complete | 2026-03-28 |
| 61. Meeting Intelligence Pipeline | v3.0 | 3/3 | ✓ Complete | 2026-03-28 |
| 62. Meeting Surfaces and Relationship Enrichment | v3.0 | 3/3 | ✓ Complete | 2026-03-28 |
| 63. Meeting Prep Loop | v3.0 | 2/2 | ✓ Complete | 2026-03-28 |
| 64. Unified Meetings | v4.0 | 3/3 | ✓ Complete | 2026-03-28 |
| 65. Task Intelligence | v4.0 | 3/3 | ✓ Complete | 2026-03-28 |
| 66. /flywheel Ritual (Rearchitected) | v4.0 | 4/4 | ✓ Complete | 2026-03-29 |
| 66.1 Flywheel Stabilization (INSERTED) | v4.0 | 0/3 | ○ Pending | — |

---
*Roadmap created: 2026-03-24*
*v2.0 milestone added: 2026-03-26*
*v2.0 shipped: 2026-03-27*
*v2.1 milestone added: 2026-03-27*
*v2.1 shipped: 2026-03-27*
*v3.0 milestone added: 2026-03-28*
*v4.0 milestone added: 2026-03-28*
