# Concept Brief: Email Voice & Intelligence Overhaul

> Generated: 2026-03-29
> Mode: Full brainstorm
> Rounds: 4
> Active Advisors: 10 core (Bezos, Chesky, PG, Rams, Ive, Hickey, Vogels, Carmack, Torvalds, Helmer) + 5 situational (DJ Patil, Reid Hoffman, Peter Thiel, Data Governance, Ben Thompson)
> Artifacts Ingested: email_drafter.py, email_voice_updater.py, email_scorer.py, gmail_sync.py, meeting-processor SKILL.md, call-intelligence SKILL.md, context store schema, voice profile DB schema

## Problem Statement

Email drafts sound AI-generated — too lengthy, too polished, not matching the user's actual writing style. The root causes are: (1) voice extraction is too shallow (Haiku on 20 emails, 4 fields), (2) there is zero visibility into what the system learned, (3) the voice profile is siloed in the email system and invisible to other skills, and (4) emails are a one-way consumer of the context store — rich relationship and deal intelligence flows in but nothing flows back out, breaking the flywheel loop.

## Proposed Approach

Three-track overhaul that transforms email from a siloed draft engine into a full bidirectional intelligence source:

- **Track A** — Fix the immediate pain: richer voice extraction with Sonnet, a voice settings card for transparency and light control, and configurable models per engine.
- **Track B** — Make voice a shared asset: write voice profile to the context store so every skill that generates text in the user's voice consumes it.
- **Track C** — Close the flywheel loop: build an email extractor that feeds contacts, topics, relationship signals, deal intelligence, and sentiment back into the context store using a shared context writer extracted from the meeting-processor.

