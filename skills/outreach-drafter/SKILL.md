---
public: true
name: outreach-drafter
version: "1.1"
description: >
  Draft ready-to-send outreach messages (email + LinkedIn) that get replies, not deletes.
  Give it contacts with context and get back personalized, persona-informed messages scored
  against a quality bar. Uses a persistent persona library and cold outreach expert advisors
  to write through the receiver's eyes. Four modes: draft (give contacts, get messages),
  review (score existing drafts, auto-redraft weak ones), build (create new receiver personas),
  feedback (feed response data to improve future drafts). Trigger on: "draft outreach for
  these contacts", "write emails for this list", "draft cold emails", "create outreach messages",
  "review my outreach", "score these emails", "are these ready to send", "check these drafts",
  "build persona", "outreach feedback", "draft follow-ups". Also integrates as a pre-send
  quality gate in the GTM pipeline.
web_tier: 3
---

# outreach-drafter v1.1

**Give it contacts. Get back messages that get replies.**

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-03-27 | Initial release: review, build, feedback modes |
| 1.1 | 2026-03-30 | Renamed from outreach-personas. Added draft mode as primary mode. |

---

## Philosophy

Personas are the product. Review and drafting are consumers.

Cold outreach fails not because nobody reviews it, but because every email is written
without understanding the receiver. The persona library is the compounding asset. After
10 verticals and 500 contacts, the library encodes institutional knowledge about buyer
behavior that would take months to replicate. The moat is not in the review logic (any
LLM can score a message). It is in the accumulated persona intelligence.

---

## Modes

### Mode 1: Draft (primary)

**Trigger:** `/outreach-drafter [contacts file]` or `/outreach-drafter draft [contacts file]`

**Input:** CSV, XLSX, or markdown with contacts (name, title, company, email, industry context).

**Steps:**

1. Read all contacts from the provided file.
2. For each contact, load or build a receiver persona:
   - Check `personas/` for an existing contact persona.
   - If none, match to an archetype in `~/.claude/skills/_shared/advisors/industry/`.
   - If no archetype matches, auto-build a lightweight one on the fly.
3. Load cold outreach advisor frameworks (Hormozi, Coleman, Holland, Braun, McKenna).
4. Load sender profile from `~/.claude/gtm-stack/sender-profile.md` or context store.
5. Load company context (from scorer output, context store, or inline in the contacts file).
6. For each contact, draft email + LinkedIn messages guided by:
   - **Persona:** JTBD, open triggers, reply triggers, language, effective patterns
   - **Advisors:** Hormozi value equation, Coleman CROP, Holland pattern interrupts, Braun curiosity CTAs, McKenna research-first
   - **Sender profile:** who we are, what we offer, value props
   - **Company context:** what we know about their company specifically
7. Self-review each draft against the persona's scoring rubric (single pass).
8. Auto-redraft any message scoring below 7.0.
9. Output: ready-to-send messages file with per-message scores.
10. Show deliverables block with output file path.

**Output format:**

```
## Outreach Drafts: [filename]
Date: [date]
Contacts: N | Personas loaded: N | Archetypes used: N

### Messages
[For each contact: email draft, LinkedIn connection request, LinkedIn follow-up, score]

### Quality Summary
- All passed (7.0+): N
- Auto-redrafted: N
- Flagged for manual review: N
```

**Key drafting rules (from advisors):**
- Never use "AI-powered" or "AI tool" (Holland: delete trigger)
- Lead with value or a question, not product features (Hormozi: value equation)
- Every email must pass the CROP test: Context, Relevance, Outcome, Proof (Coleman)
- CTA must be curiosity-based, not calendar-link-based (Braun: poke the bear)
- Personalization must show real research, not name-swap (McKenna: show me you know me)
- Never use em dashes in drafts
- Sign all emails as: Sharan JM, CPO, lumif.ai

---

### Mode 2: Review

**Trigger:** `/outreach-personas review [file]`

**Input:** .md, .csv, .xlsx, or inline text containing outreach drafts.

**Steps:**

1. Read all drafts from the provided file.
2. For each contact, find a matching persona in `personas/` directory.
3. If no persona exists, check for a matching archetype in `~/.claude/skills/_shared/advisors/industry/`.
4. If no archetype exists, build a lightweight one on the fly (minimal schema, enough for review).
5. Load cold outreach advisor frameworks from `~/.claude/skills/_shared/advisors/` (Hormozi, Coleman, Holland, Braun, McKenna).
6. Score each message on 5 dimensions (see Scoring Rubric below). Each dimension is 1-10 except spam signals (0-5).
7. Compute overall score using weighted formula. Quality bar: **7.0 to pass**.
8. Messages below 7.0: auto-redraft ONCE using persona JTBD + advisor frameworks.
   - Load the persona's open triggers, reply triggers, language preferences, and effective patterns.
   - Apply advisor frameworks (Hormozi value equation, Coleman CROP, Holland pattern interrupts, Braun curiosity CTAs, McKenna "show me you know me").
   - Rewrite the message. Do NOT re-review the rewrite (single pass only).
