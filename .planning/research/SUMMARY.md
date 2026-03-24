# Project Research Summary

**Project:** Flywheel V2 — Email Copilot
**Domain:** AI-powered email triage, scoring, and draft reply generation integrated into multi-tenant SaaS
**Researched:** 2026-03-24
**Confidence:** HIGH

## Executive Summary

The Flywheel Email Copilot is an AI email triage and drafting layer built on top of the existing Flywheel V2 platform. Unlike standalone competitors (Superhuman, Shortwave, SaneBox, Ellie AI), Flywheel's moat is the context store: meeting notes, entity relationships, and project intelligence already present before the first email is synced. Every competitor scores emails on surface signals alone (sender domain, keyword matching). Flywheel can score an email with the knowledge that Sarah Chen is the lead partner on the Series A, that the thread references a deal closing Friday, and that the sender has had 3 meetings with the user in the past month. This is a categorically different product. The research strongly supports building the context-powered scorer and drafter as the core differentiators from day one — not as post-MVP additions.

The recommended approach follows existing Flywheel patterns wherever possible: clone `calendar_sync.py` for the email sync worker, route scoring and drafting through the existing `skill_executor.py` job queue, and reuse `email_dispatch.py` for draft sends. This minimizes new code surface and keeps infrastructure changes small — only 4 new DB tables, 1 new backend service, 2 new skills, and 2 new frontend dependencies. The build order is strictly dependency-constrained: data layer first, Gmail read service second, sync worker third, scorer fourth, drafter fifth, REST API sixth, and review UI last. Attempting to build out of this order will block teams.

The top risks are concentrated in the first two phases. OAuth scope expansion is a critical architectural decision that must be made correctly before any code is written: the existing `gmail.send` scope must never be modified, and the email read capability must be a completely separate OAuth grant stored as `provider="gmail-read"`. The Gmail `historyId` sync watermark must have a full-sync fallback on 404 from day one — adding it later requires state migration across all connected integrations. Voice profile extraction from sent mail must filter out auto-replies and one-liners before the first draft is ever generated; a poisoned voice profile on first use destroys user trust permanently and recovery is difficult. Build the safety mechanisms into the foundations, not as hardening passes.

---

## Key Findings

### Recommended Stack

The project requires remarkably few new dependencies. The Flywheel V2 backend already has `google-api-python-client`, `anthropic`, `beautifulsoup4`, `html2text`, `cryptography`, and the full async SQLAlchemy + FastAPI stack. The frontend already has `@tanstack/react-query`, `zustand`, `dompurify`, `tailwindcss`, and `shadcn`. Only three new packages are needed across the entire feature.

**Core new dependencies:**
- `markdownify` (Python): HTML email body to clean markdown for LLM context — better than `html2text` for email HTML with nested blockquotes and forwarded-message trees
- `@tanstack/react-virtual` (npm): Virtualized thread list — required for users with 1,000+ emails, same TanStack family as react-query (no version conflicts)
- `@tailwindcss/typography` (npm dev): `prose` class for rendering sanitized email HTML bodies — verify Tailwind v4 plugin compatibility during Phase 4 setup

**What NOT to add:** `spacy`/`nltk`/`transformers` (heavyweight; Claude already installed and better for style understanding), `aiogoogle` (problem already solved by `asyncio.to_thread`), `react-quill`/`draft-js` (overkill; plain textarea is correct), raw MIME libraries (Gmail API returns structured JSON, not raw IMAP).

**Gmail API scope change required:** Current `google_gmail.py` grants `gmail.send` only. Email Copilot requires `gmail.readonly` + `gmail.modify` as a separate OAuth grant, stored as a separate Integration row (`provider="gmail-read"`). This is architectural, not just a config change.

See `STACK.md` for full dependency table and version compatibility notes.

### Expected Features

The feature landscape is well-researched across 5 competitors. No competitor accesses external context. That gap is Flywheel's entire value proposition and must be present in v1, not deferred.

