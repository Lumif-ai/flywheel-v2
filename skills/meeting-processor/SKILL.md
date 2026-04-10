---
name: meeting-processor
version: "2.3"
description: >
  Meeting intelligence processor that classifies meetings into 8 types,
  extracts 9 deep insight types, writes structured entries to the context
  store, and produces enriched standalone output with cross-references
  from compounded knowledge. Supports parallel processing for large batches.
context-aware: true
triggers:
  - "process meetings"
  - "pull from Granola"
  - "update insights"
  - "process my calls"
  - "add meeting notes"
  - "sync meeting notes"
  - "process my notes"
tags:
  - meetings
  - transcription
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
output:
  - context-store-writes
  - standalone-enriched-report
web_tier: 1
parameters:
  input_schema:
    type: object
    properties:
      meeting_id:
        type: string
        format: uuid
        description: "UUID of the meeting to process (from flywheel_fetch_meetings)"
    required:
      - meeting_id
  input_description: "Requires a meeting UUID. Use flywheel_fetch_meetings to find meeting IDs."
---

# meeting-processor

You are processing meeting notes using the **flywheel-powered** meeting intelligence pipeline. Your job is to classify each meeting by type, extract structured data with deep insight analysis, write it to the context store, and produce an enriched standalone report that leverages cross-references from compounded context store data.

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

**Trigger phrases:** "process meetings", "pull from Granola", "update insights", "process my calls", "add meeting notes", "update the expert tracker", "what did we learn from calls", "sync meeting notes", "process latest notes", "process my notes", "update the tracker", or any reference to extracting insights from meetings. Also trigger when the user uploads meeting notes or transcripts.

---

## Step 0: Load Context Store

Run the pre-read to snapshot existing context store data for cross-referencing:

Read all context store files listed in `~/.claude/context/_catalog.md`. For each file, load its contents and count entries (lines starting with `[20`) for a rough tally.

Programmatically, pre-read via:
```
python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags sales,people,product,learning --json
```

Show the user what was loaded (file count, rough entry count per file).

## Step 0.5: Incremental Fetch Filter (Credit Saver)

**Purpose:** Avoid re-fetching and re-processing meetings that have already been extracted. This step compares Granola's meeting list against a local tracker to identify only the **buffer** (new, unprocessed meetings), saving LLM credits on classification + extraction.

### Tracker File

`~/.claude/context/processed-meetings.jsonl` -- one JSON line per processed meeting:

```jsonl
{"source_id": "granola-abc123", "meeting_id": "meeting-2026-03-11-acme-discovery", "title": "Discovery Call with Acme", "date": "2026-03-11", "meeting_type": "discovery", "processed_at": "2026-03-11T15:30:00Z", "source": "granola"}
```