9. Output: scored report with pass/redrafted/fail breakdown.
10. Show deliverables block with output file path.

**Output format:**

```
## Outreach Review: [filename]
Date: [date]
Personas loaded: [count]

### Summary
- Total messages: N
- Passed (7.0+): N
- Auto-redrafted: N
- Below threshold after redraft: N

### Per-Message Scores
| Contact | Open | Reply | Spam | Personal | CTA | Overall | Status |
|---------|------|-------|------|----------|-----|---------|--------|

### Redrafted Messages
[For each redrafted message: original, scores, redraft, reasoning]
```

### Mode 2: Build

**Trigger:** `/outreach-personas build [title] [industry]`

**Steps:**

1. Check if archetype exists for this role + industry combo in `~/.claude/skills/_shared/advisors/industry/`.
2. If yes: show current persona, offer to enrich with new data.
3. If no: research the role.
   - Search for job descriptions, day-in-the-life content, industry forums.
   - Identify real JTBD (not "evaluate vendors").
   - Map inbox reality, vendor fatigue, decision authority.
4. Build persona following the schema in `references/persona-schema.md`.
5. Save to appropriate location:
   - **Archetype** (generic role): `~/.claude/skills/_shared/advisors/industry/[vertical]/`
   - **Contact instance** (specific person): `personas/`
6. Update `personas/_index.md` (for contact instances).

### Mode 3: Feedback

**Trigger:** `/outreach-personas feedback [results]`

**Input:** CSV or inline data with columns: contact, outcome (opened/replied/meeting/ignored), date.

**Steps:**

1. Accept response data.
2. Match contacts to persona files in `personas/`.
3. Update `response_data` counters in each matched persona's frontmatter.
4. Add entries to the persona's Response History section with outcome and hypothesis.
5. If 10+ messages sent to the same archetype:
   - Analyze patterns across all contact instances inheriting from that archetype.
   - Which openers got replies? Which got ignored?
   - Which CTAs worked? Which did not?
   - Update the archetype's Effective Patterns section.
6. Surface insights to the user (e.g., "VP Premium Audit personas respond 3x more to question-based openers than observation-based").

---

## Advisor Loading

Three layers, loaded contextually:

### Layer 1: Cold Outreach Experts (always loaded in review mode)

| Advisor | File | Lens |
|---------|------|------|
| Alex Hormozi | `~/.claude/skills/_shared/advisors/alex-hormozi.md` | Value-first offers, $100M Leads value equation |
| Kyle Coleman | `~/.claude/skills/_shared/advisors/kyle-coleman.md` | CROP framework (Context, Relevance, Outcome, Proof) |
| Becc Holland | `~/.claude/skills/_shared/advisors/becc-holland.md` | Pattern interrupts, anti-template, recipient-first |
| Josh Braun | `~/.claude/skills/_shared/advisors/josh-braun.md` | Curiosity-based CTAs, "poke the bear" methodology |
| Sam McKenna | `~/.claude/skills/_shared/advisors/sam-mckenna.md` | "Show me you know me," research-first personalization |

### Layer 2: Industry Archetypes (loaded by vertical)

Activated when outreach targets a specific industry. Loaded from:
`~/.claude/skills/_shared/advisors/industry/[vertical]/`

Current verticals with archetypes:
- **Construction:** gc-risk-manager, gc-cfo-family-owned, gc-general-counsel
- **WC Insurance:** wc-vp-premium-audit, wc-cuo, wc-ceo-state-fund

New verticals are created via build mode.

### Layer 3: Contact Personas (loaded per-contact)

Specific individuals stored in `personas/`. Inherit from an archetype but add company
context, personal history, career trajectory, and known signals.

### Baseline Reviewer

`~/.claude/skills/_shared/advisors/skeptical-buyer.md` is always loaded as a baseline
reviewer. This persona represents the default skeptical inbox scanner who deletes 90%
of cold outreach.

---

## Scoring Rubric

Six dimensions. Value Delivered is the heaviest weight. See `references/scoring-rubric.md` for detailed examples.

| Dimension | Range | Weight | What It Measures |
|-----------|-------|--------|------------------|
| **Value Delivered** | **1-10** | **0.30** | **Does the recipient GET something from reading this? The #1 predictor of replies.** |
| Reply Likelihood | 1-10 | 0.20 | Would they actually respond? (Consequence of value, not independent.) |
| Open Likelihood | 1-10 | 0.15 | Would subject line + first line survive the inbox? |
| CTA Effectiveness | 1-10 | 0.15 | Appropriate ask for this persona at this relationship stage? |
| Spam Signals | 0-5 | 0.10 | Mass-blast red flag count |
| Personalization Depth | 1-10 | 0.10 | Real research or name-swap template? |

**Formula:**

```
Overall = (Value * 0.30) + (Reply * 0.20) + (Open * 0.15) + (CTA * 0.15) + ((10 - Spam * 2) * 0.10) + (Personalization * 0.10)
```

