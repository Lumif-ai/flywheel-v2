# Concept Brief: Email Copilot

> Generated: 2026-03-24
> Mode: Deep Brainstorm
> Rounds: 3 (First Impressions → Deep Challenges → Synthesis)
> Active Advisors: Bezos, Chesky, PG, Rams, Ive, Hickey, Vogels, Carmack, Torvalds, Helmer, Thompson, Hightower, DJ Patil, Data Governance, Goldratt
> Artifacts Ingested: Flywheel V2 codebase (backend architecture, context store, Gmail OAuth, calendar sync, skill executor, database models)

## Problem Statement

Knowledge workers spend 1-2 hours daily on email triage — scanning, mentally scoring importance, context-switching to projects/meetings/CRM to understand each message, drafting replies, and filing. Existing AI email tools (Superhuman, Shortwave, SaneBox) can prioritize by surface signals (sender frequency, subject keywords) but cannot *act* because they lack the deep context: what happened in your last meeting with this sender, what project this relates to, what your relationship history looks like, or how you typically respond.

The constraint isn't reading speed — it's the cognitive load of mapping each email to your full work context. The user IS the bottleneck. This product automates the bottleneck itself.

**What changed from initial framing:** The original vision was an "AI email assistant." The board sharpened this to: the product is a **context-aware email actor** — not a smarter inbox, but a system that uses your accumulated work knowledge to take email actions on your behalf, with your approval.

## Proposed Approach

Build an Email Copilot skill within Flywheel V2 that:

1. **Syncs Gmail** via expanded OAuth scopes (add `gmail.readonly` + `gmail.modify` to existing `gmail.send`)
2. **Extracts intelligence** from each email (entities, topics, action items, urgency signals) and stores as context entries — discards raw body
3. **Scores every message** by cross-referencing extracted signals against the full context store (meeting notes, company intel, entity relationships, project context)
4. **Drafts replies** for important emails using assembled context + learned voice profile
5. **Presents a review UI** where the user approves, edits, or dismisses drafts
6. **Sends approved replies** via the existing Gmail send infrastructure

The system earns trust progressively: scoring is visible from day 1, drafts are generated from day 1 but surfaced on a configurable delay (`draft_visibility_delay_days: 0` for internal dogfooding, tunable for external users).

**Key insight from the board:** This is NOT an email client. It's the first action-oriented channel for Flywheel's knowledge-compounding engine. Email today, Slack tomorrow, calendar already. The defensible position is "the system that knows everything about your work and acts on it."

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| UX model | Draft approval UI first | Need to earn trust before autonomous action | Chesky (11-star vision) identified morning briefing as north star; Rams argued for trust-first | Morning briefing as MVP — too ambitious before trust is earned |
| Email body storage | Extract context + discard body; fetch on-demand via Gmail API | Clean separation of concerns; 90% of value with 10% of liability | Hickey (decomplecting scoring from drafting); Data Governance (PII minimization) | Store everything — creates unnecessary PII archive |
| Voice learning source | Pull last 200 sent emails, filter to ~100 substantive (>3 sentences) | Enough for pattern extraction; filtering avoids learning from trivial replies | PG (100 is sufficient); Patil (filter for diversity) | 500 sent emails — diminishing returns after ~100 |
| Scoring + drafting | Ship both together | Scoring alone is "yet another priority inbox"; drafting is the step-change | Carmack + Bezos (drafting is the value); overruled Rams (ship scoring alone) | Scoring-only MVP — doesn't differentiate enough |
| Trust ramp | Config-controlled delay on draft visibility | Allows aggressive internal dogfooding while protecting external users | Torvalds (simple integer config, no feature flag framework) | Feature flag system — over-engineered for this |
| Scorer error bias | Aggressive on escalation, conservative on suppression | False negative (missed critical email) is 1000x costlier than false positive | Vogels (asymmetric blast radius); Goldratt (constraint thinking) | Balanced precision/recall — too risky for V1 |
| Sync architecture | Poll every 5 min via background worker | Follows proven calendar_sync pattern; Gmail push is a later optimization | Hightower (progressive complexity); Carmack (boring technology) | Gmail Pub/Sub push notifications — premature optimization |
| Thread handling | Score at message level, display at thread level (highest score wins) | Matches human mental model: "this thread got important when Sarah replied" | Hickey (separate concerns); user confirmed instinct | Thread-level scoring — loses granularity of when importance changed |
| Critical notifications | In-app alerts on platform; Slack DM integration later | Simplest path; no new infrastructure for MVP | Vogels (define the notification channel); user chose platform-first | Push notifications / SMS — requires new infra |
| Data model | Three entities: Email (pointer), EmailScore (intelligence), EmailDraft (action) | Clean, napkin-testable, decomplected | Torvalds (data structures over algorithms); Hickey (separation of concerns) | Single Email model with embedded score/draft — complects everything |

