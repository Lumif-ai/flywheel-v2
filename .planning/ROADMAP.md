# Roadmap: Flywheel V2

## Milestones

- ✅ **v1.0 Email Copilot** — Phases 1–6 + patches 48, 49, 49.1 (shipped 2026-03-25)
- ✅ **v2.0 AI-Native CRM** — Phases 50–53 (shipped 2026-03-27)
- ✅ **v2.1 CRM Redesign** — Phases 54–58 (shipped 2026-03-27)
- ✅ **v3.0 Intelligence Flywheel** — Phases 59–63 (shipped 2026-03-28)
- ✅ **v4.0 Flywheel OS** — Phases 64–66.1 (shipped 2026-03-29)
- ✅ **v5.0 Tasks UI** — Phase 67 (shipped 2026-03-29)
- ✅ **v6.0 Email-to-Tasks** — Phase 68 (shipped 2026-03-29)
- 🚧 **v7.0 Email Voice & Intelligence Overhaul** — Phases 69–75 (in progress)

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

<details>
<summary>✅ v2.1 CRM Redesign (Phases 54–58) — SHIPPED 2026-03-27</summary>

- [x] Phase 54: Data Model Foundation (2/2 plans) — completed 2026-03-27
- [x] Phase 55: Relationships and Signals APIs (3/3 plans) — completed 2026-03-27
- [x] Phase 56: Pipeline Grid (3/3 plans) — completed 2026-03-27
- [x] Phase 57: Relationship Surfaces (5/5 plans) — completed 2026-03-27
- [x] Phase 58: Unified Company Intelligence Engine (3/3 plans) — completed 2026-03-27

</details>

---

<details>
<summary>✅ v3.0 Intelligence Flywheel (Phases 59–63) — SHIPPED 2026-03-28</summary>

- [x] Phase 59: Team Privacy Foundation (2/2 plans) — completed 2026-03-28
- [x] Phase 60: Meeting Data Model and Granola Adapter (3/3 plans) — completed 2026-03-28
- [x] Phase 61: Meeting Intelligence Pipeline (3/3 plans) — completed 2026-03-28
- [x] Phase 62: Meeting Surfaces and Relationship Enrichment (3/3 plans) — completed 2026-03-28
- [x] Phase 63: Meeting Prep Loop (3/3 plans) — completed 2026-03-28

</details>

---

<details>
<summary>✅ v4.0 Flywheel OS (Phases 64–66.1) — SHIPPED 2026-03-29</summary>

- [x] Phase 64: Unified Meetings (3/3 plans) — completed 2026-03-28
- [x] Phase 65: Task Intelligence (3/3 plans) — completed 2026-03-28
- [x] Phase 66: /flywheel Ritual Rearchitected (4/4 plans) — completed 2026-03-29
- [x] Phase 66.1: Flywheel Stabilization (3/3 plans) — completed 2026-03-29

</details>

---

<details>
<summary>✅ v5.0 Tasks UI (Phase 67) — SHIPPED 2026-03-29</summary>

- [x] Phase 67: Tasks UI (7/7 plans) — completed 2026-03-29

</details>

---

<details>
<summary>✅ v6.0 Email-to-Tasks (Phase 68) — SHIPPED 2026-03-29</summary>

- [x] Phase 68: Email-to-Tasks Layer A (3/3 plans) — completed 2026-03-29

</details>

---

### v7.0 Email Voice & Intelligence Overhaul (In Progress)

**Milestone Goal:** Transform email from a siloed draft engine into a bidirectional intelligence source that sounds like the user, shares voice across all skills, and feeds relationship/deal/contact intelligence back into the context store. Three tracks: (A) voice profile overhaul, (B) voice as shared context store asset, (C) email as context store source.

---

### Phase 69: Model Configuration Foundation

**Goal:** Every email engine reads its LLM model from a configurable setting rather than hardcoded constants. This is the foundation that all subsequent voice and extraction work builds on — switching from Haiku to Sonnet must be a config change, not a code change.

**Depends on:** Phase 68

**Requirements:** MODEL-01, MODEL-02

**Success Criteria** (what must be TRUE):
  1. Calling `_get_engine_model(db, tenant_id, "voice_extraction")` returns the configured model string, or `claude-sonnet-4-6` when no config exists
  2. All 5 email engine files (scorer, voice extraction, voice learning, drafter, context extraction placeholder) use the shared helper — no `_HAIKU_MODEL` or `_SONNET_MODEL` module-level constants remain
  3. Changing the model config for a specific engine takes effect on the next sync cycle without requiring a server restart
  4. An invalid model string in config logs a warning and falls back to the default model — the sync loop does not crash

**Plans:** 1 plan

Plans:
- [x] 69-01-PLAN.md — Shared get_engine_model() helper + migrate all 5 engine files to configurable models ✓

---

### Phase 70: Voice Profile Overhaul