**Must have (table stakes — without these the product feels half-baked):**
- Gmail inbox sync via 5-minute background poll
- Voice profile extraction from last ~100 substantive sent emails (cold start before first draft)
- Email scoring (5-tier) with context store cross-reference — this is the differentiator
- Score reasoning with context references ("Scored 5/5 because: Sarah Chen is a known deal contact, matched 3 context entries")
- Draft generation using voice profile + context-assembled reply
- Configurable draft visibility delay (`draft_visibility_delay_days`) — 0 for dogfood, 3–7 for cautious rollouts
- Draft review UI: approve / edit / dismiss with scored thread list
- In-app alerts for priority 5 (critical) emails only

**Should have after v1 validation (v1.x):**
- Feedback flywheel: edit diffs feed back into voice profile
- Re-scoring when thread receives new message
- Daily digest document artifact for low-priority (1-2) emails
- Unsubscribe suggestion in review UI

**Defer to v2+:**
- Gmail Pub/Sub push notifications (only if polling latency generates user complaints)
- Morning briefing / autonomous agent mode (requires months of proven scoring accuracy)
- Multi-account Gmail support
- Slack DM notifications for critical emails
- Auto-labeling (opt-in)

**Hard anti-features (never ship):** Auto-send approved drafts, full email body storage in DB, auto-clicking unsubscribe links.

See `FEATURES.md` for full competitor matrix and feature dependency graph.

### Architecture Approach

The architecture fits entirely within existing Flywheel patterns. Four new DB tables (`emails`, `email_scores`, `email_drafts`, `email_voice_profiles`) power the feature. A new `email_sync_loop()` background worker (modeled exactly on `calendar_sync_loop()`) polls Gmail every 5 minutes and creates `SkillRun` rows for the scorer. The scorer and drafter run through the existing `skill_executor.py` job queue — they are standard skills. The review UI is a new `EmailPage.tsx` with three sub-components. There is no new infrastructure.

**Major components:**
1. `gmail_read.py` — list messages, fetch headers, fetch body on-demand; separate from `google_gmail.py` (send-only)
2. `email_sync.py` / `email_sync_loop()` — 5-min background poll, upsert Email rows, trigger scorer SkillRuns, run voice profile init on first connect
3. `email-scorer` skill — context-powered 5-tier scoring via `skill_executor.py`; batches 15-20 emails per SkillRun
4. `email-drafter` skill — fetches body on-demand from Gmail API, loads voice profile, assembles context, generates draft
5. `api/email.py` — REST endpoints for review UI (GET threads, POST approve/edit/dismiss)
6. `EmailPage.tsx` + sub-components — scored thread list with virtualization, draft review panel

**Key patterns:**
- Sync worker decoupled from skill execution via job queue (never await LLM inline in sync loop)
- Thread grouping as SQL view (GROUP BY `gmail_thread_id`), not a stored entity
- Voice profile in JSONB (open-ended schema, no migration required for new pattern fields)
- Body stored as snippet only; full body fetched on-demand and discarded after draft generation
- Each SkillRun uses its own DB session with explicit `tenant_id` filter on every context query

See `ARCHITECTURE.md` for the full system diagram, data flow, and build order.

### Critical Pitfalls

1. **historyId expiry without full-sync fallback** — Gmail's `history.list` returns HTTP 404 when the watermark is stale (after any gap > ~1 week). Without an explicit 404 handler that resets `initial_sync_done = false` and triggers a full re-sync, emails are silently missed forever. Must be in `sync_inbox()` from day one.

2. **OAuth scope expansion breaking existing users** — Adding `gmail.readonly` to the existing `SCOPES` list in `google_gmail.py` will cause `invalid_grant` for all users who consented to send-only. Their Gmail send integration goes red. Recovery requires forced re-consent for every user. The fix is a completely separate `gmail-read` Integration row with its own OAuth flow. This is the single highest-impact architectural decision.

