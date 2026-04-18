> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file references the legacy `~/.claude/skills/` path. Skills are now served exclusively via `flywheel_fetch_skill_assets` from the `skill_assets` table. Retained for historical reference only; runtime bundles are delivered over MCP and paths shown in this document no longer reflect the live code location.

# Persona Schema Reference

This document defines the schema for both **archetype** personas (generic role/industry combos) and **contact** personas (specific individuals). All persona files follow this structure.

---

## Schema

```markdown
---
name: [Archetype name or person's full name]
type: archetype | contact
industry: [construction | wc-insurance | real-estate | ...]
role_category: [risk | legal | finance | operations | executive | audit | contracts]
inherits: [archetype filename, for contact instances only. Omit for archetypes.]
company: [Company name, for contact instances only. Omit for archetypes.]
response_data:
  messages_sent: 0
  replies: 0
  meetings_booked: 0
  last_updated: null
---

## JTBD (Job to Be Done)

[What they are actually trying to accomplish when they encounter cold outreach.
NOT "evaluate vendors." The real job they are hiring a solution for.]

## Daily Reality

- Inbox volume: [low | medium | high | extreme]
- Vendor fatigue: [1-10, where 10 = "deletes everything without reading"]
- Decision authority: [buyer | champion | influencer | blocker]
- Tech adoption posture: [early adopter | pragmatist | skeptic | laggard]

## Open Triggers (what makes them read past subject line)

- [Specific pattern with reasoning]
- [Another pattern]

## Delete Triggers (instant delete signals)

- [Specific pattern with reasoning]
- [Another pattern]

## Reply Triggers (what earns a response)

- [Specific pattern with reasoning]
- [Another pattern]

## Red Flags (what screams "mass blast")

- [Specific pattern]
- [Another pattern]

## Credibility Signals (what this persona respects)

- [Industry certifications? Data with sources? Peer references? Case studies?]

## Language

- Uses: [terms they actually use in their world]
- Avoids: [terms that feel foreign or vendory]

## Effective Patterns (for drafting guidance)

- Opener: [what works for this persona]
- CTA: [what kind of ask gets a response]
- Length: [preferred email length]
- Tone: [formal | conversational | technical]

## Response History (populated by feedback mode)

<!-- Format: message_hash | date | outcome | hypothesis -->
```

---

## Key Principles

1. **JTBD is never "evaluate vendors."** A VP of Premium Audit reading cold email is not evaluating vendors. Their real job: "Get through audit season without sacrificing quality or burning out my team." A CFO at a family-owned GC is not looking for "compliance tools." Their job: "Keep the family business running efficiently without adding overhead."

2. **Delete triggers are as important as open triggers.** Knowing what gets deleted instantly is more actionable than knowing what might get opened.

3. **Language section prevents vendor-speak.** If the persona uses "loss runs" and "experience mods," do not write about "data-driven insights" and "AI-powered solutions."

4. **Effective Patterns evolve.** This section starts with educated guesses and improves with real response data via feedback mode.

5. **Response History is append-only.** Never delete response history entries. They are the ground truth for calibrating the persona.

---

## Archetype vs. Contact: When to Use Which

| | Archetype | Contact |
|---|-----------|---------|
| **Scope** | Generic role at a generic company in a specific industry | Specific person at a specific company |
| **Location** | `~/.claude/skills/_shared/advisors/industry/[vertical]/` | `~/.claude/skills/outreach-personas/personas/` |
| **Filename** | `[role-shorthand].md` (e.g., `gc-risk-manager.md`) | `[firstname-lastname-company].md` (e.g., `ann-parnigoni-bnbuilders.md`) |
| **inherits** | Omitted | Points to archetype filename |
| **company** | Omitted | Required |
| **Lifespan** | Permanent, updated with pattern data | Permanent, never retired |

---

## Example: Archetype