**Goal:** The voice profile captures 10 fields from 50 emails instead of 4 fields from 20, and both initial extraction and incremental learning use Sonnet. Drafts sound noticeably more like the user because the system knows their formality, greeting style, paragraph patterns, and emoji habits — not just tone and sign-off.

**Depends on:** Phase 69

**Requirements:** VOICE-02, VOICE-01, VOICE-03, VOICE-04

**Success Criteria** (what must be TRUE):
  1. After running voice extraction, the `email_voice_profiles` row has all 10 fields populated (4 existing + 6 new: formality_level, greeting_style, question_style, paragraph_pattern, emoji_usage, avg_sentences)
  2. A draft reply for a user whose profile shows `formality_level: "casual"` and `greeting_style: "Hey,"` starts with "Hey" and uses informal language — visibly different from a formal profile's draft
  3. After editing and approving a draft, the incremental voice updater can update any of the 10 fields (not just the original 4) based on what the edit reveals
  4. Existing voice profiles (with only 4 fields) receive column defaults from the migration and continue to work for drafting without re-extraction
  5. Voice extraction analyzes 50 substantive sent emails (up from 20) — verified by checking `samples_analyzed` value on a fresh profile

**Plans:** 3 plans

Plans:
- [x] 70-01-PLAN.md — Alembic migration: 6 new columns on email_voice_profiles with defaults ✓
- [x] 70-02-PLAN.md — Expanded voice extraction (50 samples, 10-field prompt, parser updates) ✓
- [x] 70-03-PLAN.md — Updated draft system prompt using all 10 fields + incremental updater expansion ✓

---

### Phase 71: Voice Settings UI

**Goal:** Users can see what the system learned about their writing voice and make targeted corrections. The Settings page gains a Voice Profile tab that mirrors all 10 fields as read-only descriptive text, with tone and sign-off editable inline. Reset & Relearn provides a trust mechanism.

**Depends on:** Phase 70

**Requirements:** SETTINGS-04, SETTINGS-01, SETTINGS-02, SETTINGS-03

**Success Criteria** (what must be TRUE):
  1. Opening Settings and clicking "Voice Profile" tab shows all 10 learned voice fields as descriptive text with "Learned from N emails" header
  2. User can edit tone and sign_off inline, click Save, and the changes persist — refreshing the page shows the updated values
  3. Clicking "Reset & Relearn" shows a confirmation dialog, then deletes the existing profile and re-extracts from sent emails using the expanded 10-field, 50-sample prompt
  4. When no voice profile exists (new user, pre-Gmail-connect), the tab shows "No voice profile yet. Connect Gmail to get started."
  5. All three API endpoints respond correctly: GET returns profile, PATCH updates tone/sign_off only, POST reset triggers re-extraction

**Plans:** 2 plans

Plans:
- [x] 71-01-PLAN.md — Three API endpoints: GET/PATCH/POST voice-profile (user-scoped) ✓
- [x] 71-02-PLAN.md — VoiceProfileSettings component + Settings tab integration ✓

---

### Phase 72: Draft Enhancements

**Goal:** Users can see exactly how their voice profile influenced each draft and quickly adjust drafts without editing the persistent voice profile. The draft review experience goes from "approve or edit" to "approve, regenerate with quick adjustments, or edit."

**Depends on:** Phase 71

**Requirements:** DRAFT-03, DRAFT-01, DRAFT-02

**Success Criteria** (what must be TRUE):
  1. Each pending draft shows a collapsible "Voice applied" section (collapsed by default) listing tone, greeting style, sign-off, avg_length, and characteristic phrases that influenced the draft
  2. Expanding the "Voice applied" section reveals all 10 voice fields used for that specific draft
  3. Clicking "Regenerate" dropdown shows four quick actions (shorter, longer, more casual, more formal) — selecting one regenerates the draft with a loading spinner and replaces the original body
  4. After regenerating with "More casual," the draft voice annotation shows the overridden values — but visiting Voice Profile settings confirms the persistent profile is unchanged
  5. A custom override option allows the user to type free-form tone instructions for regeneration

**Plans:** 2 plans

Plans:
- [x] 72-01-PLAN.md — POST /email/drafts/{draft_id}/regenerate endpoint + voice snapshot in context_used ✓
- [x] 72-02-PLAN.md — Voice annotation component + Regenerate dropdown on DraftReview ✓

---

### Phase 73: Voice as Context Store Asset

**Goal:** The voice profile is written to `sender-voice.md` in the context store, making it a shared asset that any skill can read. Outreach drafts, social posts, meeting prep summaries — anything that generates text can match the user's voice without re-learning it.

**Depends on:** Phase 72

**Requirements:** CTX-01

**Success Criteria** (what must be TRUE):
  1. After initial voice extraction completes, `sender-voice.md` exists in the context store with all 10 voice fields in standard context entry format
  2. After an incremental voice update (user edits and approves a draft), `sender-voice.md` is updated with the revised profile
  3. Other skills can read `sender-voice.md` via `flywheel_read_context` and get the current voice profile
  4. The file follows standard context store entry format with source, date, confidence, and evidence count

