# Feature Research

**Domain:** AI Email Copilot — context-aware email scoring, triage, draft generation, voice learning, and review UX
**Researched:** 2026-03-24
**Confidence:** HIGH (competitor feature analysis confirmed via multiple sources; Flywheel-specific recommendations derived from concept brief + advisory board decisions)

---

## Competitor Feature Analysis

| Feature | Superhuman | Shortwave | SaneBox | Ellie AI | Flowrite / MailMaestro | Our Approach |
|---------|------------|-----------|---------|----------|------------------------|--------------|
| Email prioritization | Split Inbox (manual workstreams) + VIP detection via ML | Smart Bundles (auto-grouped by type) | Behavioral folder sorting (@SaneLater, @SaneBlackHole) | None — draft-only | None | Score at message level, display at thread level. 5-tier numeric score (1=noise, 5=critical) cross-referenced against context store |
| Draft generation | "Instant Reply" via OpenAI — criticized as generic/formal | Ghostwriter learns from sent history — praised as natural-sounding | None | Learns from sent mail passively; single-click draft | Template + tone selection; one-click draft | Sent mail voice profile (100 substantive emails) + full context store assembly. Drafts are always context-aware, never generic |
| Voice learning | No voice learning — generic drafts | Analyzes sent history for tone, word choice, phrase patterns | None | Passive learning from sent mail — same mechanism | Manual tone presets (casual, formal, etc.) | Automated analysis of last ~100 substantive sent emails; stores `EmailVoiceProfile` with tone, length, sign-off, characteristic phrases; updates as user edits drafts |
| Scoring transparency | None — priority is binary (important / other) | None — bundles are opaque | None — folder sorting with no explanation | None | None | Full reasoning string per score; context_refs linking to which meeting notes / entities influenced the decision |
| Triage UX | Keyboard-driven inbox; split view | Bundle review; Cmd+J AI assistant | Drag-and-drop training | Inline draft button per email | Chrome extension overlay | Dedicated review page: scored thread list by priority tier; one-tap approve, edit, or dismiss |
| Cold start | No cold start — generic scoring from day 1 | Style learning takes a few days | Behavioral learning takes weeks | Passive learning; starts generic | No learning | Context store pre-loaded with meetings/companies/entities from day 1. Voice profile extracted in Phase 1 sync before any drafts surface |
| Notification | No critical alert system | No critical alert system | Email summaries | None | None | In-app alert for priority 5 (critical) emails; Slack DM deferred to post-MVP |
| Daily digest | No | No | Scheduled summaries | No | No | Low-priority (1-2) emails batched into document artifact digest |
| Thread handling | Thread summarization ("Auto Summarize") | Thread summaries via AI | Thread-level folder routing | Per-email draft | Per-email draft | Score at message level, surface at thread level (highest score wins); re-score when thread gets new message |
| Feedback loop | None explicit | None explicit | Drag-and-drop retraining | None explicit | None | Approval/edit/dismissal feed back into `EmailVoiceProfile` and scoring refinement |

