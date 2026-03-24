# Roadmap: Flywheel V2 — Email Copilot

## Overview

The email copilot adds Gmail read sync, context-powered email scoring, voice-learned draft generation, and a review UI on top of Flywheel V2's existing infrastructure. Six phases build strictly in dependency order: data layer and OAuth foundation first, then sync worker and voice extraction, then the scorer skill, then the drafter skill, then the API and frontend, and finally the feedback flywheel. Nothing ships to users until Phase 5; the first five phases create the invisible machinery that makes Phase 5 feel intelligent from day one.

## Milestone: v1.0 — Email Copilot

**Milestone Goal:** Ship a dogfooding-ready email copilot that syncs Gmail, scores emails using context store intelligence, drafts replies in the user's voice, and provides a review UI for approval before any email is sent.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Layer and Gmail Foundation** - DB models, migrations, and separate Gmail read OAuth ✓ (2026-03-24)
- [ ] **Phase 2: Sync Worker and Voice Profile** - Background polling, incremental sync, and voice extraction
- [ ] **Phase 3: Email Scorer Skill** - Context-powered 5-tier scoring via skill executor
- [ ] **Phase 4: Email Drafter Skill** - On-demand draft generation with voice profile injection
- [ ] **Phase 5: Review API and Frontend** - REST endpoints and scored inbox with draft approval UI
- [ ] **Phase 6: Feedback Flywheel** - Edit-to-learn voice updates, re-scoring on thread activity

## Phase Details

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
- [ ] 02-01-PLAN.md — email_sync_loop() background worker with historyId incremental sync and 404 full-sync fallback
- [ ] 02-02-PLAN.md — voice_profile_init() with sent-mail filtering and EmailVoiceProfile persistence

---

### Phase 3: Email Scorer Skill

**Goal:** Every newly synced email has a priority score (1-5), a category, a suggested action, and traceable reasoning with context references — making Flywheel's context store advantage visible for the first time.

**Depends on:** Phase 2

**Requirements:** SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05, SCORE-06, SCORE-07, SCORE-08, SCORE-09

**Research flag:** Needs `/gsd:research-phase` during planning. LLM prompt engineering for multi-signal scoring (sender entity weight vs. urgency keywords vs. thread staleness) is the highest-risk open design question.

**Success Criteria** (what must be TRUE):
  1. After sync, each email has an EmailScore row with priority 1-5, a category, a suggested action, and a non-empty reasoning string
  2. Scoring reasoning cites specific context references (e.g., "Matched context entry: Series A deal closing") when relevant context exists in the store
  3. An email from a known contact (present in context_entities) scores higher than an identical email from an unknown sender
  4. Thread-level priority reflects the highest unhandled message score in the thread, not a simple average
  5. Re-syncing a thread when a new message arrives produces an updated EmailScore for that message

**Plans:** TBD

Plans:
- [ ] 03-01: email-scorer skill (SKILL.md, SkillDefinition seed, scoring prompt with context tool usage)
- [ ] 03-02: Scorer integration: sync worker triggers SkillRun, tenant isolation verification, per-tenant daily cap

---

### Phase 4: Email Drafter Skill

**Goal:** Emails scored as important have draft replies waiting — written in the user's voice, assembled with relevant context, and never storing the raw email body beyond draft generation.

**Depends on:** Phase 3

**Requirements:** DRAFT-01, DRAFT-02, DRAFT-03, DRAFT-04, DRAFT-05, DRAFT-06, DRAFT-07, DRAFT-08

**Research flag:** Needs `/gsd:research-phase` during planning. Context assembly strategy, voice profile injection format, and cold-start draft behavior need deliberate prompt engineering validation before implementation.

**Success Criteria** (what must be TRUE):
  1. Emails with priority 3+ have an EmailDraft row within the configurable visibility delay window (immediately for `delay=0`)
  2. Draft body reflects the user's characteristic tone, sign-off style, and typical length drawn from their voice profile
  3. Draft reasoning lists which context entries were assembled for the reply (traceable to specific meetings, deals, or entity notes)
  4. After draft is sent, `EmailDraft.draft_body` is nulled — the full body is not retained
  5. When Gmail API returns 401/403 during on-demand body fetch, the system falls back to snippet and surfaces a structured error (not a silent empty draft)

**Plans:** TBD

Plans:
- [ ] 04-01: email-drafter skill (SKILL.md, SkillDefinition seed, on-demand body fetch, voice profile injection, context assembly)
- [ ] 04-02: Draft lifecycle: visibility delay, approve/edit/dismiss actions, body nulling on send, structured error handling

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

**Plans:** TBD

Plans:
- [ ] 05-01: api/email.py (GET threads, GET thread detail, POST approve/edit/dismiss, GET digest, POST manual sync)
- [ ] 05-02: EmailPage.tsx, ThreadList.tsx with virtualization, ThreadCard.tsx, DraftReview.tsx, Zustand store and React Query hooks
- [ ] 05-03: In-app alert integration for priority-5 emails, daily digest view

---

### Phase 6: Feedback Flywheel

**Goal:** The system learns from the user's corrections — draft edits improve future voice profile accuracy, and re-scoring keeps thread priorities fresh as conversations evolve.

**Depends on:** Phase 5

**Requirements:** VOICE-04, FEED-01, FEED-02, FEED-03

**Success Criteria** (what must be TRUE):
  1. After the user edits and approves 5 drafts, the voice profile `samples_analyzed` count increases and at least one phrase/pattern field reflects the new signal
  2. When a new message arrives in an existing thread, that thread's priority score updates to reflect the latest message (not locked to original score)
  3. After dismissing several drafts for a sender category, subsequent emails from similar senders score lower (observable over 10+ interactions)

**Plans:** TBD

Plans:
- [ ] 06-01: Edit-to-learn: diff analysis on user_edits, voice profile update (debounced), FEED-01 dismiss signal integration
- [ ] 06-02: Re-scoring trigger on thread update (FEED-03 / SCORE-08 wiring)

---

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Layer and Gmail Foundation | 2/2 | ✓ Complete | 2026-03-24 |
| 2. Sync Worker and Voice Profile | 0/2 | Not started | - |
| 3. Email Scorer Skill | 0/2 | Not started | - |
| 4. Email Drafter Skill | 0/2 | Not started | - |
| 5. Review API and Frontend | 0/3 | Not started | - |
| 6. Feedback Flywheel | 0/2 | Not started | - |

---
*Roadmap created: 2026-03-24*
*Milestone: v1.0 Email Copilot*
