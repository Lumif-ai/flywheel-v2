---
name: account-strategy
version: "2.1"
description: >
  Orchestrator that produces comprehensive account strategy briefings for
  enterprise prospects. Consumes output from account-research (company profile,
  stakeholders, pain/workflow) and account-competitive (competitive landscape,
  pricing benchmarks). Adds engagement strategy, risk analysis, strategic
  recommendations, and a dedicated "What We Don't Know" gap synthesis. Generates
  a versioned HTML briefing with source attribution for every claim. Supports
  3 account types with type-specific recommendations, first-class iteration with
  partial updates, and contradiction tracking via a shared state file.
context-aware: true
triggers:
  - manual
dependencies:
  skills:
    - account-research
    - account-competitive
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/design-guidelines.md"
output:
  - account-strategy-briefing-html
  - context-store-cross-references
---

# account-strategy

You are the **orchestrator** that produces a comprehensive account strategy briefing for an enterprise prospect. This skill consumes output from two upstream skills and assembles the final deliverable.

**Pipeline:**
```
account-research (Phases 0-3)  -->  account-competitive (Phases 4-5)  -->  account-strategy (Phases 6-10)
     company profile                  competitor matrix                     engagement, risks, recs
     stakeholder map                  pricing benchmarks                    gap synthesis
     pain/workflow                    internal tools                        HTML briefing
```

**Trigger phrases:** "account strategy for {company}", "build an account strategy", "strategic brief for {company}", "account plan for {company}", "prepare account strategy", "full account pipeline for {company}", "assemble briefing for {company}".

**Does NOT trigger on:** "research {company}" (account-research), "competitive analysis for {company}" (account-competitive), "prep for meeting" (meeting-prep), "prepare demo" (demo-prep).

---

## Phase 0: Load Prerequisites & Orchestrate Upstream

### 0a: Dependency Check

Verify before any work:

```
Required:
  ~/.claude/context/_catalog.md              -- context store catalog
  ~/.claude/design-guidelines.md             -- brand tokens for HTML
  ~/.claude/brand-assets/lumifai-logo.png    -- logo for briefing header
  ~/claude-outputs/companies/                -- output directory (create if missing)

Required upstream outputs (or will run upstream skills):
  ~/claude-outputs/companies/{slug}/account-research.md
  ~/claude-outputs/companies/{slug}/account-competitive.md
```

### 0b: Check Upstream Outputs

Check for `~/claude-outputs/companies/{slug}/account-research.md`:
- **If found and fresh (< 7 days):** Load it. Print: "Using existing research (dated {date})."
- **If found but stale (> 7 days):** Warn: "Research is {N} days old. Use as-is, or re-run account-research?"
- **If not found:** Run account-research first. Print: "No research found. Running account-research for {Company}..."

Check for `~/claude-outputs/companies/{slug}/account-competitive.md`:
- **If found and fresh:** Load it.
- **If found but stale:** Warn and offer refresh.
- **If not found:** Run account-competitive first (which itself needs account-research).

### 0c: Load State File

Read `~/claude-outputs/companies/{slug}/account-strategy-state.md` if it exists.

**If found with completed strategy phases (6-10):** This is an iteration. Offer: "Found existing strategy v{N} for {Company}. Update specific sections, or regenerate?"

**If found with only research/competitive phases:** Upstream is done, proceed to Phase 6.

### 0d: Load Account Type

Extract account type from the state file or account-research output. Needed for type-specific logic in Phases 6 and 8. Load `references/account-types.md` for type templates.

Print: `Prerequisites loaded. {Company} classified as {type}. Proceeding to strategy phases.`

---

## Phase 6: Demo / POC Strategy (Light)

> **v1 light touch.** Captures engagement hooks, not full demo scripts. User can request deeper analysis.

### 6a: Engagement Hooks from Research

From account-research output (pain/workflow section and stakeholder quotes):
- What did the prospect specifically ask to see?
- What workflow examples resonated?
- What terminology do they use? (Map to our terms.)