**Why Value is #1:** The previous 5-dimension rubric could produce a 9.0 on a message that
offered the recipient NOTHING. That's a rubric failure. You can be personalized, pattern-breaking,
and curiosity-driven while still giving the recipient zero reason to engage. Value is the only
dimension that answers "what does the READER get from this email?"

**Truthfulness guardrail:** Every claim in a drafted message must be grounded. Never fabricate
statistics, benchmark data, or "findings from carriers we've studied." If real data is not
available, use honest framing ("we're building in this space and talking to carriers") instead
of fake authority. Fabricated credibility is worse than no credibility.

**Thresholds:**
- 9.0+: Pass (high bar, earns replies)
- 7.0-8.9: Auto-redraft once, focusing on value gap
- Below 7.0: Flag for manual review (likely needs strategic rethink, not wordsmithing)

---

## Integration Points

| Skill | Integration |
|-------|-------------|
| `gtm-outbound-messenger` | Loads personas + advisors before drafting. Runs review after drafting. |
| `gtm-pipeline` | Wires review step into outreach orchestration. |
| `gtm-company-fit-analyzer` | Consumes company context snippets for persona enrichment. |
| `meeting-prep` | Reads industry archetypes to understand how contacts think. |
| `content-critic` | Parallel quality gate pattern (social posts vs. outreach). |

---

## Directory Structure

```
~/.claude/skills/outreach-personas/
  SKILL.md                              # This file
  personas/                             # Layer 3: per-contact instances
    _index.md                           # Library index with stats
    [firstname-lastname-company].md     # Individual contact personas
  references/
    persona-schema.md                   # Schema for archetype + contact personas
    scoring-rubric.md                   # Detailed scoring rubric with examples

~/.claude/skills/_shared/advisors/
  alex-hormozi.md                       # Layer 1: cold outreach experts
  kyle-coleman.md
  becc-holland.md
  josh-braun.md
  sam-mckenna.md
  skeptical-buyer.md                    # Baseline reviewer (always loaded)
  industry/                             # Layer 2: industry archetypes
    construction/
      gc-risk-manager.md
      gc-cfo-family-owned.md
      gc-general-counsel.md
    wc-insurance/
      wc-vp-premium-audit.md
      wc-cuo.md
      wc-ceo-state-fund.md
```

---

## Memory

**Memory file:** `~/.claude/skills/outreach-personas/memory.md`

**Save:**
- Scoring calibration adjustments (if quality bar changes from 7.0)
- Patterns discovered via feedback mode
- User preferences for review output format
- Verticals the user works in most
- Known advisor loading preferences

**Load:** At skill start, read memory file to apply learned preferences.

---

## Context Store

**Context-aware declaration:** This skill discovers and uses shared context dynamically.

- **Reads from:** `~/.claude/skills/_shared/advisors/` (cold outreach experts, industry archetypes, skeptical-buyer)
- **Reads from:** Context store entries tagged `company-research`, `lead-research` (for persona enrichment)
- **Writes to:** `personas/` directory (contact persona files created during build mode)
- **Writes to:** Archetype files in `_shared/advisors/industry/` (pattern updates from feedback mode)

Discovery is dynamic via catalog tags. Never hardcode file lists.

---

## Dependency Check

**Hard dependencies:** None. The skill can run standalone.

**Recommended:**
- Cold outreach advisor files in `_shared/advisors/` (Hormozi, Coleman, Holland, Braun, McKenna). Without these, review mode still works but applies generic outreach best practices instead of advisor-specific frameworks.
- `skeptical-buyer.md` in `_shared/advisors/`. Without it, baseline skepticism is simulated but less calibrated.

**Check at start:** Verify advisor files exist. If missing, warn the user and proceed with degraded quality.

---

## Input Validation

- **Review mode:** Verify file exists and contains at least one draft. Supported formats: .md, .csv, .xlsx, inline text. Fail fast if file not found or empty.
- **Build mode:** Require both title and industry. Validate industry is a known vertical or confirm creation of a new one.
- **Feedback mode:** Require at least one contact-outcome pair. Validate outcome is one of: opened, replied, meeting, ignored.

---

## Error Handling

- If a persona file is corrupted or missing required fields, skip that contact with a warning and continue scoring the rest.
- If advisor files are missing, proceed with built-in outreach best practices. Note degraded quality in output.
- If auto-redraft fails (edge case), preserve the original message and flag for manual review.
- Never lose completed scores if a later message fails to score.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-27 | Initial release. Review, build, feedback modes. 5-dimension scoring rubric. Three-layer advisor architecture. Persona schema with JTBD, triggers, language, effective patterns. |

## Flywheel MCP Integration

When connected to the Flywheel MCP server, persist drafted messages to the GTM leads pipeline:

### After drafting outreach for each contact:
1. Call `flywheel_draft_lead_message(lead_name, contact_email, channel="email|linkedin", step_number=<N>, subject="...", body="...")`
   - step_number=1 for connection request / cold email
   - step_number=2 for follow-up 1
   - step_number=3 for follow-up 2, etc.
2. This auto-advances the contact's pipeline stage to "drafted"

If Flywheel MCP is not connected, skip these steps silently and use local file output.