3. **Voice profile poisoned by auto-replies** — Gmail's sent folder includes out-of-office messages, calendar acceptances, and form confirmations. Running voice extraction on these produces a robotic profile. First drafts sound like system messages. Users abandon the feature after the first impression. Filter must exclude messages with `Auto-Submitted` header, messages under 3 sentences, and common auto-reply phrases before any profile is built.

4. **Tenant context leakage in LLM prompts** — RLS protects SQL queries but not LLM prompt context. If DB sessions are shared across batch SkillRuns or `tenant_id` is not explicitly passed to every context query, one tenant's context entries can appear in another tenant's score prompt. This is a silent data breach. Every context tool call must include explicit `tenant_id` filtering; separate DB sessions must be used per SkillRun.

5. **Email body in error logs (GDPR time bomb)** — Developer instinct is to log the value that caused a parse error. Email bodies contain PII (names, financials, legal content). Once in logs, they are shipped to Datadog/Sentry and retained for 90 days. Establish a hard rule at kickoff: email content never appears in any log at any level. Enforce with a Sentry before-send hook and a pre-commit lint check.

See `PITFALLS.md` for full pitfall descriptions, recovery strategies, and phase-to-pitfall mapping.

---

## Implications for Roadmap

Based on the combined research, the feature dependency graph, build order analysis, and pitfall phase mapping, the following phase structure is recommended.

### Phase 1: Data Layer and Gmail Foundation

**Rationale:** All subsequent work depends on DB models and Gmail read access existing. This phase has no prerequisites and unblocks every other phase. The critical architectural decision (separate OAuth grant for read scope) must be enforced here before any code is written.

**Delivers:**
- 4 new DB tables with RLS policies: `emails`, `email_scores`, `email_drafts`, `email_voice_profiles`
- SQLAlchemy models for all 4 tables
- `gmail_read.py`: list messages, fetch headers, fetch body on-demand, fetch sent messages
- New OAuth flow for `gmail-read` scope; new Integration row pattern
- `config.py` addition: `draft_visibility_delay_days`

**Addresses (from FEATURES.md):** Gmail inbox sync foundation; configurable draft visibility

**Avoids (from PITFALLS.md):**
- OAuth scope expansion pitfall: separate `provider="gmail-read"` Integration row enforced here
- Email body in logs: log redaction pattern established in `gmail_read.py` from line 1

**Research flag:** Standard patterns — follows existing `google_gmail.py` and RLS migration patterns exactly. Skip research-phase.

---

### Phase 2: Sync Worker and Voice Profile

**Rationale:** The sync worker creates Email rows and triggers all downstream processing. Voice profile extraction must run on first connect — before any draft is generated. Getting the filter logic correct here prevents the poisoned-profile trust failure. The concurrency structure (asyncio.gather batches) must be correct from the start; retrofitting it later is expensive.

**Delivers:**
- `email_sync.py`: `email_sync_loop()`, `sync_inbox()`, `upsert_email()`, `voice_profile_init()`
- Incremental sync via `historyId` with explicit 404 full-sync fallback
- Concurrent integration processing (asyncio.gather, 20-50 per batch, per-integration timeout)
- Voice profile extraction filtered to substantive sent emails (>3 sentences, no auto-replies)
- `low_confidence` flag when fewer than 30 quality samples remain
- `main.py` registration of `email_sync_loop()` asyncio task

**Addresses (from FEATURES.md):** Gmail read sync (P1); voice profile extraction on setup (P1)

**Avoids (from PITFALLS.md):**
- historyId expiry: 404 full-sync fallback built into `sync_inbox()`
- Polling wall at 200+ users: concurrent batch processing from day one
- Voice profile poisoned by auto-replies: filter logic ships with initial extraction

**Research flag:** Standard patterns — clones `calendar_sync.py`. The concurrency model (asyncio.gather with per-integration timeout) is the only non-trivial design decision. Skip research-phase.

---

### Phase 3: Email Scorer Skill