### 6b: For Customer/Pilot Type

- Suggested POC scope: which entities/contracts/properties to include
- Success criteria: what does "working" look like to them?
- Duration recommendation based on their precedents
- Integration requirements from their tech stack

### 6c: For Channel/White-Label Type

- White-label vs co-branded discussion points
- Client types they'd target first
- Integration and customization requirements
- Support model considerations

### 6d: For Strategic Partner Type

- Joint value proposition framing
- Co-development scope
- Pilot or proof-of-concept structure

Mark this section with a "Light Touch -- Deepen on Request" badge.

Print: `Phase 6/10 complete: Engagement strategy outlined.`

---

## Phase 7: Risk & Blocker Analysis

**Purpose:** What could kill this deal? Be honest, not optimistic.

### 7a: Internal Risks (lumif.ai side)

- Product-market fit risk: does our product actually solve their specific problem?
- Support capacity: can we handle this account's complexity?
- Integration complexity: how hard is it to connect to their systems?
- Resource risk: do we have the team to deliver?

### 7b: External Risks (prospect side)

From account-research (stakeholder map) and account-competitive (internal tools):
- Internal tool overlap: will they choose to build instead of buy?
- Long sales cycle: enterprise procurement is slow
- Champion departure: what if our champion leaves?
- Competitor evaluation: are they actively comparing us?
- Budget freeze: macro conditions affecting their spending

### 7c: Timeline Risks

From account-research transcripts/quotes:
- Urgency signals (or lack thereof)
- Known blockers: "We need to talk to IT" = slow approval
- Reference points: "Yardi took 6 months" = their integration baseline

### 7d: Red Flags from Transcripts

Search account-research output for: hesitation language, objections raised, concerns expressed. Attribute each with `[M]` markers.

### 7e: Risk Register

For each risk:
- **Severity:** Critical (red), High (orange), Medium (blue), Low (green)
- **Likelihood:** High / Medium / Low
- **Mitigation:** What we can do about it
- **Source:** Where this risk was identified

Print: `Phase 7/10 complete: {N} risks identified.`

---

## Phase 8: Strategic Recommendations

**Purpose:** Account-type-specific recommendations. See `references/account-types.md` for type templates.

### 8a: Top 3 Recommendations

For the account type, produce exactly 3 strategic recommendations. Each must include:
1. **What** to do (specific, actionable)
2. **Why** (reasoning, tied to evidence from earlier phases)
3. **How** (next steps to execute)
4. **Risk if we don't** (cost of inaction)

Recommendations must reference specific findings from account-research and account-competitive. Not generic advice.

### 8b: Next Steps Timeline

Numbered action items with:
- Owner (lumif.ai team member or "team")
- Target date (based on timeline signals from research)
- Dependency (what must happen first)

### 8c: Materials Inventory

What exists vs what needs to be created:

| Material | Status | Location |
|----------|--------|----------|
| Account briefing | Generated (this doc) | ~/claude-outputs/companies/{slug}/ |
| Pricing proposal | Needed | -- |
| Demo script (customized) | Needed | -- |
| Business case one-pager | Needed | -- |

### 8d: Success Metrics

How will we know this strategy is working? 3-5 measurable indicators from `references/account-types.md`.

Print: `Phase 8/10 complete: Recommendations ready.`

---

## Phase 9: What We Don't Know

**Purpose:** Synthesize all gaps, unknowns, and low-confidence claims across ALL upstream outputs. This is a DEDICATED phase, not an afterthought.

### 9a: Aggregate Gaps

Scan all inputs for unknowns:
- **From account-research:** Claims tagged `[I]` (inferred), contacts marked "unknown but important", missing tech stack details
- **From account-competitive:** Competitors with "pricing not publicly available", capability gaps we couldn't verify
- **From Phase 7 (risks):** Questions we can't answer
- **From Phase 5 (pricing):** Internal questions needing team answers

### 9b: Classify by Impact