## Advisory Analysis

### Theme 1: Customer Clarity & Demand Validation

**Bezos** confirmed demand via the workaround test: the user already performs this exact workflow manually — scanning emails, cross-referencing with meetings and projects, drafting context-aware replies. The ugly workaround exists. **PG** identified the schlep that keeps competitors away: deep context integration across non-email data sources (meetings, projects, CRM, relationships). This isn't a "build a better inbox" play — it's a schlep that requires the full knowledge graph Flywheel already has. **Goldratt** named the constraint precisely: the user's cognitive load in mapping emails to context. This product automates the bottleneck itself, which is the highest-leverage application of TOC.

### Theme 2: Design Philosophy & UX

**Chesky's** 11-star exercise revealed that the ultimate product isn't an inbox at all — it's a morning briefing from an AI chief of staff. But **Rams** and the user agreed: earn trust first. The MVP is a review UI with scored emails and draft replies. **Ive** contributed the key UX principle: the review experience should feel like approving, not editing. The draft should be good enough that the user's primary action is a single tap to send. **Rams** insisted on honesty: when the system is uncertain about a draft, it should say so rather than presenting a bad draft confidently.

### Theme 3: Data Architecture & Privacy

**Hickey** provided the clean architectural separation: scoring needs extracted signals (metadata + context entries), drafting needs the full body (fetched on-demand from Gmail API), neither needs permanent raw email storage. This decomplects the scoring system from the drafting system and minimizes PII liability. **Data Governance** validated this approach: extracted context entries ("Email from Sarah Chen about Series A, mentions $5M cap, asks for response by Friday") are durable intelligence; raw email bodies are transient input. **Vogels** added the failure design requirement: when Gmail API is unavailable for on-demand fetch, the system must degrade gracefully (show the score and extracted summary, indicate that the full body is temporarily unavailable).

### Theme 4: Strategic Defensibility

**Helmer** identified two achievable powers: **switching costs** (the system learns your voice, scores your contacts, builds reply patterns — switching means retraining from zero) and **cornered resource** (the context store containing meeting notes, company intel, and project knowledge that no email-only competitor can access). Both compound over time. **Thompson** framed the strategic position: Flywheel is building a knowledge aggregator that uses email as an action channel. The defensible position isn't "better email" — it's "the system that knows everything about your work." Email is the first channel; Slack, calendar, and others follow. **Helmer** also noted counter-positioning against Google: Google can't deeply integrate with non-Google tools without undermining their incentive to keep users in the Google ecosystem.

### Theme 5: Technical Pragmatism

**Carmack** identified the actual hard problems in priority order: (1) learning user voice for drafts, (2) scoring accuracy without training data in week 1, (3) not annoying users with bad drafts early. The plumbing (Gmail sync, background workers, API endpoints) is boring technology that follows existing patterns. **Hightower** validated the infrastructure approach: clone the calendar_sync_loop pattern, use managed services, don't build push notification infrastructure for MVP. **Torvalds** demanded the napkin-testable data model (three entities, clean relationships) and boring technology choices throughout.

### Data Product Analysis (DJ Patil)

The email scorer is a data product driving four distinct decisions with different error tolerances:

| Decision | Signal Needed | Error Cost |
|----------|--------------|------------|
| Read now (critical) | Sender importance × topic urgency × time sensitivity | Catastrophic — missed deal, missed legal notice |
| Draft reply (important) | Full context + relationship + topic | Recoverable — wasted time editing bad draft |
| File for later (low priority) | Topic category + rough priority | Minor — slight inconvenience to find later |
| Ignore/archive (noise) | Sender pattern + content type | Moderate — missed email buried in archive |

**Cold-start solution:** The context store already contains meeting notes, company intel, and entity relationships. The scorer can cross-reference sender addresses against context entities from day 1. Voice learning requires ~100 substantive sent emails pulled during initial sync. Scoring accuracy improves over 2-3 weeks as user approvals/dismissals provide feedback.

**Data flywheel:** Every approval, edit, and dismissal teaches the scorer and the drafter. Approved drafts refine voice. Dismissed drafts refine scoring. Edited drafts reveal where context was insufficient. The system compounds knowledge with every interaction.