**Key gap across all competitors:** None of them can access external context (meeting notes, company intel, project knowledge, relationship history). Their scoring is surface-signal-only. This is Flywheel's moat.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that make the copilot feel complete and trustworthy. Missing any of these = product feels half-baked.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Gmail inbox sync (read) | Without it, there is no product | MEDIUM | Expand existing OAuth from send-only to `gmail.readonly` + `gmail.modify`; follow `calendar_sync.py` pattern; 5-min poll |
| Email priority scoring (5-tier) | Users need to know what the system thinks matters, or they can't trust it | HIGH | LLM skill cross-referencing sender entities, topic signals, urgency keywords against context store; requires EmailScore model |
| Score reasoning / transparency | Superhuman and Shortwave give no explanation — users distrust opaque prioritization | MEDIUM | "Scored 5/5 because: Sarah Chen is a known deal contact (matched entity graph), mentions 'close by Friday', thread is 72h old" — stored as `reasoning` string |
| Thread-level display with message-level scoring | Human mental model: the thread got important when Sarah replied, not from the start | LOW | Aggregate: show highest message score at thread level; show which message triggered elevation |
| One-click draft approval | Reviewers expect a single action for accept; multi-step approve is friction | LOW | API endpoint: PATCH /drafts/{id}/approve → triggers email_dispatch.py |
| Draft edit before send | Not every draft is perfect; users must be able to correct without restarting | LOW | Edit mode in review UI; diffs stored as `user_edits` in EmailDraft for voice learning |
| Draft dismiss | Users need to reject bad drafts without penalty | LOW | PATCH /drafts/{id}/dismiss; dismiss teaches the scorer (this email did not warrant a draft) |
| In-app alert for critical emails | Priority 5 emails need immediate attention; buried in a list is not enough | LOW | Reuse existing in-app notification system; badge + alert card for priority 5 |
| Voice profile extraction on setup | If first drafts sound generic, users abandon immediately | HIGH | Pull last 200 sent emails on first Gmail sync, filter to ~100 substantive (>3 sentences), extract tone/length/sign-off/phrases into EmailVoiceProfile |
| Unsubscribe suggestion | Marketing/newsletter emails are noise; users expect help | LOW | Suggest unsubscribe in UI; do NOT automate clicking unsubscribe links in v1 |
| Configurable draft visibility delay | Operators need to control when drafts surface; aggressive for dogfood, cautious for external | LOW | `draft_visibility_delay_days` config; drafts stored in `pending` status, flipped to `visible` after delay passes |

### Differentiators (Competitive Advantage)

Features that set Flywheel Email Copilot apart. Not table stakes — but these are the reason users stay.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Context-store-powered scoring | No competitor can score "this email is about the Series A — Sarah is the lead partner we met last Thursday" because they lack meeting notes + entity graph | HIGH | Scorer skill queries context_entries and context_entities; context_refs in EmailScore links the dots visibly |
| Context-assembled drafts | Draft that opens with "Following up on our Thursday call where we discussed the $5M cap table..." is categorically different from a generic AI reply | HIGH | email_drafter skill fetches body on-demand from Gmail API, loads voice profile, assembles relevant context entries; drafted reply reflects actual relationship history |
| Scoring transparency with context references | Competitors are black boxes. Showing the user exactly which meeting note or entity card drove a score builds trust faster than any other mechanism | MEDIUM | `context_refs[]` in EmailScore, surfaced in UI as linked evidence ("Influenced by: Meeting with Sarah Chen 2026-03-18") |
| Feedback flywheel (edit-to-learn) | Every edit the user makes refines the voice profile and scoring model — the product gets measurably better per week of use | MEDIUM | Diff analysis on user_edits in EmailDraft; periodic (every 50 new sent emails) voice profile refresh; approve/dismiss pattern tracking for scorer |
| Daily digest document artifact | Low-priority emails batched into a scannable HTML report (reusing existing document artifact system) — no competitor does this | LOW | Generate digest as document artifact (existing system); links to full email on demand via Gmail on-demand fetch |
| Context-aware sender scoring | "I know this person — we've met 3 times, they're involved in Project Titan" vs. "unknown sender" changes everything about triage | MEDIUM | `sender_entity_id` in EmailScore links sender to context_entities; relationship depth (meeting count, recency, project involvement) feeds into priority calculation |
| Re-scoring on thread update | Shortwave/Superhuman score once and never revise. A thread that starts as low priority becomes critical when the CEO joins it | MEDIUM | Trigger re-score when email_sync picks up a new message in an existing thread; update EmailScore, re-evaluate draft need |
| Graceful degradation when Gmail API is unavailable | Users still see score + reasoning even if body fetch fails; no silent failures | LOW | On-demand body fetch failure: show EmailScore + snippet, surface "Full body temporarily unavailable" message in UI; do not block review |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-send approved drafts | Saves one tap; removes friction | Trust cannot be assumed from day 1. One bad auto-sent email (wrong tone, wrong context, leaked information) destroys trust permanently. The cost of a false positive here is catastrophic. | Draft-only with one-tap approval — the tap is a human decision gate, not a burden |
| Full email body storage | Enables richer drafts; avoids API call latency | Creates a PII archive that grows indefinitely. Legal/compliance risk (GDPR, CCPA) exceeds value. 90% of drafting value comes from extracted context + snippet. | Extract context entries on ingest; fetch full body on-demand from Gmail API only when drafting |
| Auto-unsubscribe (click links) | Obvious productivity win | Clicking unsubscribe links on behalf of the user is an action with unpredictable side effects (confirmation pages, account changes, legal opt-outs). A bug here can unsubscribe users from things they want. | Surface unsubscribe suggestions in review UI; user clicks the link themselves |
| "Morning briefing" autonomous agent mode | The north-star vision — chief of staff | Requires months of established scoring accuracy and voice accuracy before users will trust an autonomous morning summary. Shipping it pre-trust earns bad press. | Earn trust through the review UI first; morning briefing is v2+ when precision is proven |
| Gmail push notifications (Pub/Sub) | Lower latency than 5-min poll | Adds infrastructure complexity (HTTPS callback endpoint, subscription management, token rotation). 5-minute latency is acceptable for v1 and follows proven calendar_sync pattern. | Poll every 5 minutes via background worker; upgrade to Pub/Sub push in v2 if latency becomes a user complaint |
| Multi-account Gmail support | Many users have personal + work accounts | Multiplies sync complexity, OAuth credential management, and scoring confusion (do cross-account context signals merge?). | Single Gmail account for v1; scope multi-account support post-PMF |
| Auto-labeling / modifying Gmail labels | Feels like organizing directly in Gmail | Label mutations via API require `gmail.modify` scope already needed for other reasons, but auto-applying labels without explicit user training feels presumptuous and risks misclassification | Suggest labels in UI; user applies manually; add auto-labeling as an opt-in feature in v2 |
| Scoring by email content alone (no context) | Easier to build; no dependency on context store | Produces the same result as Superhuman/SaneBox — surface signals only. Kills the differentiation entirely. Every scoring decision must draw from context store, even if the context match is weak. | Always cross-reference context store, even for low-confidence matches; surface confidence level in reasoning string |

