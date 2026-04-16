---
name: call-intelligence
version: "1.0"
description: >
  Extract granular decisions, technical specifications, scope changes, open threads,
  and discussion evolution from meeting transcripts. Produces structured call intelligence
  reports as HTML and JSON. Can be invoked standalone or consumed by meeting-prep.
context-aware: true
triggers:
  - "call intelligence"
  - "show me decisions from"
  - "what was discussed in"
  - "what was decided"
  - "call details for"
  - "decision log"
  - "call insights for"
tags:
  - meetings
  - analysis
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
output:
  - call-intelligence-html
  - call-intelligence-json
  - context-store-writes
web_tier: 3
---

# call-intelligence

You are extracting **granular call intelligence** from meeting transcripts. Your job is to read all available transcripts for a company or person, extract structured decisions, technical specifications, scope changes, open threads, and discussion evolution, and produce a comprehensive intelligence report.

**Trigger phrases:** "call intelligence", "show me decisions from", "what was discussed in", "what was decided", "call details for", "discussion log", "decision log", "call insights for", or any reference to extracting detailed intelligence from past meetings/calls.

---

## Step 0: Load Context & Discover Transcripts

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared/engines"))
from meeting_prep import (
    pre_read_context, discover_transcripts, extract_transcript_sections,
    determine_synthesis_depth
)

existing_context = pre_read_context("call-intelligence")
print(f"Loaded {len(existing_context)} context files")
```

Then discover transcripts:
```python
transcripts = discover_transcripts(company_name=COMPANY, person_name=PERSON)
print(f"Found {len(transcripts)} transcripts")
for t in transcripts:
    print(f"  {t['date']} — {t['filename']}")
```

If no transcripts found, report clearly: "No transcripts found for [query]. Check ~/Projects/lumifai/transcripts/ and ~/.claude/meetings/raw/ for available files." and exit gracefully.

Also check `contacts.md` from the context store for any prior contact/company entries.

## Step 1: Parse All Transcripts

For each transcript, extract full sections:
```python
for t in transcripts:
    sections = extract_transcript_sections(t["path"])