## Tensions Surfaced

### Tension 1: Ship Scoring Alone vs. Bundle Drafting
- **Rams + Vogels + PG** argue: ship scoring first, lower risk, bad scores are invisible but bad drafts are embarrassing, earn trust before the system "speaks"
- **Carmack + Chesky + Bezos** argue: scoring alone is just another priority inbox, drafting is the step-change value, and draft feedback improves scoring
- **Why both are right:** Scoring is safer; drafting is more valuable
- **User's resolution:** Ship both, but decouple trust via configurable delay on draft visibility
- **User's reasoning:** Internal dogfooding with delay=0 validates both; tunable delay protects external users

### Tension 2: Store Email Bodies vs. Extract and Discard
- **Carmack** argues: store it, encrypt it, add retention policy, don't add complexity for a problem you don't have
- **Data Governance + Hickey** argue: extract context entries, discard body, fetch on-demand — 90% value, 10% liability
- **Why both are right:** Storage is simpler; extraction is cleaner and more privacy-respecting
- **User's resolution:** Extract and discard, fetch on-demand
- **User's reasoning:** Clean separation of concerns; context entries are more useful than raw bodies for scoring anyway

### Unresolved Tensions
- **Voice drift over time**: How often to re-learn voice from sent mail? After every 50 new sent emails? On a schedule? Deferred to implementation.
- **Multi-account support**: Should the system handle multiple Gmail accounts? Deferred to post-MVP.
- **Shared context boundaries**: When team features arrive, which context is shared vs. private for email scoring? Deferred to team feature milestone.

## Moat Assessment

**Achievable powers:** Switching Costs + Cornered Resource
**Moat status:** Emerging — both powers compound with usage

- **Switching costs** grow as the system learns voice patterns, contact importance, topic preferences, and response styles. After 3 months of use, switching to a competitor means losing all learned behavior.
- **Cornered resource** is the context store itself. No email-only tool has access to meeting notes, company intel, project context, and relationship history. This data takes months to accumulate and cannot be exported to a competitor.
- **Counter-positioning** against Google/Microsoft is moderate: they'd have to deeply integrate with non-native tools (your meeting transcripts, your CRM, your project docs) which undermines their ecosystem lock-in strategy.
- **Data flywheel** accelerates both powers: more usage → better scoring → better drafts → more usage → richer context → harder to leave.

## Existing Foundations (What's Already Built)

| Component | Status | File/Location |
|-----------|--------|---------------|
| Gmail OAuth (send-only) | Done — needs scope expansion | `services/google_gmail.py` |
| Integration model (encrypted credentials) | Done | `db/models.py` → Integration |
| Background sync loop pattern | Done | `services/calendar_sync.py` |
| Context store (full-text search + entity graph) | Done | `context_utils.py`, `db/models.py` |
| Skill executor (async LLM tool loop) | Done | `services/skill_executor.py` |
| Email send dispatch | Done | `services/email_dispatch.py` |
| Meeting processor skill (template) | Done | `skills/meeting-processor/` |
| AES-256-GCM encryption | Done | `auth/encryption.py` |
| Tenant isolation (RLS) | Done | All tables |
| Job queue (FOR UPDATE SKIP LOCKED) | Done | `services/job_queue.py` |

## Data Model

```
Email (thin pointer to Gmail)
├── id, tenant_id, user_id
├── gmail_message_id        -- pointer to Gmail API
├── gmail_thread_id         -- for thread grouping
├── sender_email, sender_name
├── subject
├── received_at
├── snippet                 -- Gmail's pre-generated preview (no PII storage)
├── labels[]                -- Gmail labels
├── is_read, is_replied
└── synced_at

EmailScore (the intelligence layer)
├── id, email_id
├── priority (1-5)          -- 5=critical, 1=noise
├── category                -- meeting_followup, deal_related, action_required,
│                              informational, marketing, personal
├── suggested_action        -- notify, draft_reply, file, archive, unsubscribe
├── reasoning               -- LLM explanation for debugging/transparency
├── context_refs[]          -- links to context entries that informed the score
├── sender_entity_id        -- link to context_entities if sender is known
└── scored_at

EmailDraft (the action layer)
├── id, email_id
├── draft_body              -- generated reply text
├── status                  -- pending, visible, approved, sent, dismissed, edited
├── context_used[]          -- which context entries informed the draft
├── user_edits              -- diff of what user changed (for voice learning)
├── visible_after           -- timestamp controlled by draft_visibility_delay_days
└── created_at

EmailVoiceProfile (learned patterns)
├── id, tenant_id, user_id
├── tone                    -- extracted: formal, casual, direct, warm, etc.
├── avg_length              -- typical reply length
├── sign_off                -- "Best," / "Thanks," / just first name / etc.
├── phrases[]               -- characteristic expressions
├── samples_analyzed        -- count of sent emails processed
└── updated_at
```