Fields:
- `source_id`: The ID returned by the meeting source (e.g., Granola's meeting ID from `get_meetings()`)
- `meeting_id`: Our internal slug (e.g., `meeting-2026-03-11-acme-discovery`)
- `title`: Meeting title as returned by source
- `date`: Meeting date (YYYY-MM-DD)
- `meeting_type`: Classification result (discovery, expert, prospect, etc.)
- `processed_at`: ISO timestamp of when we processed it
- `source`: Which source provided it (granola, fathom, fireflies, manual)

### Filter Logic

1. **Load tracker:** Read `~/.claude/context/processed-meetings.jsonl`. If file doesn't exist, treat as empty (first run -- all meetings are new).
2. **Fetch meeting list from source:** Call `get_meetings()` (Granola MCP) or equivalent. This returns lightweight metadata (ID, title, date) -- cheap, no full content yet.
3. **Diff:** Compare source IDs from the fetched list against `source_id` values in the tracker.
   - **New meetings** = source IDs not found in tracker -> these are the buffer to process
   - **Already processed** = source IDs found in tracker -> skip entirely
4. **Show the user the diff:**

```
Meetings from Granola: 15 total
Already processed:     12 (skipped)
New (buffer):          3

New meetings to process:
  1. [2026-03-13] Discovery call with FooBar Inc
  2. [2026-03-14] Expert call with Jane Smith
  3. [2026-03-14] Internal standup

Process all 3? Or select specific meetings.
```

5. **Only fetch full content** (`get_meeting_content(id)`) for the buffer meetings. This is where the real credit savings happen -- full content fetch + classification + extraction is skipped for already-processed meetings.

### Force Reprocess Override

If the user says "reprocess all", "reprocess [meeting]", or "force refresh":
- Skip the filter and process the requested meetings regardless of tracker state
- After processing, update the tracker with the new `processed_at` timestamp (overwrites previous entry for that source_id)

### Edge Cases

- **Manual paste/upload:** No source_id available. Process normally, log to tracker with `source_id: "manual-{date}-{slug}"` and `source: "manual"`.
- **Tracker file corrupted:** If JSONL parsing fails, warn user, rename to `.backup`, start fresh.
- **Meeting updated in source:** If a meeting was edited in Granola after processing, the filter will skip it (same source_id). User must explicitly say "reprocess" to pick up edits. This is acceptable -- edits are rare and the credit savings outweigh the edge case.

---

## Step 1: Get Meeting Notes

**Source-agnostic input** (supports Granola, Fathom, Fireflies, manual):

1. **Granola MCP:** If MCP tools are available:
   - Call `mcp__granola__list_meetings()` to get meeting titles + metadata (lightweight).
   - **Apply the incremental filter from Step 0.5** to identify only new meetings.
   - For each new meeting, fetch **two things**:
     - `mcp__granola__get_meetings(meeting_ids=[id])` -- returns **AI-generated summary**, private notes, attendees, metadata
     - `mcp__granola__get_meeting_transcript(meeting_id=id)` -- returns **full verbatim transcript**
   - The **Granola AI summary** is a distinct, valuable artifact. It serves as: (a) active input to extraction alongside the transcript, (b) quick-reference in archive, (c) cross-check for completeness, (d) fallback if transcript is too long for context.
   - Use **both the transcript AND the AI summary** as inputs to extraction (Steps 1.5, 2, 3). The transcript has raw detail; the summary has Granola's distillation from full audio context (may catch things the transcript text misses, e.g., tone, emphasis, speaker identification). Archive both in Step 6.
2. **User paste/upload:** Accept notes pasted directly or uploaded as a file. (Bypass filter -- always process.)
3. **Uploads directory:** Check if the user has placed files in a known uploads location. (Bypass filter -- always process.)

If multiple new meetings are available, list them and let the user select which to process. Process one meeting at a time (unless batch -- see Step 1.75).

---

## Step 1.5: Classify Meeting Type (8 Types)

**Before extracting insights, classify every meeting into one of 8 types.** This determines which extraction pipeline applies and where data is stored.

**Use the Granola AI summary (when available) as a classification accelerator.** The summary often contains clear signals (e.g., "discovery call", "follow-up with prospect", "internal sync") that make classification faster and more accurate than scanning the full transcript. Cross-check against attendees and contacts.md as usual.

### Meeting Types

| Type | Code | Description | Primary Write Targets |
|------|------|-------------|----------------------|
| **Discovery Call** | `discovery` | First-time external call with prospects, potential customers, or market participants being interviewed for product/market insights | pain-points, icp-profiles, contacts, competitive-intel |
| **Expert Call** | `expert` | External call with industry professionals, domain experts, or SMEs for deep technical or market knowledge | pain-points, competitive-intel, insights |
| **Prospect Call** | `prospect` | Meeting with someone already in contacts.md as a prospect -- the classification reads contacts.md to detect this automatically | contacts, pain-points, icp-profiles, competitive-intel |
| **Advisor Session** | `advisor` | Session with advisor, mentor, or board member providing strategic guidance | insights, action-items |
| **Investor Pitch** | `investor-pitch` | Fundraising-related meeting with VCs, angels, or potential investors | insights, action-items, product-feedback |
| **Internal Meeting** | `internal` | Internal standup, sprint review, retrospective -- team members only | action-items, insights |
| **Customer Feedback** | `customer-feedback` | Dedicated feedback, support, or account management session with active customers | product-feedback, pain-points, contacts |
| **Team Meeting** | `team-meeting` | All-hands, planning sessions, brainstorms, offsites, kickoffs | action-items, insights |

### Classification Rules

The classification logic checks contacts.md first for known relationships:
- If ANY attendee is a known **prospect** in contacts.md -> classify as `prospect`
- If ANY attendee is a known **customer** in contacts.md -> classify as `customer-feedback`
- If ANY attendee is a known **advisor** in contacts.md -> classify as `advisor`
- If no contact match, keyword scoring determines the type

Use the classification suggestion as a starting point, but apply your own reasoning:
1. **Check participants.** If ALL are internal team members -> `internal`
2. **Check contacts.md matches.** The classification already does this, but verify if the result makes sense.
3. **Check title and content signals.** Override if the keyword scoring seems wrong.
4. **When ambiguous**, default to `discovery` and flag for user review.

**Always extract something from every meeting** -- including internal standups. Every meeting has value.

### What Gets Processed Per Type

| Type | Deep Insights (9 types) | All 7 Context Files | Transcript Archive | Feedback Loop |
|------|:-----------------------:|:-------------------:|:-----------------:|:-------------:|
| `discovery` | Yes -- all 9 | Yes | Yes | Yes |
| `expert` | Yes -- all 9 | Yes | Yes | Yes |
| `prospect` | Yes -- all 9, emphasis on buying signals | Yes | Yes | Yes |
| `advisor` | Partial -- strategic advice, intros, action items | Primary only | Yes | Yes |
| `investor-pitch` | Partial -- feedback, signals, action items | Primary only | Yes | Yes |
| `internal` | No | action-items, insights only | No | Yes |
| `customer-feedback` | Partial -- product feedback, pain points, expansion | Yes | Yes | Yes |
| `team-meeting` | No | action-items, insights only | No | Yes |

---

### Advisor Session Extraction

For `advisor` meetings, extract these fields instead of the standard deep insights:

- **Strategic Advice Given:** Key recommendations, strategic direction discussed
- **Introductions / Referrals Made:** Who they connected the team with, warm intros offered
- **Market Intelligence Shared:** Industry knowledge, competitive intel, pricing benchmarks
- **Action Items:** What the team committed to based on advisor input
- **Product Feedback:** Any reactions to product demos, positioning, or strategy
- **Follow-up Cadence:** How often the team meets with this advisor
- **Advisor Engagement Level:** Active (regular calls, making intros) / Occasional / One-time

Do NOT extract Hair on Fire, ICP Signals, Willingness to Pay, or Warm Lead for advisor calls.

### Customer Feedback Extraction

For `customer-feedback` meetings, extract:

**Account Health:**
- **Account Health Signal:** Green (happy, expanding) / Yellow (concerns) / Red (at risk)
- **Satisfaction Indicators:** Positive signals (praise, referrals, continued engagement)
- **Concerns / Blockers:** Issues raised, frustrations, delays, unmet expectations

**Product Intelligence:**
- **Feature Requests:** Specific features requested (must-have / nice-to-have)
- **Product Feedback:** Reactions to current product, what works, what doesn't
- **Usage Patterns:** How they use the product, which features, how often
- **Integration Needs:** Systems they want to connect with

**Expansion & Strategy:**
- **Expansion Signals:** New use cases, more users, additional departments, upsell
- **Competitive Mentions:** Evaluating alternatives or competitors?
- **Referral Potential:** Could they refer others? Did they offer introductions?

**Action Items:**
- **Action Items (Team):** What the team committed to doing
- **Action Items (Customer):** What the customer committed to doing
- **Next Meeting / Follow-up:** When the next touchpoint is scheduled

### Prospect Meeting Extraction

For `prospect` meetings (known prospect from contacts.md):

Extract everything from the standard deep insights pipeline (Step 3), PLUS:
- **Prior Interaction Context:** What do we know from contacts.md? Previous meetings, notes.
- **Progression Signals:** Has the relationship moved forward since last contact?
- **Demo/Trial Interest:** Specific interest in seeing the product?
- **Decision Timeline:** Any urgency or timeline signals?
- **Budget Indicators:** Pricing discussions, current spend, budget cycle

Update the prospect's contacts.md entry with new meeting date and any changes to relationship status.

---

## Step 1.75: Parallel Agent Processing (for large batches)

When processing **8 or more meetings**, use parallel agents to maximize throughput. The orchestrator (main conversation) handles classification, dedup, and final assembly. Agents handle the heavy extraction work.

### Decision Logic

| Meetings to Process | Strategy |
|---------------------|----------|
| 1-7 | Process sequentially in main conversation |
| 8-15 | Spawn **2 parallel agents** -- split evenly |
| 16-30 | Spawn **3 parallel agents** -- split by type or date range |
| 31+ | Spawn **4 parallel agents** -- roughly equal batches by date |

### How to Split Work

1. **Apply incremental filter first** (Step 0.5) -- only new meetings enter the pipeline
2. **Classify all new meetings** (Step 1.5) -- fast, done in main conversation
3. **Filter out** `internal` (skip deep insights) and `team-meeting` (lightweight)
4. **Split remaining meetings** across agents
4. Each agent receives: meeting IDs + titles + types, extraction instructions per type
5. **Main conversation** collects results, deduplicates, writes to context store

### Agent Prompt Template

```
You are processing meeting notes. For each meeting below, fetch the content
and extract structured data per the schema.

Meeting type determines extraction depth:
- "discovery"/"expert"/"prospect": Full extraction (all fields + 9 deep insights)
- "customer-feedback": Customer extraction (account health, features, expansion)
- "advisor": Advisor extraction (strategic advice, intros, market intel, actions)

Return results as structured data per meeting. Do NOT write to files.
The main conversation handles all file writes.

Meetings to process:
[list of {id, title, type}]
```

### Assembly (main conversation)

After all agents complete:
1. Collect all extracted records
2. Deduplicate against existing context store
3. Write to context store (Step 5)
4. Archive raw notes (Step 6)
5. Update meeting log (Step 7)
6. Generate enriched output (Step 9)

---

### Checkpoint Protocol (batches >10 meetings)
- Save to `~/.claude/context/meeting_processing_status.md` every 10 meetings
- At startup: check for existing status file, offer resume
- Include: meetings completed, meetings remaining, context files written so far

### Idempotency
- Before writing to context store: check for existing entry with composite key (meeting_id + file + date)
- Programmatically, check duplicates via:
```
python3 ~/.claude/skills/_shared/context_utils.py check-dup [file] --source meeting-processor --detail "[tag]" --date [date]
```
- If duplicate found: skip write, log "duplicate skipped"
- Re-running produces same output without duplicate context entries
- Meeting log `append_meeting_log()` also checks for existing meeting_id before appending

### Backup Protocol
- Before overwriting meeting log or context files: create `.backup.YYYY-MM-DD`, keep last 3

## Step 2: Extract Structured Data

This is the LLM-dependent step. For each relevant context file, extract content lines from the meeting notes.

**Dual-source extraction (when Granola AI summary is available):**

Use both the **transcript** and the **Granola AI summary** as inputs. They complement each other:
- **Transcript** = raw detail, exact quotes, speaker turns, nuance you can only get from verbatim text
- **AI summary** = distilled highlights, action items, decisions, key topics -- Granola processes the full audio so it may capture things the transcript text misses (e.g., tone shifts, off-mic comments, context from visual cues)

**Extraction strategy:** Extract primarily from the transcript (richer detail), then cross-check against the AI summary. If the summary mentions something not evident in the transcript (a decision, an action item, a name), include it with a `[from-summary]` tag so downstream consumers know the provenance. Example:
- `Action: Team to send pricing proposal by Friday [from-summary]`

This ensures nothing falls through the cracks between the two sources.

**Key rules:**
- **One entry per meeting per context file** -- preserves meeting context
- **Distinguish speakers** -- prefix content lines with speaker role when known:
  - `Prospect: frustrated with manual rule config`
  - `Team: committed to sending demo by Friday`
  - `Advisor: recommended focusing on GC segment first`
  - `Customer: need multi-state compliance by Q3`
- **Extract partial contacts** -- name only is fine, whatever is available
- **Write everything, flag low confidence** -- let downstream consumers decide relevance
- **Feature requests go to product-feedback.md**, not pain-points.md

**Entry format for each context file:**

| File | What to Extract |
|------|----------------|
| competitive-intel.md | Competitor mentions, tools used, pricing, switching signals. Speaker attribution. |
| pain-points.md | Problems described, severity indicators, current workarounds. Speaker attribution (prospect vs team). |
| icp-profiles.md | Company profile signals, segment fit, decision-maker info, buying signals. |
| contacts.md | Names, roles, companies, contact info (partial OK). Use per-person schema: Name, Title, Company, Relationship, Role, Meeting history, Notes. |
| insights.md | Overall meeting sentiment/outcome summary, strategic takeaways, cross-cutting observations. |
| action-items.md | Commitments made, owners, due dates, follow-up items. Distinguish team vs external commitments. |
| product-feedback.md | Feature requests, product reactions, demo feedback. Separate from pain points. |

**Speaker distinction is critical** -- prospect pain points vs team commitments are fundamentally different data.

Build entries using:
```python
entry = format_context_entry(
    date="2026-03-11",
    detail="meeting-2026-03-11-acme-discovery",
    content_lines=[
        "Prospect: spending 15-20 hrs/week on manual COI tracking",
        "Prospect: currently using spreadsheets and email reminders",
        "Team: offered live demo with their MSA"
    ],
    confidence="medium"  # default per locked decision
)
```

For contacts.md entries, use the per-person schema:
```python
contact_entry = format_context_entry(
    date="2026-03-11",
    detail="contact: john-smith",
    content_lines=[
        "Name: John Smith",
        "Title: VP Risk Management",
        "Company: Acme Corp",
        "Relationship: prospect",
        "Role: decision-maker",
        "Meeting history: 2026-03-11 discovery call",
        "Notes: Interested in automated COI tracking. Budget cycle in Q4."
    ],
    confidence="medium"
)
```

---

## Step 3: Extract Deep Insights (9 Types)

For each `discovery`, `expert`, or `prospect` call, perform all 9 deep insight analyses. For `customer-feedback`, apply the relevant subset. For `advisor`, skip (use advisor-specific extraction above).

### 1. Hair on Fire Problems

The single most painful problem described. Capture their exact words.

- Classify: **Painkiller** (actively suffering, seeking solutions, has budget) / **Vitamin** (acknowledged but not urgent) / **Unclear**
- Rate severity 1-5: 5 = "need this yesterday, budget allocated" down to 1 = "I guess that could be improved"
- Write to: `pain-points.md` with severity and classification in content lines

### 2. ICP Discovery Signals

Does this confirm an existing ICP or reveal a new segment?

- If confirmed: "Validates [ICP segment] -- [evidence]"
- If new: "NEW ICP: [segment] -- [why they'd be a customer] -- [estimated prevalence]"
- Write to: `icp-profiles.md` with segment classification

### 3. Workflow Details

How they currently do things. This is gold for product design.

- Tool names, step counts, time spent, team sizes, current costs
- Manual vs automated steps, bottlenecks, handoff points
- Write to: `pain-points.md` (workflow-as-pain) and `insights.md` (workflow intelligence)

### 4. Buying Signals & Willingness to Pay

- Interest in a solution? Pricing discussion? Pilot offer?
- Current spend on alternatives? Budget/procurement signals?
- Decision timeline, approval process, number of stakeholders
- Write to: `icp-profiles.md` (buying signals) and `insights.md` (pricing intelligence)

### 5. Competitor Intelligence

- Tools, vendors, or alternatives mentioned
- What they said about them (positive, negative, switching reasons)
- Pricing data points, feature comparisons
- Write to: `competitive-intel.md` with speaker attribution

### 6. Objections & Resistance

- Pushback, regulatory worries, "we already have X", AI skepticism
- These are as valuable as positive signals
- Distinguish between genuine blockers and negotiation tactics
- Write to: `insights.md` (objection patterns) and `competitive-intel.md` (if about competitors)

### 7. Quotable Moments

- Specific phrases useful for pitch decks and investor conversations
- Exact words, not paraphrased -- the rawness is the value
- Write to: `insights.md` with "Quotable:" prefix

### 8. Cross-Call Patterns

- Does this confirm or contradict previous calls?
- "This is the Nth person who mentioned [pattern]"
- Read from existing context store to identify patterns
- Write to: `insights.md` with pattern identification

### 9. Follow-up Linking

- If spoken to this person before, note what changed since last time
- Check contacts.md for prior meeting history
- Progression signals: relationship warming, cooling, stalling
- Write to: `contacts.md` (updated meeting history) and `insights.md` (relationship trajectory)

---

## Step 4: Cross-Reference

Run cross-referencing against the pre-loaded context store snapshot:

```python
# Build extracted_data dict with categorized entities
extracted_data = {
    "contacts": ["John Smith", "Jane Doe"],
    "companies": ["Acme Corp"],
    "pain_points": ["manual COI tracking taking 15-20 hours weekly"],
    "competitors": ["Jones", "TrustLayer"]
}

cross_refs = cross_reference(extracted_data, existing_context)
print(f"Found {len(cross_refs)} cross-references")
for ref in cross_refs:
    print(f"  {ref['type']}: {ref['entity']} -- {ref['details']}")
```

This is the flywheel proof. Show cross-references prominently.

**Entity merging:** When cross_reference() finds an existing entity (same contact name, same company), note it in the entry content line: `"Previously mentioned in meeting-2026-03-05-acme-followup"`.

**Contradictions:** When extracted data contradicts existing context, keep both versions and add: `"Note: contradicts previous entry [detail] -- flagged for resolution"`.

## Step 5: Write to Context Store

```python
# entries_by_file = {filename: entry_dict or None}
entries_by_file = {
    "competitive-intel.md": competitive_entry,
    "pain-points.md": pain_entry,
    "icp-profiles.md": icp_entry,
    "contacts.md": contacts_entry,
    "insights.md": insights_entry,
    "action-items.md": actions_entry,
    "product-feedback.md": feedback_entry,
}

write_results = write_to_context_store(entries_by_file, "meeting-processor")
for f, result in write_results.items():
    print(f"  {f}: {result}")
```

Individual append_entry() calls per file. Programmatically, append via:
```
python3 ~/.claude/skills/_shared/context_utils.py append [file] --source meeting-processor --detail "[tag]" --content "[lines]"
```

Partial success is acceptable. No empty writes -- only include files where content was extracted.

## Step 6: Archive Raw Notes + Granola Summary

```python
meeting_id = f"meeting-{date}-{slug}"  # e.g., meeting-2026-03-11-acme-discovery
archive_path = archive_raw_notes(notes, meeting_id)
print(f"Raw notes archived: {archive_path}")
```

90-day archive retention (locked decision). Raw notes are NOT stored in context store.

**Archive format** (see `references/transcript-template.md`):
- One file per meeting: `YYYY-MM-DD-firstname-lastname-company.md`
- Contains raw unedited transcript + metadata header + key highlights
- Update interview index if maintained

**Granola AI Summary section:** When available from `get_meetings()`, include the Granola-generated summary in the archive file as a dedicated section:

```markdown
## Granola AI Summary

[paste Granola's AI-generated summary verbatim here]

---

## Transcript

[full verbatim transcript below]
```

This preserves the source AI's perspective alongside the raw transcript. Do NOT use the Granola summary as a substitute for our own extraction -- it serves a different purpose (quick reference, cross-check, completeness audit).

## Step 7: Update Meeting Log + Processed Tracker

```python
append_meeting_log(
    meeting_id=meeting_id,
    meeting_type=meeting_type,
    date=date,
    attendees=attendee_names,
    files_written=list(write_results.keys()),
    entry_count=len(write_results),
)
```

**Also append to the processed meetings tracker** (enables incremental fetch in Step 0.5):

```python
import json, datetime

tracker_entry = {
    "source_id": source_meeting_id,       # ID from Granola/Fathom/etc., or "manual-{date}-{slug}"
    "meeting_id": meeting_id,              # Our internal slug
    "title": meeting_title,                # Title as returned by source
    "date": date,                          # YYYY-MM-DD
    "meeting_type": meeting_type,          # Classification result
    "processed_at": datetime.datetime.utcnow().isoformat() + "Z",
    "source": source_name,                # "granola", "fathom", "manual", etc.
}

tracker_path = os.path.expanduser("~/.claude/context/processed-meetings.jsonl")
with open(tracker_path, "a") as f:
    f.write(json.dumps(tracker_entry) + "\n")
```

This is the critical link that makes Step 0.5 work. Without this write, the next run cannot know which meetings were already processed.

## Step 8: Log Event

```python
log_processor_event(
    meeting_id=meeting_id,
    meeting_type=meeting_type,
    files_written=list(write_results.keys()),
    entry_count=len(write_results),
    cross_ref_count=len(cross_refs),
)
```

## Step 9: Generate Enriched Output

```python
enriched_output = generate_enriched_output(
    extracted={
        "summary": summary_text,
        "date": date,
        "attendees": attendee_names,
        "sentiment": sentiment,
        "pain_points": pain_points_list,
        "competitive_intel": competitive_list,
        "icp_signals": icp_list,
        "contacts": contacts_list,
        "product_feedback": feedback_list,
        "strategic_insights": insights_list,
        "action_items": action_items_list,
    },
    cross_refs=cross_refs,
    write_results=write_results,
    meeting_type=meeting_type,
)
print(enriched_output)
```

### Processing Summary Format

```
## Processing Complete

**Meeting:** [title/slug]
**Type:** [type] | **Date:** [date] | **Attendees:** [names]

### Deep Insights Summary
- Hair on Fire: [problem] -- Severity: X/5 -- [Painkiller/Vitamin]
- ICP: [confirmed/new segment]
- Buying Signals: [present/absent] -- [details]
- Competitors Mentioned: [list]
- Objections: [list]
- Quotable: "[exact quote]"
- Cross-Call Pattern: [Nth person to mention X]
- Follow-up: [relationship progression]

### Context Store Writes
[table of files written with status]

### Cross-References Found
[flywheel connections from existing context]

### Action Items
- [ ] [item with owner and due date]
```

## Step 9.5: Save to Library

**Library Contract (Standard 15):** When calling `flywheel_save_document` for each processed meeting:
- **title**: `"Meeting Summary: {Company} — {Meeting Title}"`
- **account_id**: Look up the primary company via `flywheel_fetch_account`. If not found, create it first. Pass the pipeline entry UUID. If no clear company (internal meetings), pass null.
- **tags**: Include relevant tags: company name (slugified), meeting type, quarter. E.g., `["acme-corp", "discovery", "q2-2026"]`
- **skill_name**: `"meeting-processor"`

## Step 9.6: Deliverables

**Always show the deliverables block after processing completes:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Context store:    [N] files updated in ~/.claude/context/
                    [list files written, e.g. contacts.md, pain-points.md, insights.md]

  Meeting archive:  /absolute/path/to/YYYY-MM-DD-name-company.md
                    Raw transcript with metadata header

  Meeting log:      ~/.claude/context/meeting-log (entry appended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 9.6: Progress Updates (Batch Processing)

When processing multiple meetings, show progress after each meeting:

```
Progress: X/Y meetings processed
  discovery: N | expert: N | prospect: N | advisor: N | internal: N
  Context writes: N entries across M files
```

For parallel agent batches (8+ meetings), each agent reports progress independently.
The orchestrator shows a combined view when assembling results.

## Step 10: Collect Feedback

**Read `references/feedback-loop.md` for the full feedback collection and self-improvement mechanism.**

Always end with:
> "Quick feedback on this run? Extraction errors, missing data points, process suggestions?
> Even 'looks good' helps -- your feedback trains the system."

Before each future run, check if feedback has been stored and adjust extraction behavior accordingly. If the same correction has been made 2+ times, apply it proactively.

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/meeting-processor.md`

> **Naming convention:** Memory file name MUST match the `name` field in SKILL.md frontmatter + `.md`. No company prefix, no alias. This ensures every session can find the file by skill name alone.

Check for the memory file. If it exists, load:
- Contact classifications (which contacts are prospects vs team vs advisors)
- Meeting type overrides for recurring meetings
- Preferred extraction emphasis per meeting series
- Any user corrections to previous extractions

After processing, save any new learned preferences to the auto-memory file:
- New contacts identified and their classifications
- Type corrections made by the user
- Extraction preferences (e.g., "always extract competitor mentions even from internal calls")
- Processing stats (cumulative count by type)

---

## Error Handling

- **MCP connection failure:** Fall back to manual input (user paste/upload)
- **Context file write failure:** Log error, continue with other files (partial success OK)
- **Cross-reference failure:** Continue without cross-refs, note in output
- **Archive failure:** Log warning, continue (archive is supplementary)
- **Empty meeting notes:** Warn user, do not process
- **Duplicate meeting:** Check meeting log for existing meeting_id, warn if duplicate
- **contacts.md read failure:** Fall back to keyword-only meeting type inference (no contact-based classification)

---

## Context Store

**Pre-read:** All context files at startup for cross-referencing (Step 0). This snapshot powers the flywheel -- previous meeting data enriches current processing.

**Post-write:** After writing, verify entries were created. Report any failures in processing summary.

**Knowledge overflow:** If extracted content exceeds entry size limits (4000 chars), truncate to fit. For meetings with exceptionally rich content, consider splitting into multiple entries per file.

**Company-specific data:** All company names, product descriptions, contact lists, and pricing data come from the context store at runtime. Read `contacts.md` to identify known relationships. Read `positioning.md` for company context. Read `product-modules.md` for product details. NEVER hardcode this data in the skill.

## Important Notes

- Extraction confidence defaults to "medium" per locked decision
- Source tag is always "ctx-meeting-processor"
- Entry detail format: "meeting-{date}-{company-slug}" or "contact: {firstname-lastname}"
- Group calls: create one contacts.md entry per person, tag each with "Group call with [other names]"
- Same person, different capacity: classify per-call, not per-person. An advisor in one call may be a customer contact in another.

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
| 2.3 | 2026-03-14 | Added incremental fetch filter (Step 0.5) with processed-meetings.jsonl tracker; explicit Granola MCP tool mapping (list_meetings, get_meetings for AI summary, get_meeting_transcript for verbatim); Granola AI summary preserved in archive alongside transcript |
| 2.2 | 2026-03-13 | Replaced hardcoded context file lists with context-aware: true; removed phantom meeting_processor.py and context_utils.py engine references |
| 2.1 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
