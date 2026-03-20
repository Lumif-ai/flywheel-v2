---
name: account-research
version: "1.0"
description: >
  Deep company and stakeholder research for enterprise accounts. Loads all
  existing context (context store, company outputs, transcripts, Granola MCP),
  classifies the account type, builds a verified company profile with source
  attribution, and maps stakeholders with decision paths. Produces structured
  research output consumed by account-competitive and account-strategy skills.
  Can run standalone for pure research or as part of the account strategy pipeline.
context-aware: true
triggers:
  - manual
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
output:
  - account-research-profile
  - context-store-cross-references
---

# account-research

You are performing **deep company and stakeholder research** for an enterprise account. This skill produces the foundation that account-competitive and account-strategy build on.

Can run standalone ("research {company}") or as the first stage of the full account strategy pipeline.

**Trigger phrases:** "research {company} for account strategy", "company deep dive on {company}", "stakeholder map for {company}", "who do we know at {company}", "account research for {company}".

**Does NOT trigger on:** "prep for meeting with {person}" (meeting-prep), "account strategy for {company}" (account-strategy orchestrator), "competitive analysis for {company}" (account-competitive).

---

## Phase 0: Source Discovery & Context Loading

### 0a: Dependency Check (fail fast)

Verify before any work:

```
Required:
  ~/.claude/context/_catalog.md          -- context store catalog
  ~/claude-outputs/companies/            -- output directory (create if missing)

Enhancing (degrade gracefully if missing):
  Granola MCP (mcp__granola__list_meetings)  -- recent meeting transcripts
  ~/Projects/lumifai/transcripts/            -- file-based transcripts
  Playwright MCP                             -- live website crawling
```

If required files are missing, report which ones and stop. If enhancing sources are missing, note the gap and continue.

### 0b: Load Context Store

```
python3 ~/.claude/skills/_shared/context_utils.py pre-read \
  --tags sales,competitors,people,customer,product,market,partnerships \
  --customer {account-slug} --json
```

Load up to 10 recent entries per file. Key files:
- `contacts.md` -- prior contact profiles
- `competitive-intel.md` -- known competitive landscape
- `pain-points.md` -- validated pain points
- `insights.md` -- meeting intelligence
- `action-items.md` -- commitments and next steps
- `icp-profiles.md` -- fit signals
- `product-feedback.md` -- feature requests
- `positioning.md` -- lumif.ai value propositions
- `product-modules.md` -- product capabilities
- Check for `customer-{slug}.md` specifically

Show what was loaded: file count, entry count per file.

### 0c: Source Aggregation

Check these 4 source locations (in order):

1. **Context store** (loaded in 0b)
2. **Company outputs:** `~/claude-outputs/companies/{slug}/` -- prior briefings, pricing docs, demo prep, call intelligence reports. Read first 50 lines of each for summaries.
3. **Transcripts:** Search `~/Projects/lumifai/transcripts/` for files matching the company name or known contact names. If Granola MCP is available, also call `mcp__granola__list_meetings()` and filter for meetings mentioning the company.
4. **User-provided paths:** If the user included file paths or URLs in their request, load those.

**Do NOT scan ~/Downloads/.** Only use explicitly provided paths or the structured locations above.

Display source inventory:
```
Source Inventory for {Company}:
  Context store:     N files, ~N entries
  Company outputs:   N files (list names)
  Transcripts:       N transcripts (list dates)
  Granola meetings:  N transcripts (or "MCP not available")
  User-provided:     N files (or "none")
```

### 0d: Detect Existing State (Resume / Iteration)

Check for `~/claude-outputs/companies/{slug}/account-strategy-state.md`.

**If found:** Read it. Check which research phases are already complete. Offer: "Found existing research for {Company} (last updated {date}). Update research, or start fresh?"

**If not found:** This is new research. Proceed to Phase 1.

Print: `Phase 0/3 complete: Source discovery done.`

---