**Rationale:** Scoring is the core differentiator and gates both drafting and the review UI. The scorer must be stable before the drafter is built (drafter decisions depend on score). Tenant isolation must be verified before the drafter inherits all scorer context. Batching (15-20 emails per SkillRun) must be implemented here, not retrofit later.

**Delivers:**
- `skills/email-scorer/SKILL.md`: system prompt, context tool usage, scoring schema
- `SkillDefinition` seed for `email-scorer`
- Batched scoring (15-20 emails per SkillRun)
- `EmailScore` rows with: priority (1-5), category, action, reasoning string, `context_refs[]`
- Context store cross-reference: sender entity lookup + 3 most relevant context entries per email
- Scorer triggers `email-drafter` SkillRun for emails where `action == "draft_reply"`
- High-signal emails (meeting followups, deal updates) write `context_entries`
- Per-tenant daily scoring cap

**Addresses (from FEATURES.md):** Email scoring (P1); score reasoning + context refs (P1); in-app alerts for priority 5 (P1); thread-level display with message-level scoring (P1)

**Avoids (from PITFALLS.md):**
- Tenant context leakage: explicit `tenant_id` on every context query; separate DB sessions per SkillRun
- LLM cost at scale: batching + idempotency check (`scored = false` filter) + per-tenant cap

**Research flag:** Needs deeper research during planning. The LLM prompt structure for multi-signal scoring (sender entity weight vs. urgency keywords vs. thread staleness) is not documented. The exact balance of scoring signals needs prompt engineering iteration. Flag Phase 3 for `/gsd:research-phase`.

---

### Phase 4: Email Drafter Skill

**Rationale:** Depends on EmailScore existing (Phase 3) and voice profile being populated (Phase 2). The on-demand body fetch and its failure handling must be specced before the review API is built — the API must know what structured errors to surface.

**Delivers:**
- `skills/email-drafter/SKILL.md`: system prompt with voice profile injection, context assembly
- `SkillDefinition` seed for `email-drafter`
- On-demand Gmail body fetch inside skill execution (never stored)
- Draft body nulled after `status=sent`
- `EmailDraft` rows: `status=pending`, `visible_after=now+delay_days`, `user_edits` field
- Structured error on body fetch failure (401/403) vs. generic failure — snippet fallback
- Proactive token refresh (refresh if within 5 minutes of expiry)

**Addresses (from FEATURES.md):** Draft generation with voice profile + context assembly (P1); configurable draft visibility delay (P1); graceful degradation when Gmail API unavailable (P1)

**Avoids (from PITFALLS.md):**
- On-demand body fetch auth failure: structured error + snippet fallback in review UI
- Draft body retained after send: null `EmailDraft.body` on `status=sent`
- Voice learning from edited drafts without diff: capture `user_edits` as delta, not final text

**Research flag:** Needs deeper research during planning. Draft quality is highly dependent on prompt engineering and context assembly strategy. The voice profile injection format and context relevance ranking (which 3 context entries to include) need validation. Flag Phase 4 for `/gsd:research-phase`.

---

### Phase 5: Review API and Frontend

**Rationale:** Depends on Email, EmailScore, and EmailDraft rows existing (Phases 1-4). The API and UI can be built in parallel once the backend endpoints are defined, but the API spec must be finalized first. No SSE required — email review is request/response, not streaming.

**Delivers:**
- `api/email.py`: GET threads, GET thread detail, POST approve, POST edit, POST dismiss, GET voice-profile
- Thread grouping via SQL GROUP BY (not stored entity); composite index on `(tenant_id, gmail_thread_id, received_at DESC)`
- `EmailPage.tsx`: scored thread list sorted by priority tier, then recency
- `ThreadList.tsx`: virtualized with `@tanstack/react-virtual` for inboxes > 100 emails
- `ThreadCard.tsx`: score badge, reasoning snippet, draft-ready indicator, approve/edit/dismiss
- `DraftReview.tsx`: draft text, context refs, inline edit mode (textarea, not rich editor)
- `useEmailThreads.ts` hook, `stores/email.ts` Zustand store
- In-app alert integration (priority 5 → existing notification system)
- Score reasoning visible on every email (not behind a toggle)