```markdown
---
name: Risk Manager at a Mid-Size General Contractor
type: archetype
industry: construction
role_category: risk
response_data:
  messages_sent: 0
  replies: 0
  meetings_booked: 0
  last_updated: null
---

## JTBD (Job to Be Done)

"Keep my projects compliant without adding headcount or changing everything I already do."

This person manages COIs in spreadsheets, juggles 20+ vendor emails per week, and
dreads audit season. They are not looking for new technology. They are looking for
fewer fires.

## Daily Reality

- Inbox volume: high
- Vendor fatigue: 7
- Decision authority: champion (recommends to CFO or VP Ops)
- Tech adoption posture: pragmatist

## Open Triggers

- Mention of a specific project or jobsite they manage (shows research)
- Reference to a compliance gap they personally deal with (COI tracking, sub verification)
- Peer reference from another GC in their region

## Delete Triggers

- "AI-powered" anything
- Generic "I help construction companies..." opener
- Attachment from unknown sender
- Long email (4+ paragraphs)

## Reply Triggers

- Question about their current process (shows genuine curiosity)
- Offer to solve a specific, named problem they face this quarter
- Short, direct, no pitch in first email

## Red Flags

- "Dear [First Name]," with no other personalization
- Company boilerplate in the body
- Sent from a no-reply address
- HTML-heavy formatting

## Credibility Signals

- References to other GCs by name (not "leading contractors")
- Knowledge of COI requirements, insurance certificate specifics
- Understanding of GC/sub relationships
- AGC membership or safety award awareness

## Language

- Uses: COIs, subs, certificates, jobsite, GC, change orders, RFIs, punch list
- Avoids: stakeholders, synergies, leverage, digital transformation, scalable solution

## Effective Patterns

- Opener: Reference a specific project, compliance challenge, or regional peer
- CTA: "Worth a 10-minute look?" or "Can I show you how [peer GC] handles this?"
- Length: 3-5 sentences max. No paragraphs.
- Tone: conversational, peer-to-peer, zero corporate speak

## Response History

<!-- No data yet -->
```

---

## Example: Contact Instance

```markdown
---
name: Ann Parnigoni
type: contact
industry: construction
role_category: risk
inherits: gc-risk-manager.md
company: BNBuilders
response_data:
  messages_sent: 0
  replies: 0
  meetings_booked: 0
  last_updated: null
---

## JTBD (Job to Be Done)

Same as archetype, plus: BNBuilders is 100% ESOP ($669M revenue), so compliance is
not just about avoiding fines. It is about protecting employee-owners' equity. Ann's
real job: "Protect the ESOP value by keeping projects compliant without slowing down
our growth."

## Daily Reality

- Inbox volume: high
- Vendor fatigue: 7
- Decision authority: champion (reports to CFO/COO)
- Tech adoption posture: pragmatist

## Open Triggers

- All archetype triggers, plus:
- Reference to BNBuilders' ESOP structure or employee ownership
- Mention of their AGC Safety Award win
- Reference to Pacific Northwest construction market dynamics

## Delete Triggers

- All archetype triggers apply

## Reply Triggers

- All archetype triggers, plus:
- Connection to ESOP-owned companies who solved similar problems
- Reference to BNBuilders' specific project portfolio

## Red Flags

- All archetype red flags apply

## Credibility Signals

- All archetype signals, plus:
- Knowledge of ESOP-specific compliance considerations
- Awareness of BNBuilders' market position in PNW

## Language

- Inherits from archetype
- Additional: ESOP, employee-owners, vested interest

## Effective Patterns

- Inherits from archetype
- Opener variation: Reference ESOP angle or specific BNBuilders project
- CTA: peer reference to another ESOP contractor if available

## Response History

<!-- No data yet -->
```

---

## Creating New Personas

### Archetype Creation Checklist

1. Research the role: job descriptions, industry forums, day-in-the-life content.
2. Identify real JTBD (interview the question: "When they open cold email, what job are they trying to do?").
3. Map inbox reality from the persona's perspective, not the sender's.
4. Fill every section. Empty sections mean the persona is not ready.
5. Save to `~/.claude/skills/_shared/advisors/industry/[vertical]/`.

### Contact Creation Checklist

1. Start from the matching archetype (set `inherits` field).
2. Research the specific person: company context, role, career history, recent news.
3. Override archetype sections only where contact-specific data exists.
4. For sections with no override, note "Inherits from archetype" so reviewers know it is intentional.
5. Save to `~/.claude/skills/outreach-personas/personas/`.
6. Update `personas/_index.md`.
