---
name: account-competitive
version: "1.0"
description: >
  Competitive landscape and commercial signal analysis for enterprise accounts.
  Researches competitors sequentially (one at a time), analyzes internal tools,
  builds comparison matrices, identifies competitive moat, and captures pricing
  benchmarks. Consumes account-research output. Produces structured competitive
  intelligence consumed by account-strategy. Can run standalone for competitive
  updates or as part of the account strategy pipeline.
context-aware: true
triggers:
  - manual
dependencies:
  skills:
    - account-research
  files:
    - "~/.claude/context/_catalog.md"
output:
  - account-competitive-analysis
  - context-store-cross-references
web_tier: 1
---

# account-competitive

You are performing **competitive landscape and commercial analysis** for an enterprise account. This skill builds on research from account-research and produces competitive intelligence consumed by account-strategy.

Can run standalone ("update competitive for {company}") or as the middle stage of the full account strategy pipeline.

**Trigger phrases:** "competitive analysis for {company}", "update competitive landscape for {company}", "add {competitor} to {company} analysis", "who competes with us for {company}", "pricing benchmarks for {company} deal", "commercial signals for {company}".

**Does NOT trigger on:** "research {company}" (account-research), "account strategy for {company}" (account-strategy orchestrator), "prep for meeting" (meeting-prep).

---

## Phase 0: Load Prerequisites

### 0a: Load Account Research

Check for `~/claude-outputs/companies/{slug}/account-research.md`.

**If found:** Load it. This is the foundation -- company profile, stakeholders, pain points, source inventory.

