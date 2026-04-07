---
name: gtm-pipeline
version: "2.1"
description: >
  Context-aware GTM pipeline with bidirectional context store feedback.
  Reads enriched context from 7 context files for outreach personalization,
  and writes outreach-discovered data back to the context store.
context-aware: true
triggers:
  - "run GTM pipeline"
  - "enrich outreach"
  - "outreach with context"
  - "pipeline run"
  - "write back outreach results"
  - "GTM feedback loop"
tags:
  - gtm
  - pipeline
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
output:
  - context-store-writes
  - pipeline-report
web_tier: 2
---

# gtm-pipeline

You are running the **flywheel-powered** bidirectional GTM pipeline. Your job is to read enriched context from the context store to personalize outreach, then write discoveries from outreach back to the context store -- closing the GTM feedback loop.

**Trigger phrases:** "run GTM pipeline", "enrich outreach", "outreach with context", "pipeline run", "write back outreach results", "GTM feedback loop", or any reference to context-enriched outreach or writing outreach outcomes back to the context store.

---

## Step 0a: Dependency Check
- Verify: Playwright MCP tools (`browser_navigate`), Python 3, `~/.claude/skills/_shared/engines/gtm_pipeline.py`, context store catalog (`~/.claude/context/_catalog.md`).
- Verify sub-skills installed: `gtm-web-scraper-extractor`, `gtm-company-fit-analyzer`, `gtm-outbound-messenger` SKILL.md files exist in `~/.claude/skills/`.
- If Playwright missing: "Connect Playwright MCP and restart Claude Code."
- If any sub-skill missing: name which one and how to install it.
- Block if Playwright or any sub-skill is missing.

### Input Validation
- Verify: at least one target URL or company name provided before starting pipeline.
- Verify: if resuming, scored CSV path exists and is readable.
- For outreach phase: confirm scored CSV has `Fit_Score` and `Fit_Tier` columns before handing off to messenger.
- For batches >50 companies: confirm scope with user before proceeding.

---

### Checkpoint Protocol
- Save to `~/.claude/gtm-stack/pipeline_context_status.md` every 10 items
- At startup: check for existing status file, offer resume
- Include: phase (context-read/enrich/capture/write-back), items completed, items remaining, partial results

## Step 1: Load Context

Read the full context store snapshot and build the outreach enrichment summary.

Programmatically, pre-read via:
```
python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags sales,outreach,people,competitors --json
```

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared/engines"))
from gtm_pipeline import (
    pre_read_context, find_contact_context, synthesize_outreach_context,
    format_outcome_entry, write_outreach_outcomes, generate_pipeline_report,
    READ_TARGETS, WRITE_TARGETS
)

# Snapshot all context files
context_snapshot = pre_read_context("gtm-pipeline")
print(f"Loaded {len(context_snapshot)} context files")

# Build the outreach enrichment summary
outreach_summary = synthesize_outreach_context(context_snapshot)
print(outreach_summary)
```

Show the user the outreach summary. This is the flywheel proof -- all previous meetings, company profile work, and enrichment data compiled into a single personalization brief.

If a specific contact or company is being targeted, also run:

```python
contact_context = find_contact_context("Contact Name", "Company Name", context_snapshot)
for filename, lines in contact_context.items():
    print(f"\n{filename}:")
    for line in lines[:5]:
        print(f"  {line}")
```

## Step 2: Enrich Outreach

Use the synthesized context to personalize outreach messaging:

- **Pain points** that resonate with the prospect's industry or role
- **Positioning angles** backed by competitive intelligence
- **Known objections** with prepared counter-arguments
- **Prior interactions** with the contact or company (if any)
- **ICP fit signals** to tailor the value proposition

The enrichment summary from Step 1 provides all the ammunition. Reference specific data points (evidence counts, confidence levels) to prioritize which angles are strongest.

## Step 3: Capture Outcomes

After outreach is complete, collect new data discovered during the interaction. For each discovery, format an entry:

### New contacts discovered

```python
contact_entry = format_outcome_entry(
    outcome_type="new-contact",
    content_lines=[
        "Name: [contact name]",
        "Role: [role/title]",
        "Company: [company name]",
        "Source: outreach on [date] -- referred by [referrer]",
    ],
    detail="outreach-new-contact",
)
```

### New objections heard

```python
objection_entry = format_outcome_entry(
    outcome_type="new-objection",
    content_lines=[
        "Objection: [what the prospect said]",
        "Context: [situation where objection arose]",
        "Possible response: [if any counter-argument was used]",
    ],
    detail="outreach-new-objection",
)
```

### Validated insights

```python
insight_entry = format_outcome_entry(
    outcome_type="validated-insight",
    content_lines=[
        "Insight: [what was confirmed/learned]",
        "Source: outreach response from [prospect/company]",
        "Implication: [what this means for strategy]",
    ],
    detail="outreach-validated-insight",
)
```

All outcome entries start with confidence "low" (single observation). Evidence counting and confidence upgrades happen automatically through the context store deduplication system.

## Step 4: Write Back

Write all discovered outcomes back to the context store:

```python
outcomes_by_file = {}

# Add entries for each file that has new data
if contact_entry:
    outcomes_by_file["contacts.md"] = contact_entry