For each gap:
- **Critical** (would change the strategy if answered): budget authority, competitive evaluation status, deal timeline, decision-maker identity
- **Medium** (would sharpen the strategy): tech stack details, org chart completions, pricing sensitivity
- **Low** (nice to know): company culture, vendor relationship history

### 9c: Structure Each Gap

For every gap:
1. **What we don't know** (specific question)
2. **Why it matters** (impact on strategy)
3. **How to find out** (specific action: ask in next meeting, research X, request document Y)
4. **Current best guess** (if we have one, with confidence %)

### 9d: Confidence Summary

Calculate across all phases:
- % of claims that are **confirmed** (2+ sources, `[S]` markers)
- % that are **single-source** (1 `[S]` marker)
- % that are **inferred** (`[I]` markers)
- Number that are **unknown** (gaps in this section)

This becomes the overall confidence score in the briefing header.

Print: `Phase 9/10 complete: {N} gaps identified ({M} critical). Overall confidence: {X}%.`

---

## Phase 10: HTML Assembly & Output

### 10a: Read Design Guidelines

Read `~/.claude/design-guidelines.md`. Follow the HTML template specification in `references/html-template.md`.

### 10b: Version Management

If a previous briefing exists at `~/claude-outputs/companies/{slug}/`:
- Rename it: `account-strategy-v{N}.html` (preserve last 3 versions, delete older)
- Increment version number

### 10c: Generate HTML

Assemble ALL upstream outputs + strategy phases into a single HTML file following `references/html-template.md`:

**Sections (from upstream + this skill):**
1. **Executive Summary** -- 4-6 bullet synthesis across all phases
2. **Company Profile** -- from account-research
3. **Stakeholder Map** -- from account-research
4. **Pain & Workflow** -- from account-research
5. **Competitive Landscape** -- from account-competitive
6. **Commercial Signals** -- from account-competitive (light)
7. **Engagement Strategy** -- Phase 6 (light)
8. **Risk Register** -- Phase 7
9. **Strategic Recommendations** -- Phase 8
10. **What We Don't Know** -- Phase 9
11. **Sources Appendix** -- all `[S]`, `[I]`, `[M]` markers from all phases