## Phase 1: Account Intake & Type Classification

### 1a: Gather Account Details

If the user didn't provide all of these, ask:
- **Company name** (required -- stop if not provided)
- **Account type** (detect from context or ask):
  - **Customer/Pilot:** They'll use lumif.ai in their own operations
  - **Channel/White-Label:** They'll resell or white-label lumif.ai to their clients
  - **Strategic Partner:** Co-development, investment, joint GTM
- **Key context** the user wants to share (optional but valuable)

### 1b: Input Validation Gate

| What We Have | Verdict |
|---|---|
| Company name + context store entries | **Proceed** (full research) |
| Company name + transcripts only | **Proceed** (transcript-heavy research) |
| Company name + nothing else | **Proceed with warning:** "No prior context found for {Company}. This will be cold research from web only. Proceed?" |
| No company name | **Stop.** Ask: "Which company should I research?" |

### 1c: Classify Account Type

Detection heuristics:
- Context store has `relationship: prospect` -> default to Customer/Pilot
- Context store has `relationship: partner` -> default to Channel/White-Label
- Multiple client references in transcripts -> likely Channel/White-Label
- C-suite only meetings, no operational detail -> likely Strategic
- If ambiguous, ask the user

Set `account_type` and record in state file.

Print: `Phase 1/3 complete: Account classified as {type}.`

---

## Phase 2: Company Intelligence

**Purpose:** Build a complete, verified company profile. Every fact sourced.

### 2a: Synthesize Existing Knowledge

Start with what's already in context store and company outputs. Extract: company description, size, revenue, leadership, tech stack, recent activity.

### 2b: Web Research

Use WebSearch (and Playwright MCP if available) to fill gaps:
- Company website: about page, leadership page, careers page (tech stack signals)
- Financial data: public filings, stock data (if public), revenue estimates
- Recent news: last 6 months of coverage
- LinkedIn company page: employee count, recent hires, growth signals

### 2c: Cross-Reference & Flag Discrepancies

Compare web findings to meeting transcripts and context store. If they contradict:
- Flag it: "Website says X, but {Person} said Y on {Date}"
- Include both with source markers
- Add to the contradiction log in the state file

### 2d: Output

Produce a structured company profile:
- Company overview (what they do, in one paragraph)
- Key metrics: revenue, employees, locations, stock (if public)
- Leadership team with LinkedIn links
- Subsidiaries / divisions / managed entities (if complex org)
- Technology stack (confirmed vs inferred)
- Strategic direction (what are they moving toward?)

**Every fact must have a source marker.** Follow `~/.claude/skills/account-strategy/references/source-attribution-guide.md`:
- `[S1]` for direct sources with URL
- `[I1]` for inferred with reasoning
- `[M1]` for meeting-sourced (person + date)

Print: `Phase 2/3 complete: Company profile built. {N} facts sourced.`

---

## Phase 3: Stakeholder Mapping

**Purpose:** Map every contact, their role in the deal, and the decision path.

### 3a: Extract Known Contacts

Pull from `contacts.md` in context store. For each contact:
- Name, title, LinkedIn, email
- Relationship status (met, referenced, unknown)
- Role classification: Champion, Evaluator, Decision-maker, Blocker, Advisor/Connector
- Key quotes from transcripts (search by name)

### 3b: Web Research on Contacts

For each known contact, research LinkedIn profiles for:
- Career history, education, tenure at company
- Common connections (especially with lumif.ai team)
- Recent activity/posts (signals about priorities)

### 3c: Identify Unknown-but-Important Contacts

From company research (Phase 2), identify roles we haven't met but should:
- CIO/CTO (if not met -- who controls technology decisions?)
- Budget holder (if different from champion)
- Procurement/legal (if enterprise deal)

### 3d: Map Decision Path

Based on all contacts and context: who leads to who? What's the approval chain?
```
Champion ({name}) -> Evaluator ({name}) -> Budget Holder ({name}) -> Final Approver ({name/unknown})
```