---

## Feature Dependencies

```
Voice Profile Extraction
    └──required by──> Draft Generation
                          └──required by──> Draft Review UI
                                                └──required by──> Feedback Flywheel

Gmail Read Sync
    └──required by──> Email Scoring
                          └──required by──> Draft Generation
                          └──required by──> In-App Critical Alerts
                          └──required by──> Daily Digest

Context Store (already built)
    └──enhances──> Email Scoring (sender entity lookup, topic matching)
    └──enhances──> Draft Generation (context assembly for reply body)

Scoring Transparency (context_refs)
    └──enhances──> User Trust
    └──required by──> Thread Detail View (showing which meeting note triggered priority)

Email Scoring
    └──required by──> Re-Scoring on Thread Update

Document Artifact System (already built)
    └──enhances──> Daily Digest Generation

In-App Notification System (already built)
    └──required by──> Critical Email Alerts (priority 5)

Gmail Send Dispatch (already built)
    └──required by──> Draft Approval / Send
```

### Dependency Notes

- **Voice Profile Extraction requires Gmail Read Sync:** Profile is built from sent mail pulled during first sync. Must complete before any draft is generated.
- **Email Scoring requires Context Store:** Scoring without context store cross-reference produces competitor-parity results, not differentiated results. Non-negotiable.
- **Draft Generation requires on-demand Gmail body fetch:** Bodies are not stored. Drafter skill must fetch full body from Gmail API at draft time. Failure mode must be handled gracefully.
- **Feedback Flywheel requires Draft Review UI:** Approvals, edits, and dismissals are the signal source. No UI = no feedback loop.
- **Re-scoring on thread update requires Email Scoring:** Obvious, but ensures the scorer is stable before adding re-trigger logic.

---

## MVP Definition

### Launch With (v1 — dogfooding-ready)

- [ ] Gmail read sync via background poll (5 min) — foundation for everything else
- [ ] Voice profile extraction from sent mail (100 substantive emails) — without this, first drafts are generic and users disengage
- [ ] Email scoring (5-tier) with context store cross-reference — the core differentiator; scoring-only still has value if drafts are delayed
- [ ] Score reasoning with context references — trust mechanism; without transparency, users can't verify the system is using context correctly
- [ ] Draft generation with voice profile + context assembly — the step-change value; one good context-aware draft converts skeptics
- [ ] Configurable draft visibility delay (`draft_visibility_delay_days`) — allows delay=0 for dogfood, delay=7 for cautious external users
- [ ] Draft review UI: scored thread list + approve/edit/dismiss — required to actually use drafts
- [ ] In-app alerts for priority 5 (critical) emails — ensures critical emails never go unnoticed