**Addresses (from FEATURES.md):** Draft review UI (P1); one-click approval (P1); draft edit (P1); draft dismiss (P1); in-app critical alerts (P1); score reasoning visible (P1)

**Avoids (from PITFALLS.md):**
- Notification fatigue: alert only on priority 5; batch everything else
- Bad first draft kills adoption: draft visibility delay config gates early exposure
- No original context visible: snippet shown alongside draft; "View full email" with auth-failure handling
- Urgency inflation: alert threshold is priority 5 only, never lower

**Research flag:** Standard patterns — Tailwind v4 + `@tailwindcss/typography` integration needs a quick verification step during setup (plugin API changed in v4). Otherwise well-documented React patterns. Skip research-phase.

---

### Phase 6: Feedback Flywheel and v1.x Polish

**Rationale:** Add only after v1 dogfooding has generated edit signal. The flywheel only works when there is data to learn from. Adding it pre-launch adds complexity with no signal to process.

**Delivers:**
- Edit-to-learn: `user_edits` diff analysis → voice profile update (debounced to every 5 approvals or daily)
- Re-scoring trigger on thread update (new message in existing thread)
- Daily digest document artifact for priority 1-2 emails (reuses existing document artifact system)
- Unsubscribe suggestion in review UI (manual, user clicks the link)

**Addresses (from FEATURES.md):** Feedback flywheel (P2); re-scoring on thread update (P2); daily digest (P2); unsubscribe suggestion (P2)

**Avoids (from PITFALLS.md):**
- Voice drift from circular reinforcement: learn from edit delta, not final approved text
- Voice profile update on every approval (unbounded growth): debounce to batch updates

**Research flag:** Standard patterns — voice profile update is a targeted LLM call using the existing skill executor. Skip research-phase.

---

### Phase Ordering Rationale

- Phases 1-2 are non-negotiable foundations: nothing can be built or tested without the data layer and sync worker.
- Phase 3 (Scorer) before Phase 4 (Drafter): the drafter's context and trigger logic depends on EmailScore rows; building them in parallel risks integration mismatch.
- Phase 5 (API + UI) last in the backend sequence: the REST endpoints can only be specced once the data structures from Phases 3-4 are stable.
- Phase 6 post-dogfood: feedback flywheel without signal is infrastructure waste.
- The architecture research's 7-step build order (`ARCHITECTURE.md` — Step 1 through Step 7) maps directly to this phase structure and should be used as the implementation checklist within each phase.

### Research Flags

**Phases needing `/gsd:research-phase` during planning:**
- **Phase 3 (Email Scorer):** LLM prompt engineering for multi-signal scoring is uncharted for this codebase. Signal weighting (sender entity vs. urgency keywords vs. thread staleness) needs validation. Batching strategy and cross-email pattern reasoning in a single prompt need prompt engineering experimentation.
- **Phase 4 (Email Drafter):** Draft quality is the highest-risk user-facing element. Context assembly strategy (which entries to include, how to rank them for the prompt), voice profile injection format, and cold-start draft behavior all need deliberate prompt engineering research before implementation.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Direct application of existing OAuth and Alembic migration patterns
- **Phase 2:** Direct clone of `calendar_sync.py` with concurrency extension
- **Phase 5:** Well-documented React patterns; only Tailwind v4 typography plugin needs a quick compatibility check
- **Phase 6:** Standard skill executor patterns for voice update

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Minimal new dependencies; existing libraries confirmed via official docs and PyPI/npm. Only gap is Tailwind v4 + typography plugin compatibility — flag for Phase 5 setup. |
| Features | HIGH | Competitor analysis confirmed via multiple sources. Flywheel-specific feature decisions derived from concept brief and advisory board decisions. Scoring prompt design is the one LOW-confidence sub-area. |
| Architecture | HIGH | Based on direct codebase inspection of `calendar_sync.py`, `skill_executor.py`, `google_gmail.py`, and `email_dispatch.py`. No guesswork — patterns are directly reused. |
| Pitfalls | HIGH | Verified against official Gmail API docs, Google developer forums, GDPR compliance literature, and multi-tenant LLM security research. All 7 critical pitfalls have documented real-world precedents. |