**Plans:** 1 plan

Plans:
- [x] 73-01-PLAN.md — Voice context writer module + hooks into extraction, incremental update, and reset paths ✓

---

### Phase 74: Email Context Extractor and Shared Writer

**Goal:** The system can extract intelligence from email bodies (contacts, topics, deals, relationships, action items) and write it to the context store through a shared writer that handles dedup, evidence counting, and format compliance. This creates the infrastructure for emails to feed the same intelligence loop that meetings already power.

**Depends on:** Phase 73

**Requirements:** CTX-02, CTX-03

**Success Criteria** (what must be TRUE):
  1. `extract_email_context()` processes a priority-3+ email and returns structured data with contacts, topics, deal_signals, relationship_signals, and action_items
  2. The shared context store writer writes to contacts.md, insights.md, and action-items.md using standard entry format — duplicate entries (same source + detail_tag + date) are skipped, not appended
  3. When the same insight is corroborated by a second email, the evidence count on the existing entry increments rather than creating a duplicate
  4. Backend engines call the writer directly (no MCP dependency during sync), while Claude Code skills can invoke the same writer via MCP tool — both paths use identical write/dedup logic
  5. Email bodies are fetched on-demand and discarded after extraction — never stored in the database (PII posture unchanged)

**Plans:** 2 plans

Plans:
- [ ] 74-01-PLAN.md — context_store_writer.py: write_contact, write_insight, write_action_item, write_deal_signal with dedup + evidence
- [ ] 74-02-PLAN.md — email_context_extractor.py: extraction prompt, structured parsing, confidence assignment

---

### Phase 75: Context Extraction Pipeline

**Goal:** Email context extraction is live in production — wired into the gmail sync loop with confidence-based routing, a human review queue for low-confidence extractions, daily caps, and tracking to prevent re-extraction. The context store steadily enriches with every sync cycle.

**Depends on:** Phase 74

**Requirements:** CTX-04, CTX-05

**Success Criteria** (what must be TRUE):
  1. After a gmail sync cycle, priority-3+ emails have `context_extracted_at` set — subsequent sync cycles skip these emails (no re-extraction)
  2. High and medium confidence extractions appear in context store files immediately after sync
  3. Low confidence extractions appear in `email_context_reviews` table with status "pending" — they do NOT auto-write to the context store
  4. Approving a review via `POST /email/context-reviews/{id}/approve` writes the extraction to the context store and sets status to "approved"
  5. Context extraction respects the 200/day per-tenant cap — the 201st eligible email in a day is skipped with a log message

**Plans:** 2 plans

Plans:
- [ ] 75-01-PLAN.md — email_context_reviews table migration + context_extracted_at column + confidence routing logic
- [ ] 75-02-PLAN.md — Sync loop wiring: extract after score, daily cap, review API endpoints (list/approve/reject)

---

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 48 → 49 → 49.1 → 50 → 51 → 52 → 53 → 54 → 55 → 56 → 57 → 58 → 59 → 60 → 61 → 62 → 63 → 64 → 65 → 66 → 66.1 → 67 → 68 → 69 → 70 → 71 → 72 → 73 → 74 → 75

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
| 66.1 Flywheel Stabilization (INSERTED) | v4.0 | 3/3 | ✓ Complete | 2026-03-29 |
| 67. Tasks UI | v5.0 | 7/7 | ✓ Complete | 2026-03-29 |
| 68. Email-to-Tasks (Layer A) | v6.0 | 3/3 | ✓ Complete | 2026-03-29 |
| 69. Model Configuration Foundation | v7.0 | 1/1 | ✓ Complete | 2026-03-30 |
| 70. Voice Profile Overhaul | v7.0 | 3/3 | ✓ Complete | 2026-03-30 |
| 71. Voice Settings UI | v7.0 | 2/2 | ✓ Complete | 2026-03-30 |
| 72. Draft Enhancements | v7.0 | 2/2 | ✓ Complete | 2026-03-30 |
| 73. Voice as Context Store Asset | v7.0 | 1/1 | ✓ Complete | 2026-03-30 |
| 74. Email Context Extractor and Shared Writer | v7.0 | 0/2 | Not started | - |
| 75. Context Extraction Pipeline | v7.0 | 0/2 | Not started | - |

---
*Roadmap created: 2026-03-24*
*v2.0 milestone added: 2026-03-26*
*v2.0 shipped: 2026-03-27*
*v2.1 milestone added: 2026-03-27*
*v2.1 shipped: 2026-03-27*
*v3.0 milestone added: 2026-03-28*
*v4.0 milestone added: 2026-03-28*
*v5.0 milestone added: 2026-03-29*
*v6.0 milestone added: 2026-03-29*
*v7.0 milestone added: 2026-03-29 — Email Voice & Intelligence Overhaul (7 phases, 18 requirements)*
