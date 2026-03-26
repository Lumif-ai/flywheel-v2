# Roadmap: Flywheel V2

## Milestones

- ✅ **v1.0 Email Copilot** — Phases 1–6 + patches 48, 49, 49.1 (shipped 2026-03-25)
- 🚧 **v2.0 AI-Native CRM** — Phases 50–53 (in progress)

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

**Plans:** 2 plans

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

**Plans:** 2 plans

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

**Plans:** 2 plans

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

**Plans:** 2 plans

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

**Plans:** 2 plans

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

### 🚧 v2.0 AI-Native CRM (In Progress)

**Milestone Goal:** Founders never lose track of an account again — a single screen with all contacts, timeline, commitments, intel, and next actions, all auto-populated from skill runs.

---

#### Phase 50: Data Model and Utilities

**Goal:** The CRM schema exists in the database and the normalization utility is available — the foundation that the seed CLI, APIs, and automation all depend on.

**Depends on:** Phase 49.1

**Requirements:** DATA-01, DATA-02, UTIL-01

**Success Criteria** (what must be TRUE):
  1. Running `alembic upgrade head` creates `accounts`, `account_contacts`, and `outreach_activities` tables with RLS policies, and adds `account_id` column to `context_entries` — verifiable via `psql \d accounts`
  2. Account, AccountContact, OutreachActivity ORM models can be imported and used in a Python shell session without errors; relationships navigate correctly (account.contacts, account.outreach_activities)
  3. `normalize_company_name("Acme Corp., Inc.")` returns the same value as `normalize_company_name("acme corp")` — collision-free deduplication demonstrable with a handful of known edge cases

**Plans:** 2 plans

Plans:
- [x] 50-01-PLAN.md — Alembic migration (accounts, account_contacts, outreach_activities tables, RLS policies, indexes, account_id FK on context_entries) ✓
- [x] 50-02-PLAN.md — ORM models (Account, AccountContact, OutreachActivity, ContextEntry update) and normalize_company_name utility ✓

---

#### Phase 51: Seed CLI

**Goal:** The CRM tables are populated with real data from the GTM stack files — developers and the product owner can open the Accounts page and see actual companies from day one.

**Depends on:** Phase 50

**Requirements:** DATA-03

**Success Criteria** (what must be TRUE):
  1. Running `python -m flywheel.seed_crm --tenant-id <uuid>` completes without errors and populates Account, AccountContact, and OutreachActivity rows drawn from gtm-leads-master.xlsx, outreach-tracker.csv, scored CSVs, and pipeline-runs.json
  2. Running the seed command a second time produces no duplicate rows — idempotency is verifiable by comparing row counts before and after the second run
  3. Two company names that differ only by suffix or casing (e.g., "Stripe Inc." and "stripe") resolve to the same Account row (deduplication via normalization utility)

**Plans:** 1 plan

Plans:
- [x] 51-01-PLAN.md — seed-crm CLI command with file parsing, normalization, deduplication, and idempotent upsert for all three tables ✓

---

#### Phase 52: Backend APIs

**Goal:** Every CRM data surface has a REST API — accounts, contacts, outreach, timeline, pipeline, pulse, and graduation automation all respond correctly before any frontend is built.

**Depends on:** Phase 51

**Requirements:** API-01, API-02, API-03, API-04, API-05, AUTO-01

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/accounts/` returns paginated, filterable, searchable, sortable results; `GET /api/v1/accounts/{id}` returns full detail including contacts list and recent timeline entries
  2. `GET /api/v1/accounts/{id}/timeline` returns a chronological feed that interleaves outreach activities, context entries, and documents — each item carries a `type` discriminator field
  3. `GET /api/v1/pulse/` returns a prioritized signal list with at least `reply_received`, `followup_overdue`, and `bump_suggested` signal types populated from seeded data
  4. `GET /api/v1/pipeline/` returns only prospect-stage accounts sorted by fit score; `POST /api/v1/accounts/{id}/graduate` advances the account to engaged and logs a context entry
  5. When an outreach activity is updated to `status="replied"`, the parent account status automatically changes to `engaged` — observable by fetching the account before and after the PATCH

**Plans:** 3 plans

Plans:
- [ ] 52-01-PLAN.md — Accounts and Contacts REST API (list, detail, create, update, graduate endpoint, contacts CRUD)
- [ ] 52-02-PLAN.md — Outreach Activities REST API, Pipeline endpoint, graduation automation (AUTO-01)
- [ ] 52-03-PLAN.md — Account Timeline API (unified chronological feed with type discriminator) and Pulse Signals API

---

#### Phase 53: Frontend

**Goal:** The product is usable — founders can open Accounts, drill into a company, work the Pipeline, and see Pulse signals on their Briefing page without leaving the browser.

**Depends on:** Phase 52

**Requirements:** UI-01, UI-02, UI-03, UI-04, PULSE-01

**Success Criteria** (what must be TRUE):
  1. User navigates to `/accounts` via the sidebar and sees a table of companies with name, status badge, fit score/tier, contact count, last interaction, and next action due — filter, search, sort, and pagination all work
  2. User clicks an account row and lands on `/accounts/{id}` showing the company header, contacts panel on the left, chronological timeline in the center, intel sidebar on the right, and an action bar with Prep/Research/Follow-up buttons
  3. User navigates to `/pipeline` and sees only prospect-stage accounts sorted by fit score with outreach status, days since last action, and a Graduate button — clicking Graduate advances the account and removes it from the Pipeline view
  4. Accounts and Pipeline links appear in the sidebar between Library and Email with Building2 and TrendingUp icons respectively; active route highlights correctly
  5. When the Briefing page is open with Revenue focus active, the top 5 Pulse signals appear as clickable cards that navigate to the relevant account

**Plans:** 3 plans

Plans:
- [ ] 53-01-PLAN.md — Accounts list page (/accounts) with table, filters, search, sort, pagination, and React Query integration
- [ ] 53-02-PLAN.md — Account detail page (/accounts/{id}) with contacts panel, timeline feed, intel sidebar, commitments, and action bar
- [ ] 53-03-PLAN.md — Pipeline page (/pipeline), sidebar navigation links (UI-04), and Pulse feed component on Briefing page (PULSE-01)

---

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 48 → 49 → 49.1 → 50 → 51 → 52 → 53

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
| 52. Backend APIs | v2.0 | 0/3 | Not started | — |
| 53. Frontend | v2.0 | 0/3 | Not started | — |

---
*Roadmap created: 2026-03-24*
*v2.0 milestone added: 2026-03-26*