if objection_entry:
    outcomes_by_file["objections.md"] = objection_entry
if insight_entry:
    outcomes_by_file["insights.md"] = insight_entry

write_results = write_outreach_outcomes(outcomes_by_file, "gtm-pipeline")
for filename, result in write_results.items():
    print(f"  {filename}: {result}")
```

Programmatically, append entries via:
```
python3 ~/.claude/skills/_shared/context_utils.py append [file] --source gtm-pipeline --detail "[tag]" --content "[lines]"
```

Individual writes per file. Partial success is acceptable -- if one file fails, the others still complete.

## Step 5: Report

Generate and display the pipeline report:

```python
report = generate_pipeline_report(context_snapshot, write_results)
print(report)
```

The report shows what context was consumed and what was written back -- proof that the feedback loop is working.

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-pipeline.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Preferred outreach tone and style
- Scoring thresholds and tier cutoffs
- Target verticals and industry preferences
- Template choices and approved messaging
- Contact segments that respond best to certain positioning angles
- Objection patterns and most effective counter-arguments
- Which pain points resonate most by industry/role

### What NOT to save
- Session-specific content, temporary overrides, confidential data

### Parallel Execution
For multi-source pipeline runs (2+ sources):
- Sources can be scraped in parallel (independent operations)
- Scoring is sequential per source (depends on scrape output)
- Use `~/.claude/skills/gtm-shared/parallel.py` for batch planning when available

| Phase | Parallelizable | Notes |
|-------|---------------|-------|
| Scraping | Yes | Each source independent |
| Scoring | Per-source | Depends on scrape output |
| Logging | Sequential | Append to pipeline-runs.json |
| Dashboard | After all | Runs once at end |

### Idempotency
- Each pipeline run gets a unique run ID (YYYYMMDD_HHMMSS format) -- never collides
- Scored CSVs use run ID in filename -- re-runs create new files, don't overwrite
- `pipeline-runs.json`: append-only log, duplicate run IDs checked before write
- Master workbook merge is idempotent -- company key (name+domain) deduplicates
- Dashboard regeneration is safe to repeat (overwrites single HTML file)

### Context Management
For large pipeline runs (50+ leads):
- Process in batches of 25 for scoring
- Checkpoint after each batch to scored CSV (partial results preserved)
- Keep running totals (companies scored, fit distribution) rather than full lead list in context
- Final summary aggregates from CSV files, not from memory

### Backup Protocol
- Before merging to master workbook: `gtm_utils.backup_file()` creates `.backup.YYYY-MM-DD`
- Before dashboard regeneration: backup existing HTML, keep last 3
- `pipeline-runs.json`: append-only (no destructive operations)
- Scored CSVs: new file per run (never overwritten)
- Context store writes: backup target file before modification

## Error Handling

- **Context store read failure:** Continue with available data; partial reads are acceptable.
- **Write-back failure:** Log error with filename, continue writing other files (independent writes).
- **Empty context store:** Warn user, suggest running `/gtm-my-company` first to populate positioning data.
- **Sub-skill failure (scraper/scorer/messenger):** Save all progress to CSV, report which phase failed and at what point, offer to resume from the failed phase.
- **Partial pipeline completion:** If scraping succeeds but scoring fails, deliver the scraped CSV. If scoring succeeds but outreach fails, deliver the scored CSV.
- **No outcomes to write:** Skip write-back step, still generate report showing what was read.
- **Duplicate entries:** Context store deduplication handles automatically via `append_entry()`.
- Partial results: save progress incrementally after each phase, never all-at-end.
- Final report includes success/failure counts per phase.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-03-13 | Remove phantom Python engine references, replace hardcoded context list with context-aware flag, fix context_utils reference |
| 2.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |

## Important Notes

- This skill does **NOT** replace `gtm-leads-pipeline` or `gtm-outbound-messenger` -- it enriches the pipeline with context store knowledge and records outcomes
- The outreach tracker CSV (`outreach-tracker.csv`) is owned by `gtm-outbound-messenger` -- read-only access for effectiveness tracking is handled in a separate workflow (Plan 05-02)
- Effectiveness scoring is handled separately (Plan 05-02) -- this skill only captures raw outcomes
- All context store writes follow the entry format in `~/.claude/skills/_shared/context-protocol.md`
- Outcome entries start at confidence "low" -- confidence upgrades happen based on evidence accumulation

## Flywheel MCP Integration

When connected to the Flywheel MCP server, orchestrate the GTM pipeline using lead data:

### Pipeline orchestration:
1. Use `flywheel_list_leads(pipeline_stage="scraped")` to find leads needing scoring
2. Use `flywheel_list_leads(pipeline_stage="scored", fit_tier="Strong Fit")` to find leads needing research
3. Use `flywheel_list_leads(pipeline_stage="researched")` to find leads needing outreach drafts
4. Use `flywheel_list_leads(pipeline_stage="drafted")` to find leads ready to send
5. Use `flywheel_list_leads(pipeline_stage="sent")` to check for replies

Each sub-skill (scraper, scorer, researcher, drafter, sender) should use its own MCP integration to persist results.
If Flywheel MCP is not connected, fall back to local file-based pipeline orchestration.