```

Read every transcript in full. Do NOT skip or summarize at this stage. The value of this skill is in the **granularity** — every detail matters.

## Step 2: Extract Structured Intelligence

For each transcript, extract the following categories. Be exhaustive — capture every meaningful detail.

### Category 1: Decisions Made
Explicit agreements or choices made during the call. Each decision must include:
- **What** was decided (specific, not vague)
- **Who** made or confirmed the decision (by name if available)
- **Why** (rationale if stated)
- **Impact** on scope, timeline, or architecture

Examples from transcripts:
- "Murphy confirmed: restrict to SKU level vs feature level" — this is a decision
- "Price movement cards excluded from POC" — this is a decision
- "Multi-contract resolution: best contract applicable only" — this is a decision

### Category 2: Technical Specifications Locked
Specific technical details that were confirmed or agreed upon:
- Data structures, schemas, hierarchies
- Algorithms or logic (e.g., "bottom-up discount search, no compounding")
- System architecture decisions
- Integration patterns
- Product configurations (e.g., "bundles = 6NC codes, options = 7AN codes")
- Pricing rules, calculation methods
- Data sources and their locations

### Category 3: Scope Changes
What was added, removed, deferred, or simplified across meetings:
- **Added:** Features or requirements introduced
- **Removed:** Items explicitly cut from scope
- **Deferred:** Items moved to later phases with stated reasons
- **Simplified:** Complex requirements reduced to achievable versions
- Track the **direction** of scope changes (expanding vs contracting)

### Category 4: Open Threads
Topics discussed but not fully resolved. For each:
- **Topic:** What was discussed
- **Status:** Where it was left (pending decision, needs more info, assigned to someone)
- **Meeting introduced:** Which call first raised this
- **Last discussed:** Most recent mention
- **Blocking?** Does this block progress?

### Category 5: Action Items & Commitments
Specific commitments made by specific people:
- **Who** committed
- **What** they committed to do
- **When** (deadline if stated, or meeting date as proxy)
- **Status:** Open, overdue (if past reasonable timeframe), completed (if evidence exists)

### Category 6: Data Points & Numbers
Specific quantitative information surfaced in calls:
- Metrics, budgets, timelines mentioned
- Test cases with specific values (e.g., "10% becoming 12% on April 1st")
- System scale numbers (e.g., "17 million rows of pricing data")
- Revenue figures, employee counts, project sizes

### Category 7: Discussion Evolution
How key topics evolved across multiple meetings:
- Track how understanding of a topic deepened over time
- Note when positions changed or were refined
- Identify patterns (e.g., "scope consistently narrowed across 4 meetings")
- Flag contradictions or reversals between meetings

### Category 8: Stakeholder Map
Who participated in which meetings and what roles they played:
- Decision-makers vs technical experts vs observers
- Who introduced whom (network growth)
- Who was referenced but not present
- Emerging influence patterns

## Step 3: Cross-Meeting Synthesis

After extracting per-meeting intelligence, synthesize across all meetings:

### Decision Timeline
Chronological list of all decisions, showing how the project evolved through progressive decision-making.

### Scope Evolution Map
Visual (text-based) representation of how scope changed from meeting 1 to the latest:
```
Meeting 1: [Full scope] → Meeting 2: [Narrowed] → Meeting 3: [Refined] → Meeting 4: [Detailed]
```

### Unresolved Items
All open threads and overdue action items, sorted by criticality.

### Knowledge Gaps
What we still don't know. Things that were discussed but never concluded, or topics that should have been discussed but weren't.

## Step 4: Generate HTML Report

**Read `~/.claude/design-guidelines.md` before generating any HTML.** Follow the global design system.

### HTML Structure

**Header:**
- Logo, company name, date range of transcripts
- Badge: number of meetings analyzed
- Print button

**Section 1 — Executive Summary:**
- Total meetings analyzed, date range, participants
- Key stats: N decisions, N specs locked, N open threads, N action items
- One-paragraph synthesis of where things stand

**Section 2 — Decision Log:**
Chronological table with columns: Date | Decision | Decided By | Rationale | Impact
- Color-code by category (scope, technical, commercial, process)
- Bold for high-impact decisions

**Section 3 — Technical Specifications:**
Grouped by domain (e.g., "Pricing Logic", "Product Hierarchy", "Data Sources"):
- Each spec as a card with: specification, confirmed date, confirmed by, status (locked/tentative)
- Use code-style formatting for technical values

**Section 4 — Scope Evolution:**
Timeline visualization showing scope changes across meetings:
- Green badges for additions
- Red badges for removals
- Orange badges for deferrals
- Gray badges for simplifications
- Net direction indicator (expanding/contracting/stable)

**Section 5 — Open Threads & Action Items:**
Table with: Item | Owner | Introduced | Last Discussed | Status | Blocking?
- Overdue items highlighted in warning color
- Blocking items at top

**Section 6 — Data Points Registry:**
All specific numbers, metrics, test cases mentioned across calls:
- Organized by category (financial, technical, timeline, scale)
- Source meeting noted for each

**Section 7 — Discussion Evolution:**
For each major topic, show how it evolved:
- Topic name with timeline bar
- Key quotes or positions from each meeting
- Current status

**Section 8 — Stakeholder Map:**
Visual (HTML) representation of participants:
- Table: Name | Role | Meetings Attended | Key Contributions
- Network diagram (text-based) if referrals or introductions happened

**Section 9 — Knowledge Gaps:**
Numbered list of things we don't know yet, with:
- Why it matters
- Which meeting should have addressed it (if any)
- Suggested resolution approach

### Save Location

Save to: `~/Documents/call-intelligence/YYYY-MM-DD-{company-slug}.html`

Also save structured JSON alongside: `~/Documents/call-intelligence/YYYY-MM-DD-{company-slug}.json`

The JSON should contain all extracted intelligence in a machine-readable format that meeting-prep can consume.

## Step 5: Write Intelligence to Context Store

Write discovered intelligence back to relevant context files:

- **contacts.md:** Updated stakeholder map, role clarifications
- **insights.md:** Key decisions and their rationale
- **action-items.md:** Open action items with owners and dates

Use source tag `call-intelligence` for all writes.

**Deliverables block at the end:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Report (HTML):    /absolute/path/to/report.html
  Data (JSON):      /absolute/path/to/data.json
  Context writes:   [N] files updated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 6: Integration with meeting-prep

When meeting-prep invokes this skill's intelligence:
1. Check if a JSON file exists at `~/Documents/call-intelligence/` for the target company
2. If exists and is less than 7 days old, load it directly (skip re-extraction)
3. If stale or missing, run full extraction

The JSON output schema:
```json
{
  "company": "Company Name",
  "generated": "YYYY-MM-DD",
  "meetings_analyzed": 4,
  "date_range": {"first": "YYYY-MM-DD", "last": "YYYY-MM-DD"},
  "decisions": [...],
  "specifications": [...],
  "scope_changes": [...],
  "open_threads": [...],
  "action_items": [...],
  "data_points": [...],
  "discussion_evolution": [...],
  "stakeholder_map": [...],
  "knowledge_gaps": [...]
}
```

## Memory & Learned Preferences

Check for auto-memory at `~/.claude/projects/-Users-sharan/memory/call-intelligence.md`. If exists, load:
- Preferred detail level (granular vs summary)
- Companies with active tracking
- Custom categories the user added

After generating a report, save any new learned preferences.

## Progress Updates

Report status at each milestone:
- "Reading transcript N of M..."
- "Extracting decisions and specifications..."
- "Cross-meeting synthesis complete — generating report..."

## Error Handling

- **No transcripts found:** Clear message with directory paths checked. Never crash.
- **Partial transcript parse failure:** Skip unparseable section, log warning, continue with what parsed.
- **Context store write failure:** Non-blocking. Log error, continue, report at end.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Guidelines

- **Exhaustive extraction.** The value is in the details. If it was discussed, capture it.
- **Attribution matters.** Every decision and commitment needs a name attached.
- **Chronological ordering.** Decisions and evolution must be time-ordered to show progression.
- **No interpretation beyond evidence.** Report what was said, not what you think it means.
- **Cross-reference with context store.** Flag contradictions between transcript intelligence and context store entries.
- **Machine-readable output.** The JSON must be consumable by meeting-prep without human intervention.

## Tool Access (Web Platform)

When running on the web platform, you have access to these tools via tool_use:

- **context_read**: Read context files. Call with `{"file": "company-intel"}` to read a context file.
- **context_write**: Write to context files. Call with `{"file": "company-intel", "content": ["line1", "line2"], "detail": "description", "confidence": "high"}`.
- **context_query**: Search across context. Call with `{"search": "search terms"}`.
- **web_search**: Search the web. Call with `{"query": "search query"}`. Limited to 20 searches per run.
- **web_fetch**: Fetch and extract text from a URL. Call with `{"url": "https://..."}`.
- **file_write**: Save generated output. Call with `{"filename": "output.html", "content": "<html>...", "mimetype": "text/html"}`.

When running in Claude Code (CLI), use direct Python calls to context_utils instead.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Initial creation. 8 extraction categories, HTML + JSON output, meeting-prep integration. |