## Architecture

```
Gmail API (poll every 5 min)
    ↓
email_sync_loop()               ← follows calendar_sync pattern
    ↓
Email table (thin pointers)     ← tenant-isolated, RLS
    ↓
email_scorer skill              ← reads context_entries + context_entities
    ↓                              cross-references sender against entity graph
    ↓                              checks meeting history, project context
    ↓
EmailScore table
    ↓
┌──────────────────────────────────────────────┐
│ Priority 5 (critical)  → in-app alert        │
│ Priority 3-4 (important) → draft reply       │
│   ↓                                          │
│   email_drafter skill                        │
│     ← fetches body on-demand from Gmail API  │
│     ← loads voice profile                    │
│     ← assembles relevant context             │
│     → EmailDraft (visible per delay config)  │
│ Priority 1-2 (low)    → auto-label + digest  │
│ Priority 0 (noise)    → archive              │
└──────────────────────────────────────────────┘
    ↓
Review UI                       ← scored thread list + draft approvals
    ↓
email_dispatch.py               ← send via Gmail (already built)
    ↓
Voice learning                  ← user edits feed back to EmailVoiceProfile
```

## Phased Implementation

### Phase 1: Gmail Read + Sync (Backend plumbing)
- Expand Gmail OAuth scopes (`gmail.readonly`, `gmail.modify`)
- Create Email, EmailScore, EmailDraft, EmailVoiceProfile models + migration
- Build `gmail_read.py` service (list/fetch messages via Gmail API)
- Build `email_sync_loop()` background worker (5-min poll)
- Initial voice profile extraction from ~100 substantive sent emails

### Phase 2: Score + Triage (The intelligence)
- Build `email_scorer` skill using context store
- Implement scoring logic: sender entity lookup, topic matching, urgency signals
- Action routing: notify / draft / file / archive based on score
- Context entry extraction from email metadata + snippet
- In-app alert system for critical emails (priority 5)

### Phase 3: Draft + Review (The value)
- Build `email_drafter` skill with on-demand Gmail body fetch
- Voice profile integration for reply generation
- Draft storage with configurable visibility delay
- Review API endpoints (list scored threads, approve/edit/dismiss drafts)
- Send approved drafts via existing email dispatch

### Phase 4: Frontend Review UI
- Scored thread list (grouped by priority, thread-level display)
- Thread detail view with score reasoning + context references
- Draft review: approve (one tap), edit, dismiss
- Alert indicator for critical emails
- Daily digest view for low-priority batched emails

### Phase 5: Feedback Loop + Polish
- Voice learning from user edits (diff analysis → profile updates)
- Scoring refinement from approve/dismiss patterns
- Re-scoring when thread gets new messages
- Digest generation as document artifact
- Slack DM integration for critical alerts

## Open Questions

- [ ] Voice drift: how often to re-analyze sent mail for voice profile updates?
- [ ] Multi-account Gmail support: needed for users with personal + work accounts?
- [ ] Rate limits: Gmail API has quotas — what's the polling budget per user at scale?
- [ ] Offline/degraded mode: what does the UI show when Gmail API is temporarily unavailable?
- [ ] Thread depth: how far back in a thread should the scorer look for context?
- [ ] Unsubscribe automation: should the system actually hit unsubscribe links, or just suggest?

## Recommendation

**Proceed to /gsd for execution.** The foundations are 70% built. The concept is validated by the board with two achievable powers (switching costs, cornered resource) and a clear data flywheel. The five-phase plan is scoped for incremental value delivery — Phase 1-3 produces a functional dogfooding-ready system, Phase 4 adds the UI, Phase 5 closes the feedback loop.

## Artifacts Referenced

- Flywheel V2 backend codebase: architecture, models, services, integrations
- Existing Gmail OAuth implementation (`services/google_gmail.py`)
- Calendar sync pattern (`services/calendar_sync.py`)
- Context store architecture (`context_utils.py`, `db/models.py`)
- Skill executor (`services/skill_executor.py`)
- Meeting processor skill (template for email processor)