**If not found:** Warn: "No account research found for {Company}. Run account-research first for best results, or I can proceed with web research only." If the user says proceed, do basic company research inline (lighter than account-research's full pipeline).

### 0b: Load Existing Competitive Intel

Check context store `competitive-intel.md` for existing entries about this account's space.

Check for existing competitive analysis: `~/claude-outputs/companies/{slug}/account-competitive.md`.

### 0c: Load State File

Read `~/claude-outputs/companies/{slug}/account-strategy-state.md` if it exists. Check which competitive phases are already complete.

Print: `Prerequisites loaded. Starting competitive analysis.`

---

## Phase 4: Competitive Landscape

**Purpose:** Map every alternative the prospect could use. Sequential research (one competitor at a time for v1).

### 4a: Identify Competitors

From context store (`competitive-intel.md`), account-research output, transcripts, and web research:

**Tier 0 -- Internal Tools (always check first):**
Does the prospect build their own solutions? This is the hardest competitor to displace. Both TAG and RMR had internal tools. Search transcripts for mentions of "internal", "built", "our tool", "our system", "we developed".

**Tier 1 -- Direct Competitors:**
Same capability, same buyer. Who else solves this exact problem?

**Tier 2 -- Partial Overlap:**
Some capabilities overlap, different positioning or market segment.

**Tier 3 -- Adjacent:**
Could expand into our space. Enterprise platforms with extensibility.

Present the identified competitors to the user: "I've identified these competitors for {Company}. Add any I'm missing, or confirm to proceed."

### 4b: Research Each Competitor (Sequential)

For each competitor, one at a time:

1. **Capabilities:** What do they do? Core product, key features, integrations.
2. **Pricing:** How much do they charge? **MUST link to pricing page or source URL.** No unsourced pricing claims.
3. **Notable clients:** Who uses them? Especially in the prospect's vertical.
4. **Integrations:** What systems do they connect to? (Critical for enterprise deals.)
5. **Strengths vs lumif.ai:** Where do they win? Be honest.
6. **Weaknesses vs lumif.ai:** Where does lumif.ai win?

Use WebSearch for each competitor. If Playwright MCP is available, crawl their product and pricing pages directly.

**Source attribution:** Every pricing figure must have a `[S]` marker linking to the source. Competitor comparison sites are biased (flag them). First-party pricing pages are most reliable. Follow `~/.claude/skills/account-strategy/references/source-attribution-guide.md`.

Print progress after each competitor: `Researched {N}/{total}: {competitor name}`

### 4c: Internal Tools Analysis

If the prospect has internal tools (identified in Phase 4a):

- What does the internal tool do? (From transcripts and research)
- What can't it do that lumif.ai can?
- Who built it? Who maintains it? (Switching cost = political + technical)
- What did the prospect say about it in meetings? (Search transcripts for quotes with `[M]` markers)
- How sophisticated is it? (RMR's was "very simple compared to" lumif.ai. TAG considered building one.)

This is critical intelligence. Internal tools are often the real competition, not external vendors.

### 4d: Build Comparison Matrix

Create a structured comparison:

```
| Capability | lumif.ai | Competitor A | Competitor B | Internal Tool |
|------------|----------|-------------|-------------|---------------|
| Feature 1  | Full     | Partial     | --          | Basic         |
| Feature 2  | Full     | Full        | Full        | --            |
```

For each cell: capability level (Full / Partial / Basic / None) with brief note.

### 4e: Identify Competitive Moat

Based on the comparison matrix:
- **Unique capabilities:** What can lumif.ai do that NO competitor can?
- **Must-differentiate areas:** Where competitors exist and we need to clearly win
- **Positioning anchor:** How to frame lumif.ai vs the field

**Positioning rule:** lumif.ai is contract-to-coverage intelligence, NOT a commodity COI tracking tool. Never position in the same category as basic COI date-tracking vendors.

Print: `Phase 4 complete: {N} competitors analyzed, comparison matrix built.`

---

## Phase 5: Pricing & Commercial Signals (Light)

> **v1 light touch.** This phase captures signals and benchmarks, not full pricing models. User can request deeper analysis: "deepen pricing for {Company}".

### 5a: Budget Signals from Transcripts

Search account-research output and transcripts for pricing discussions, budget mentions, procurement signals. Attribute each to the person who said it with `[M]` markers.

### 5b: Market Pricing Benchmarks

For competitors identified in Phase 4, compile their pricing into a benchmark table:

```
| Competitor | Model | Price Range | Source |
|-----------|-------|-------------|--------|
| Comp A    | Per user/mo | $15-50 | [S1] |
| Comp B    | Annual license | $50K-200K | [S2] |
```

Every price needs a source URL. No unsourced benchmarks.

### 5c: Cost-of-Problem Anchor

From account-research's pain analysis:
- Labor hours on manual processes
- Risk exposure from gaps
- Lost revenue or efficiency
- Specific numbers mentioned in meetings (with `[M]` attribution)

This becomes the value anchor: "You're spending $X on the problem. Our solution costs $Y."

### 5d: Internal Questions

List questions the team needs to answer internally before presenting pricing:
- What are our actual COGS per unit?
- What margin do we need?
- What's the minimum viable pilot price?
- For channel deals: What wholesale price leaves room for partner margin?

Mark this section with a "Light Touch -- Deepen on Request" badge.

Print: `Phase 5 complete: Commercial signals captured.`

---

## Output & State

### Save Competitive Output

Save structured analysis to `~/claude-outputs/companies/{slug}/account-competitive.md`:
- Competitor identification (all tiers)
- Per-competitor research summaries
- Internal tools analysis
- Comparison matrix
- Competitive moat summary
- Pricing benchmark table
- Budget signals
- Cost-of-problem anchor
- Internal questions
- All source markers preserved

### Update State File

Update `~/claude-outputs/companies/{slug}/account-strategy-state.md`:

```markdown
### Phase Completion (append to existing)
| Phase | Skill | Last Run | Status |
|-------|-------|----------|--------|
| 4 - Competitive | account-competitive | {date} | complete |
| 5 - Commercial | account-competitive | {date} | complete |
```

### Context Store Write-Back

Write competitive intelligence:

```
python3 ~/.claude/skills/_shared/context_utils.py append competitive-intel.md \
  --source account-competitive --detail "{competitor-slug}" \
  --content "{capabilities, pricing, positioning}" --confidence {level}
```

Dedup before writing. Write failures are non-blocking.

### Deliverables

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Competitive Analysis:  ~/claude-outputs/companies/{slug}/account-competitive.md

  State File:            ~/claude-outputs/companies/{slug}/account-strategy-state.md
                         (updated)

  Context writes:        [N] entries to competitive-intel.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Next step:** Run `account-strategy` to assemble the full briefing with recommendations, risks, and gaps.

---

## Partial Update Patterns

This skill supports targeted updates without full re-analysis:

| User Says | Action |
|-----------|--------|
| "Add {Competitor} to the analysis" | Research that competitor only, merge into existing comparison matrix |
| "Update pricing benchmarks" | Re-run Phase 5b only, update benchmark table |
| "Re-research {Competitor}" | Re-run Phase 4b for that specific competitor |
| "Refresh the whole competitive picture" | Re-run Phases 4-5 from scratch |

For partial updates, load existing `account-competitive.md` and merge new findings in. Don't regenerate sections that weren't requested.

---

## Memory & Learned Preferences

Check for auto-memory at `~/.claude/projects/-Users-sharan/memory/account-strategy.md`. If exists, load:
- Competitive research depth preferences
- Preferred competitor sources
- Pricing methodology preferences

After analysis, save any new learned preferences.

## Idempotency

- State file tracks completed phases. Re-running on same day skips context store writes.
- Competitive output file is overwritten (previous version backed up).

## Progress Updates

- After each competitor researched: `Researched {N}/{total}: {name}`
- After Phase 4 complete: `Phase 4 complete: {N} competitors analyzed.`
- After Phase 5 complete: `Phase 5 complete: Commercial signals captured.`

## Backup Protocol

Before overwriting competitive output or state file:
- Create `.backup.{YYYY-MM-DD}` of the previous version
- Keep last 3 backups

## Error Handling

- **Account research missing:** Warn and offer to proceed with web-only research.
- **Web research fails for a competitor:** Skip that competitor, note "research failed" in the table. Continue with others.
- **No pricing found for a competitor:** Note "pricing not publicly available" with confidence: unknown. Don't guess.
- **No transcripts available:** Skip quote extraction. Note: "No meeting transcripts available for budget signal extraction."
- **Write failures:** Log error, continue. Non-blocking.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md`.

## Guidelines

- **Source every price.** The #1 error in competitive analysis is unsourced pricing claims. Every number needs a `[S]` marker with URL.
- **Internal tools are Tier 0.** Always check for them first. Both TAG and RMR had internal solutions.
- **Be honest about competitor strengths.** "They can't do X" is powerful. "They're worse at everything" is not credible.
- **Positioning matters.** lumif.ai is NOT a COI vendor. Contract-to-coverage intelligence.
- **Sequential for v1.** One competitor at a time. Quality over speed.
- **Never fabricate pricing.** If you can't find it, say "not publicly available."

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-17 | Initial creation. Phases 4-5 extracted from account-strategy monolith. Sequential competitor research, internal tools analysis, comparison matrix, pricing benchmarks, partial update support. |