**Overall confidence:** HIGH

### Gaps to Address

- **Scoring prompt design (Phase 3):** The exact signal weighting and prompt structure for the email-scorer skill is the biggest open question. Plan for 2-3 prompt engineering iteration cycles before the scorer produces reliable 5-tier results. Do not set user-visible accuracy expectations until after dogfooding.

- **Draft quality (Phase 4):** Draft quality is highly dependent on context richness (how populated the context store is) and voice profile quality (how many substantive sent emails the user has). Users with sparse context stores and few sent emails will see lower-quality drafts. Plan a cold-start UI experience that sets expectations rather than promising context-aware drafts from day one.

- **Tailwind v4 typography plugin:** `@tailwindcss/typography` v0.5.x plugin API compatibility with `@tailwindcss/vite` v4 is flagged as needing implementation-time verification. May require `@tailwindcss/typography@next`. Resolve at the start of Phase 5.

- **Google restricted scope verification timeline:** `gmail.readonly` is a restricted scope requiring Google verification for apps in production. If the app has fewer than 100 verified users or is still in "Testing" mode in Google Cloud Console, the verification process takes 2-6 weeks. This must be initiated no later than the end of Phase 2 to avoid blocking Phase 5 rollout.

---

## Sources

### Primary (HIGH confidence — official documentation and codebase inspection)
- [Google Gmail API — Synchronize clients](https://developers.google.com/workspace/gmail/api/guides/sync) — historyId watermark, 404 behavior, full-sync fallback
- [Google Gmail API — Usage limits](https://developers.google.com/workspace/gmail/api/reference/quota) — per-user quota (15,000 units/min), per-project quota
- [Google Gmail API — Choose scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) — restricted scope classification for `gmail.readonly`
- [Google restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification) — verification timeline
- [google-api-python-client PyPI](https://pypi.org/project/google-api-python-client/) — version 2.193.0 confirmed
- [markdownify PyPI](https://pypi.org/project/markdownify/) — version 1.2.2 confirmed
- [@tanstack/react-virtual npm](https://www.npmjs.com/package/@tanstack/react-virtual) — version 3.13.23 confirmed, React 19 support
- Codebase inspection: `backend/src/flywheel/services/` — `calendar_sync.py`, `google_gmail.py`, `email_dispatch.py`, `skill_executor.py`, `job_queue.py`
- Codebase inspection: `backend/src/flywheel/db/models.py` — Integration, SkillRun, ContextEntry patterns
- Concept brief: `.planning/CONCEPT-BRIEF-email-copilot.md` — architecture decisions, privacy minimization, advisory board decisions

### Secondary (MEDIUM confidence — community sources, multiple corroborating sources)
- [Shortwave vs Superhuman 2025 Exec Guide](https://www.baytechconsulting.com/blog/shortwave-vs-superhuman-the-2025-executives-guide-to-ai-email-clients) — competitor feature analysis
- [Ellie AI Deep Dive](https://skywork.ai/skypage/en/ellie-ai-email-assistant/1976860414183534592) — voice learning patterns
- [PII in Logs is a GDPR Time Bomb](https://dev.to/polliog/pii-in-your-logs-is-a-gdpr-time-bomb-heres-how-to-defuse-it-307l) — log sanitization guidance
- [Cross Session Leak detection](https://www.giskard.ai/knowledge/cross-session-leak-when-your-ai-assistant-becomes-a-data-breach) — multi-tenant LLM context leakage

### Tertiary (LOW confidence — inferred or single-source)
- Scoring prompt signal weighting — no established benchmark; requires empirical validation during Phase 3 implementation
- Draft quality benchmarks — no published metrics for context-assembled email draft approval rates; must be measured during dogfooding

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