### Add After Validation (v1.x)

- [ ] Feedback flywheel: edit diffs → voice profile update — add when edit patterns accumulate (after ~2 weeks of use)
- [ ] Re-scoring on thread update — add when scoring stability is confirmed; premature re-scoring can confuse users
- [ ] Daily digest document artifact for low-priority emails — add when users report batch review need; low development cost
- [ ] Unsubscribe suggestion in review UI — low cost, high annoyance reduction; add in first polish sprint

### Future Consideration (v2+)

- [ ] Slack DM notifications for critical emails — already decided as post-MVP; requires Slack integration infrastructure
- [ ] Morning briefing / autonomous agent mode — requires months of proven scoring accuracy + established user trust
- [ ] Gmail push notifications (Pub/Sub) — only if 5-min poll latency generates user complaints
- [ ] Multi-account Gmail support — post-PMF, after single-account pattern is proven
- [ ] Auto-labeling (opt-in) — after feedback loop is stable and users request it

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Gmail read sync | HIGH | MEDIUM | P1 |
| Voice profile extraction | HIGH | HIGH | P1 |
| Email scoring with context store | HIGH | HIGH | P1 |
| Score reasoning + context refs | HIGH | MEDIUM | P1 |
| Draft generation | HIGH | HIGH | P1 |
| Draft visibility delay config | HIGH | LOW | P1 |
| Draft review UI (approve/edit/dismiss) | HIGH | MEDIUM | P1 |
| In-app critical alerts | HIGH | LOW | P1 |
| Thread-level display, message-level scoring | MEDIUM | LOW | P1 |
| Graceful degradation on Gmail API failure | HIGH | LOW | P1 |
| Feedback flywheel (edit-to-learn) | HIGH | MEDIUM | P2 |
| Re-scoring on thread update | MEDIUM | MEDIUM | P2 |
| Daily digest artifact | MEDIUM | LOW | P2 |
| Unsubscribe suggestion | MEDIUM | LOW | P2 |
| Slack DM for critical | MEDIUM | MEDIUM | P3 |
| Morning briefing / autonomous mode | HIGH | HIGH | P3 |
| Multi-account Gmail | MEDIUM | HIGH | P3 |
| Gmail Pub/Sub push | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for dogfooding launch
- P2: Should have, add after v1 validates
- P3: Future milestone, after PMF

---

## Implementation Notes by Feature Area

### Email Scoring

- Five scoring tiers map to four routing decisions: 5=notify+draft, 3-4=draft, 1-2=file+digest, 0=archive
- Scoring signals (in priority order): sender entity match in context graph → topic match against active projects/meetings → urgency keywords (deadlines, "by Friday", "urgent", "action required") → email age/thread staleness → historical sender importance (reply frequency from sent mail)
- Cold start is solved by context store pre-population: meeting notes and entity relationships exist before email sync begins
- Error bias: aggressive escalation (prefer false positive over false negative for high-priority routing), conservative suppression (never auto-archive unless confidence is very high)
- Confidence LOW: The exact LLM prompt structure and weight balancing for scoring needs phase-specific research. Training data for scoring accuracy is not available until user interactions accumulate.

### Voice Profile Learning

- Extract from last 200 sent emails; filter to those >3 sentences to exclude trivial replies ("Sounds good!", "Thanks!")
- Extract: tone (formal/casual/direct/warm), typical length (word count percentile), sign-off (exact string), characteristic phrases (repeated expressions), sentence structure patterns
- Microsoft Copilot's approach (manual style guide) is the wrong model — users should not have to author their voice profile. Shortwave's passive learning (like Ellie AI) is the right model.
- Voice drift: re-run extraction every 50 new sent emails, or on explicit user request. Deferred to implementation.
- Confidence MEDIUM: Specific NLP techniques for phrase extraction from email samples need validation during implementation.

### Draft Generation