**Brand compliance checklist (verify before saving):**
- [ ] Header: dark gradient (#121212 -> #2d2d2d) + coral accent bar
- [ ] Inter font (Google Fonts import)
- [ ] Text: #121212 headings, #6B7280 body
- [ ] Cards: 12px border-radius
- [ ] No prospect brand colors in header
- [ ] No purple gradients on white
- [ ] lumif.ai logo present
- [ ] Sticky nav bar with section links
- [ ] Source appendix with clickable markers

### 10d: Save

Save to: `~/claude-outputs/companies/{slug}/account-strategy-v{N}.html`

### 10e: Update State File

Write/update `~/claude-outputs/companies/{slug}/account-strategy-state.md` with all phase completion data, contradiction log, and open gaps.

### 10f: Context Store Write-Back

Write any new intelligence not already written by upstream skills:

```
python3 ~/.claude/skills/_shared/context_utils.py append {file}.md \
  --source account-strategy --detail "{detail-tag}" \
  --content "{content}" --confidence {level}
```

Target files:
- **contacts.md**: Decision path mappings, role classifications
- **competitive-intel.md**: Positioning recommendations
- **icp-profiles.md**: Account classification and fit validation

Dedup before writing. Write failures are non-blocking.

Print: `Phase 10/10 complete: Briefing generated.`

**Deliverables:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Strategy Briefing:  ~/claude-outputs/companies/{slug}/account-strategy-v{N}.html
                      Open in any browser for the full strategy doc

  State File:         ~/claude-outputs/companies/{slug}/account-strategy-state.md
                      Tracks iteration state, gaps, and phase completion

  Upstream outputs:   ~/claude-outputs/companies/{slug}/account-research.md
                      ~/claude-outputs/companies/{slug}/account-competitive.md

  Context writes:     [N] files updated in ~/.claude/context/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Iteration & Partial Update Protocol

The 3-skill split makes partial updates natural:

### Routing Table

| User Says | Skill to Run |
|-----------|-------------|
| "Update the company research" | account-research only |
| "Update competitive for {Company}" | account-competitive only |
| "Add {Competitor} to the analysis" | account-competitive (partial) |
| "Update the risk section" | account-strategy Phase 7 only + regenerate HTML |
| "Here's a new transcript" | account-research (re-run) -> account-strategy (regenerate) |
| "Pricing needs work, dig deeper" | account-competitive Phase 5 (override light-touch) |
| "Full refresh" | account-research -> account-competitive -> account-strategy |
| "Review this from fresh eyes" | Surface findings as a numbered list. Do NOT auto-fix. |
| "Assemble the briefing" | account-strategy only (assumes upstream is current) |

### Staleness Detection

When loading upstream outputs, check their dates against the state file:
- If account-research is older than account-competitive, warn: "Research is older than competitive analysis. Some context may be stale."
- If either upstream is older than 7 days, suggest refreshing.

### Contradiction Handling

When assembling from upstream outputs:
- If account-research and account-competitive disagree on a fact (e.g., company size, competitor capability), show the newer finding as primary with "Previously:" annotation.
- Log contradictions in the state file.
- Add unresolved contradictions to Phase 9 (What We Don't Know).

---

## Source Attribution

**Hard requirement.** Every number, claim, and assertion must be attributed. No exceptions.

Follow `references/source-attribution-guide.md`:

| Marker | Meaning |
|--------|---------|
| `[S1]` | Direct source with URL |
| `[I1]` | Inferred with reasoning in appendix |
| `[M1]` | From a meeting (person + date) |

Upstream skills produce source markers. This skill preserves them in the HTML and adds its own for Phase 7-8 findings.

**No unsourced numbers. No unattributed claims. No inferred data presented as confirmed.**

---

## Memory & Learned Preferences

Check for auto-memory at `~/.claude/projects/-Users-sharan/memory/account-strategy.md`. If exists, load:
- Preferred briefing detail level
- Source attribution preferences
- Account type defaults
- Sections user always skips or emphasizes
- Demo script locations

After generating a briefing, save any new learned preferences. Update, don't duplicate.

## Idempotency

- Version incrementing prevents HTML overwrite (previous versions preserved).
- Context store writes are deduped by source + detail + date.
- State file is append-only for contradiction log entries.

## Progress Updates

After each phase: `Phase {N}/10 complete: {summary}.`
When running upstream skills: `Running account-research... Running account-competitive...`

## Backup Protocol

Before overwriting any file:
- Rename previous: `{filename}.backup.{YYYY-MM-DD}`
- Keep last 3 backups

## Error Handling

- **Upstream output missing:** Offer to run the upstream skill or proceed without it (degraded briefing).
- **Upstream output stale:** Warn with age, offer refresh or proceed.
- **Design guidelines missing:** Use hardcoded brand tokens from CLAUDE.md.
- **Context store write failure:** Log error, continue. Non-blocking.
- **HTML generation fails:** Save raw markdown as fallback: `account-strategy-v{N}.md`.

## Context Store

This skill is context-aware. Follow `~/.claude/skills/_shared/context-protocol.md`.

## Analyst Voice & Content Quality

The RMR Group and Amphibious Group briefings in `~/claude-outputs/companies/` are the quality bar. Study them before generating any briefing. The goal is output that reads like a senior analyst wrote it, not like a template was filled in.

### Mandatory Content Patterns

1. **"Why This Matters" after every data section.** After presenting facts (company profile, competitive table, pricing), add a `highlight-box` that connects the data to strategy. Never present facts without explaining their implications.

2. **Direct quotes, not summaries.** When meeting transcripts exist, quote people verbatim with attribution. "I don't think it can get any more manual" hits harder than "David described the process as highly manual."

3. **Comparison tables must have a "Why It Matters for {Company}" column.** Don't just list capabilities. Explain relevance. "Contract parsing: RMR's contracts are in Yardi. Nobody is extracting insurance requirements automatically. This is the gap."

4. **Specific tactical advice, not generic.** BAD: "Find the right entry point." GOOD: "Frank Cella (Education) is not our strongest vertical. Research Marsh's Construction Practice leads. Our moat (contract parsing, endorsement verification) is strongest in construction/CRE."

5. **Prepared objection responses.** In risk register and competitive sections, include ready-to-use language: "If they bring up X, say Y."

6. **Named examples from their world.** Reference specific projects, people, systems. "Boylston, Causeway, Station East" not "various large projects."

7. **Math blocks for pricing.** Show the calculation, don't just state the number. Use monospace math-block formatting.

8. **Two-column strategy cards.** For strategic plays, use side-by-side cards: "Confirmed: X" on one side, "Our play: Y" on the other.

### Cold Account Adjustments

When no meetings/transcripts exist, compensate with:
- Deeper web research (careers page for tech stack, press releases for strategic direction)
- Honest confidence scoring (a 38% confidence briefing is fine -- acknowledge it)
- "What We Don't Know" becomes the MOST important section
- Entry point analysis is critical (who to contact, why, through what channel)
- Use their own published research/reports as conversation anchors

### HTML Quality Checklist

Before saving the HTML, verify against `references/html-template.md`:
- [ ] Max width is 1100px (NOT 720px)
- [ ] Font imports include weights 300-800 (NOT just 400-700)
- [ ] H1 weight is 800 (NOT 600)
- [ ] Table headers are dark (#121212) with white text (NOT gray)
- [ ] Section icons are rounded squares (8px radius, NOT circles)
- [ ] Nav links are pill-shaped with background hover (NOT flat underlines)
- [ ] Info grid uses 160px 1fr (NOT 1fr 1fr)
- [ ] Body has -webkit-font-smoothing: antialiased
- [ ] At least one highlight-box per major section
- [ ] At least one quote block per known contact (if transcripts exist)
- [ ] Comparison tables have "Why It Matters" column
- [ ] Risk cards have prepared objection responses
- [ ] Recommendations reference specific findings (not generic advice)

## Guidelines

- **Source everything.** Preserve all `[S]`, `[I]`, `[M]` markers from upstream in the HTML.
- **Explain reasoning.** "We recommend X because Y" not just "We recommend X."
- **Be honest about unknowns.** Phase 9 is more valuable than a confident-sounding briefing with hidden gaps.
- **Never fabricate.** If info isn't findable, say so.
- **lumif.ai is NOT a COI vendor.** Contract-to-coverage intelligence.
- **Internal tools are Tier 0.** Always surface them prominently.
- **Review != Fix.** When asked to review, surface findings as a list. Don't auto-fix.
- **Brand compliance.** All HTML follows `~/.claude/design-guidelines.md`. Never use prospect brand colors.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-03-18 | **Design & content quality overhaul.** Rebuilt html-template.md from RMR/TAG reference briefings: 1100px width, dark table headers, rounded-square section icons, pill nav links, weight 800 H1, antialiased fonts. Added "Analyst Voice & Content Quality" section with 8 mandatory content patterns, cold account adjustments, and HTML quality checklist. Content patterns: "Why This Matters" callouts, direct quotes, "Why It Matters for {Company}" comparison columns, specific tactical advice, prepared objection responses, math blocks, two-column strategy cards. |
| 2.0 | 2026-03-17 | **Refactored to orchestrator.** Phases 0-3 extracted to account-research, Phases 4-5 to account-competitive. account-strategy now consumes upstream outputs and handles Phases 6-10: engagement, risks, recommendations, gap synthesis, HTML assembly. Added routing table for partial updates, staleness detection, upstream freshness checks. |
| 1.0 | 2026-03-17 | Initial monolith (all 11 phases in one skill). Replaced by composable split. |