### 3e: Pain & Workflow Extraction

Search transcripts for:
- Workflow descriptions and pain quotes (with person + date attribution)
- Quantified pain metrics (labor hours, risk exposure, cost)
- Failure points in their current process
- Specific feature requests from the prospect
- Named projects or examples from conversations

Print: `Phase 3/3 complete: {N} contacts mapped, {M} unknown contacts identified.`

---

## Output & State

### Save Research Output

Save structured research to `~/claude-outputs/companies/{slug}/account-research.md`:
- Source inventory summary
- Account type classification with reasoning
- Full company profile (Phase 2 output)
- Stakeholder map (Phase 3 output)
- Pain & workflow analysis (Phase 3e output)
- All source markers preserved

### Update State File

Write/update `~/claude-outputs/companies/{slug}/account-strategy-state.md`:

```markdown
## Account Strategy State: {Company}
Account type: {type}

### Phase Completion
| Phase | Skill | Last Run | Status |
|-------|-------|----------|--------|
| 0 - Sources | account-research | {date} | complete |
| 1 - Intake | account-research | {date} | complete |
| 2 - Company | account-research | {date} | complete |
| 3 - Stakeholders | account-research | {date} | complete |

### Contradiction Log
{any contradictions found}

### Source Inventory
{summary from Phase 0c}
```

### Context Store Write-Back

Write new intelligence discovered during research:

```
python3 ~/.claude/skills/_shared/context_utils.py append {file}.md \
  --source account-research --detail "{detail-tag}" \
  --content "{content}" --confidence {level}
```

Target files:
- **contacts.md**: New contacts discovered, title corrections, LinkedIn URLs
- **pain-points.md**: Validated pain points with severity and quotes
- **icp-profiles.md**: Fit signals and account classification

Dedup before writing. Write failures are non-blocking.

### Deliverables

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Research Profile:  ~/claude-outputs/companies/{slug}/account-research.md

  State File:        ~/claude-outputs/companies/{slug}/account-strategy-state.md

  Context writes:    [N] files updated in ~/.claude/context/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Next step:** Run `account-competitive` for competitive landscape, or `account-strategy` to orchestrate the full pipeline.

---

## Memory & Learned Preferences

Check for auto-memory at `~/.claude/projects/-Users-sharan/memory/account-strategy.md`. If exists, load:
- Stakeholder research depth preferences (LinkedIn-based vs context-store-only)
- Preferred research sources
- Financial data preferences (include revenue estimates or skip)

After research, save any new learned preferences.

## Idempotency

- State file tracks completed phases. Re-running same phase on same day skips context store writes.
- Research output file is overwritten (previous version backed up).

## Progress Updates

After each phase: `Phase {N}/3 complete: {summary}.`

## Backup Protocol

Before overwriting research output or state file:
- Create `.backup.{YYYY-MM-DD}` of the previous version
- Keep last 3 backups

## Error Handling

- **Context store empty:** Proceed with web research only. Note: "No prior context. Cold research."
- **No transcripts found:** Skip quote extraction. Note: "No meeting transcripts available."
- **LinkedIn errors:** Use available web data. Note: "LinkedIn profile not accessible."
- **Granola MCP unavailable:** Use file-based transcripts only.
- **Write failures:** Log error, continue. Non-blocking.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md`.

## Guidelines

- **Source everything.** Every fact needs a `[S]`, `[I]`, or `[M]` marker.
- **Be honest about unknowns.** If info isn't findable, say so explicitly.
- **Never fabricate.** Mark as unknown, don't guess.
- **Cross-reference is key.** Web findings vs transcript claims -- flag discrepancies.
- **Privacy first.** Only use publicly available information.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-17 | Initial creation. Phases 0-3 extracted from account-strategy monolith. Source discovery, company intelligence, stakeholder mapping, pain/workflow extraction. |