The architecture is: source-specific extractors (meeting, email, future sources), shared context store writer (dedup, merge, conflict resolution). Different eyes, same brain.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Model choice | Sonnet everywhere, configurable per engine | User plans to run through Claude Code (user's own subscription), so cost is user-controlled. Configurable lets power users tune. | Carmack: configurable + sensible defaults. Thompson: counter-positioning vs SaaS competitors who must optimize margins. | Haiku for scoring (rejected: user wants Sonnet default everywhere) |
| Voice settings UX | Read-mostly mirror card with editable tone + sign-off | User wants both trust/transparency AND ability to correct. Board refined: show what was learned, only expose the 2 fields people have strong opinions on. | Ive/Rams: mirror not mixing console. Bezos: trust comes from showing the work. | Full editable settings page with 15 fields (rejected: makes user do AI's job) |
| Track C scope | All 5 dimensions (contacts, topics, relationships, deals, sentiment) | User: restricting to one doesn't serve the flywheel vision. Context store richness comes from all dimensions. | DJ Patil: map each dimension's flywheel arrow. Helmer: each dimension strengthens the cornered resource moat. Slootman retracted scope pushback after learning meeting-processor already handles 80% of the extraction patterns. | Single dimension first (rejected: doesn't serve vision) |
| Extraction architecture | Source-specific extractors + shared context store writer | Board unanimous: emails and meetings are different inputs (headers/threads vs speaker turns). But the write/merge logic should not be reimplemented per source. | Carmack: don't build frameworks for 2 things. Linus: the context store IS the shared layer. Hickey: decouple the write interface. Vogels: merge logic is where bugs hide. | Fully shared extraction layer (rejected: over-abstraction for 2 sources) |
| Track C build effort | Integration work, not greenfield | User challenged board's initial pushback — meeting-processor already extracts all 5 dimensions from transcripts. Email adds a new source to existing pipeline. | PG reversed position: "This is integration, not invention." Slootman conceded. | Treat as 5 new extraction systems (rejected: 80% already exists) |
| Confidence handling | Human review queue for low-confidence extractions | User chose review queue over write-with-tag or skip. | Vogels: email is lower-signal than meetings, needs a quality gate. | Write with confidence tag; auto-skip below threshold |
| PII scope for Track C | Defer — not a concern now | User: don't worry about it now. Email bodies already fetched on-demand and discarded. | Data Governance flagged but user deferred. | Design retention policy upfront |
| Voice drift correction | Defer — tackle later | User: tackle this later. | Board flagged periodic re-extraction from sent emails as an anchor. | Build drift detection now |

## Advisory Analysis

### Customer Clarity & Trust
Bezos and PG converge: the user doesn't want a "voice profile" — they want drafts that sound like they wrote them. The settings page is a trust mechanism ("we analyzed 47 of your sent emails, here's what we learned") with light correction ability, not a configuration surface. If the AI needs a settings page to get voice right, it hasn't learned the voice. Show the work, don't make the user do the work.

### Design & Simplicity
Ive and Rams drove the settings UX to a read-mostly mirror card. Show learned style attributes (tone, avg length, sign-off, characteristic phrases) as a descriptive card. Let users edit tone and sign-off — the two things people have strong opinions on. Everything else learns silently from the edit feedback loop. A "Reset & relearn" button for fundamental misreads. No sliders, no mixing console.

### Technical Architecture
Carmack, Linus, and Hickey reached consensus on source-specific extractors with a shared context store writer. The context store files (contacts.md, insights.md, etc.) ARE the shared abstraction — they don't care which source produced the data. Extraction prompts SHOULD differ because emails and meetings have fundamentally different structure. But the write/merge/dedup logic must be shared to prevent bugs and duplication. Three pieces: email extractor (new), shared context writer (extracted from meeting-processor), meeting-processor refactor (use shared writer).

### Strategic Defensibility
Helmer identifies two compounding powers: cornered resource (the user's communication patterns + relationship history + contextual knowledge across all channels) and switching costs (once voice is trained, context store is rich, and every skill consumes both — leaving means starting from zero). Thompson frames voice-in-context-store as the user's "communication identity layer" — every text-generating skill consumes it, creating aggregation dynamics. The more channels feed the system, the harder it is to replicate elsewhere.

### Data Product Thinking
DJ Patil reframed Track C: for each dimension, the data must enable a decision the user can't make today. Topic threads → better draft assembly (tightest flywheel loop). Contacts → outreach targeting. Relationship signals → prioritize engagement. Deal intelligence → CRM accuracy. Sentiment → alerts. Every dimension has a clear flywheel arrow back to user value. Guard rail: only priority >= 3 emails feed the context store — low-priority emails are noise by definition.

### Operational Reality
Vogels raised the critical guard rail: email is high-volume (50/day vs 5 meetings/week) and lower-signal (snippet vs full transcript). Two mitigations: (1) only priority >= 3 emails feed the context store, (2) low-confidence extractions go to a human review queue rather than auto-writing potentially wrong data. PII posture is maintained: email bodies fetched on-demand and discarded after extraction, same as draft generation.

## Tensions Surfaced

### Tension 1: Settings as Mirror vs Control Panel
- **Ive/Rams** argue: the settings page should be pure transparency — if users need to tune knobs, the AI failed
- **Bezos** argues: trust requires showing the work AND giving the user agency to correct
- **Why both are right:** Trust needs visibility (Bezos), but too many controls undermines the product promise (Ive)
- **User's resolution:** Read-mostly card with editable tone + sign-off only
- **User's reasoning:** "Both — need to show and be able to correct if something is wrong." Board refined to limit editable fields to the two that matter most.

### Tension 2: Scope of Track C
- **Slootman/PG** argued (initially): five extraction dimensions is five products in a trenchcoat
- **Chesky/Helmer** argued: all dimensions serve the flywheel, restricting defeats the purpose
- **Resolution:** User and board aligned after discovering meeting-processor already handles 80% of extraction patterns. Track C is integration work, not greenfield. Slootman and PG retracted.
- **User's reasoning:** "The context store richness is from all dimensions. Restricting to one does not serve the flywheel vision."

### Tension 3: Extraction Architecture
- **Hickey** argues: source-agnostic extraction layer for clean decomposition
- **Carmack/Linus** argue: emails and meetings are different inputs, pretending otherwise is wrong
- **Resolution:** Source-specific extractors + shared context store writer. Different extraction, uniform writes.
- **User's reasoning:** Deferred to tech experts. Board was unanimous on this split.

### Unresolved Tensions
- **Voice drift** — incremental learning from situational edits may drift profile away from true style. Periodic re-extraction proposed but deferred.
- **PII retention** — context store entries derived from emails are persistent even though email bodies aren't stored. Retention policy deferred.

## Moat Assessment
**Achievable powers:** Cornered Resource (user's cross-channel communication data), Switching Costs (compound learning across voice + context + skills)
**Moat status:** Emerging → Strong (if all three tracks ship)

The moat compounds: each new channel (email, meetings, Slack, calendar) that feeds the context store makes the cornered resource deeper. Each skill that consumes the voice profile increases switching costs. Counter-positioning is also present: competitors who host inference must optimize for margin; Flywheel users bring their own Claude subscription, enabling better models at no platform cost.

## Competitive Landscape
No direct competitor combines: (1) cross-channel voice learning, (2) bidirectional context store enrichment from email, (3) voice profile as a shared asset across outreach/social/meeting prep skills. Individual pieces exist (Superhuman does email AI, Apollo does outreach, Granola does meeting intelligence) but none compound across channels through a shared context store.

## Open Questions
- [ ] Confidence threshold values for email extraction — what scores trigger human review queue vs auto-write?
- [ ] Voice drift detection and periodic re-anchoring mechanism (deferred)
- [ ] PII retention policy for email-derived context store entries (deferred)
- [ ] How does the voice settings card surface in the existing Settings page? New tab or section within existing tab?
- [ ] Should the email extractor run synchronously during the gmail sync loop or as a separate background job?

## Recommendation
**Proceed to spec.** The idea survived 4 rounds of advisory scrutiny. Scope is validated. Architecture is clear. The heaviest lift (extraction patterns, context store schema, write logic) already exists in the meeting-processor. Sequence: Track A first (immediate user pain), Track B second (low effort, high leverage), Track C third (highest strategic value, de-risked by existing infrastructure).

## Artifacts Referenced
- `backend/src/flywheel/engines/email_drafter.py` — current draft generation engine
- `backend/src/flywheel/engines/email_voice_updater.py` — current incremental voice learning
- `backend/src/flywheel/engines/email_scorer.py` — current email scoring
- `backend/src/flywheel/services/gmail_sync.py` — gmail sync loop + voice profile init
- `backend/src/flywheel/api/email.py` — email REST endpoints
- `skills/meeting-processor/SKILL.md` — extraction patterns and context store writes (7 files)
- `skills/call-intelligence/SKILL.md` — granular intelligence extraction (8 categories)
- Context store files: contacts.md, insights.md, pain-points.md, action-items.md, competitive-intel.md, product-feedback.md, objections.md