- Fetch full email body on-demand from Gmail API at draft time (not stored)
- Assemble context: EmailVoiceProfile + relevant context_entries (matched by sender entity, topics, project mentions) + thread history (fetched as thread, not single message)
- Drafts stored with `visible_after` timestamp; `status: pending` until delay passes; `status: visible` thereafter
- `user_edits` field captures diff between generated and approved/edited draft — primary input for voice refinement
- Confidence LOW on quality: draft quality is highly dependent on prompt engineering, context assembly strategy, and the richness of the context store. This is the highest-risk feature for user trust. Carmack's framing: "the actual hard problem is learning user voice for drafts." Plan for multiple iteration cycles.

### Review UX

- Thread list sorted by score tier (priority 5 first), then recency within tier
- Thread row shows: sender, subject, score badge (1-5), score category label, age, draft-ready indicator
- Thread detail shows: score reasoning text, context refs (linked to context entries), email snippet, full draft (when visible), approve/edit/dismiss actions
- "Approve" is the primary action — should be the most visually prominent control
- "Edit" opens inline editor, not a separate page — friction must be minimal
- "Dismiss" removes draft from queue, does not send — dismissal signal fed to feedback loop
- Ive's UX principle (from concept brief): "the review experience should feel like approving, not editing" — the draft should be good enough that approve is the natural default action

### Critical Alert Design

- Priority 5 triggers in-app notification (reusing existing notification system)
- Alert surface: persistent badge in nav + alert card in email copilot view
- Alert card shows: sender, subject, score reasoning one-liner, "Review now" CTA
- Do not alert on priority 4 or below — alert fatigue is a real risk; better to under-alert than over-alert
- Slack DM deferred: requires Slack integration, out of scope for v1

### Daily Digest

- Generated as document artifact (HTML report via existing system)
- Covers: all priority 1-2 emails batched since last digest
- Format: grouped by category (informational, marketing, newsletters) with one-line summaries
- Link to each email goes to on-demand Gmail fetch, not stored body
- Generation trigger: scheduled (e.g., end of business day) or manual from UI

---

## Sources

- Superhuman AI features: [Superhuman Mail AI Guide](https://blog.superhuman.com/the-best-ai-email-management-tool/), [Shortwave vs Superhuman 2025 Exec Guide](https://www.baytechconsulting.com/blog/shortwave-vs-superhuman-the-2025-executives-guide-to-ai-email-clients)
- Shortwave features: [Shortwave AI Assistant Docs](https://www.shortwave.com/docs/guides/ai-assistant/), [Shortwave Review 2025](https://max-productive.ai/ai-tools/shortwave/)
- SaneBox triage mechanism: [SaneBox Review 2025](https://decidesoftware.com/sanebox-review-a-deep-practical-look-at-the-ai-email-organizer-that-works-with-your-existing-inbox/)
- Ellie AI voice learning: [Ellie AI Deep Dive](https://skywork.ai/skypage/en/ellie-ai-email-assistant/1976860414183534592), [Ellie.ai](https://tryellie.com/)
- Flowrite / MailMaestro: [Flowrite acquired by MailMaestro 2025](https://www.maestrolabs.com/flowrite)
- Microsoft Copilot Outlook: [Prioritize My Inbox](https://support.microsoft.com/en-us/topic/prioritize-my-inbox-65e37040-2c90-4ee3-86d9-e95d5ba0e3cb), [Copilot Voice Style Learning](https://support.microsoft.com/en-us/topic/ask-copilot-to-make-email-drafts-sound-like-you-62cbb77e-2828-4ff2-826e-ca09b1f4e803)
- AI email trust / pitfalls: [Hidden risks of AI emails](https://www.futureofbeinghuman.com/p/the-hidden-risks-of-ai-for-email), [AI email management pros/cons](https://gmelius.com/blog/pros-and-cons-of-ai-assistants)
- Triage review UX patterns: [AI Email Automation](https://www.lindy.ai/solutions/email), [AI email triage classification](https://instantly.ai/blog/automate-email-triage-classification-ai/)
- Project concept brief and advisory decisions: `.planning/CONCEPT-BRIEF-email-copilot.md`

---
*Feature research for: AI Email Copilot — Flywheel V2 Email Copilot Milestone*
*Researched: 2026-03-24*
