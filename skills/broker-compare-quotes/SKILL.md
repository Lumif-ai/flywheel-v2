---
public: true
name: broker-compare-quotes
version: "1.2"
web_tier: 3
description: Quote comparison workflow — from received quote PDFs to client recommendation
context-aware: true
triggers:
  - /broker:compare-quotes
tags:
  - broker
  - insurance
  - pipeline
  - quotes
  - comparison
assets: []
depends_on: ["broker"]
dependencies:
  skills:
    - broker-extract-quote
    - broker-draft-recommendation
  files:
    - "~/.claude/skills/broker/api_client.py"
---

# Broker Pipeline: compare-quotes

> **Version:** 1.0 | **Last Updated:** 2026-04-15
> **Changelog:** Phase 135 — initial pipeline implementation

This pipeline chains 3 steps to extract received carrier quote PDFs, compare them via the
backend comparison endpoint, and generate a client recommendation draft. The sentinel is active
during quote extraction writes and deactivated before the comparison read and recommendation draft.

---

## Pipeline Announcement

When `/broker:compare-quotes` is triggered, announce:

```
Starting compare-quotes pipeline. This chains 3 steps:
extract-quote (for each received PDF) → comparison → draft-recommendation
```

---

## Inputs

Ask the broker for the following before starting:

1. **PROJECT_ID** — UUID of the broker project
2. **How many quote PDFs** do you need to process? (Enter a number)

Then for each quote PDF, ask for the absolute path. (Collect all paths upfront before starting.)

Validate that PROJECT_ID matches UUID format before proceeding.

---

## Activate Pipeline Sentinel

After collecting inputs, activate the pipeline mode sentinel:

```python
import os
os.environ["BROKER_PIPELINE_MODE"] = "1"
print("Pipeline mode ON")
```

This suppresses the quote-write hook so it does not call the comparison endpoint prematurely
while quote records are still being extracted.

---

## Step 1 — extract-quote (repeat for each PDF)

For each quote PDF, execute:

```
Now executing Step 1 (quote {N} of {total}): extract-quote.
Follow the instructions in ~/.claude/skills/broker-extract-quote/SKILL.md
for PROJECT_ID={project_id} and PDF_PATH={pdf_path}.
```

**v1.2 Pattern 3a note:** `broker-extract-quote` v1.2 runs the text extraction
in THIS conversation via `broker_api.extract_quote_extraction` →
inline-analyze → `broker_api.save_quote_extraction` (no backend LLM call,
no polling). The pipeline sentinel + sequencing below are unchanged — only
the per-PDF step internals changed.

After each extraction, confirm success (extracted premium, carrier matched) before proceeding
to the next PDF. If extraction fails for a quote, ask the broker whether to skip it or retry.

---

## Deactivate Pipeline Sentinel

After all quote PDFs have been extracted, deactivate the sentinel:

```python
import os
os.environ.pop("BROKER_PIPELINE_MODE", None)
print("Pipeline mode OFF — running comparison")
```

---

## Step 2 — comparison (inline)

Call the comparison endpoint directly (this is not a separate step skill):

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

comparison = api_client.run(api_client.get(f"projects/{project_id}/comparison"))
carriers = comparison.get("carriers", [])
```

Print a compact comparison matrix:

```
Quote Comparison for Project {project_id}
=========================================
Carrier Name       | Total Premium | Coverages | Exclusions | Status
{carrier_name}     | ${premium}    | {N}       | {N}        | {status}
...

Recommended: {recommended_carrier}
Recommendation basis: {reason from comparison response}
```

If the comparison endpoint returns an error or incomplete data (fewer carriers than expected),
warn the broker:

```
WARNING: Comparison returned {N} carriers but {M} quotes were extracted.
Some carriers may not be ready. Proceeding to draft-recommendation with available data.
```

---

## Step 3 — draft-recommendation

Execute:

```
Now executing Step 3: draft-recommendation.
Follow the instructions in ~/.claude/skills/broker-draft-recommendation/SKILL.md
for PROJECT_ID={project_id}.
```

**v1.2 Pattern 3a note:** `broker-draft-recommendation` v1.2 runs the
narrative drafting in THIS conversation via
`broker_api.extract_recommendation_draft` → inline-analyze →
`broker_api.save_recommendation_draft`. Same recommendation row written to
the same DB, backend makes zero LLM calls. No observable change for the
broker — the draft shows up in the same recommendations tab as before.

### Why this is different from v1.1

v1.1 chained two server-side Anthropic calls (quote extraction +
recommendation narrative) through the backend's subsidy key. v1.2 keeps the
pipeline shape but has THIS conversation run both steps inline via
Pattern 3a helpers. Same outputs, same DB rows, zero backend LLM spend.
See `skills/broker/MIGRATION-NOTES.md` for the full v1.1 → v1.2 migration
record.

Wait for the draft creation confirmation.

---

## Pipeline Complete Summary

After Step 3 completes, print:

```
Compare-Quotes Pipeline Complete
=================================
Project:              {project_id}
Quotes processed:     {N}
Recommended carrier:  {recommended_carrier}
Recommendation draft: saved to database

Next step: Review and send the recommendation in the Flywheel web app
```

---

## Memory Update (Standard 1)

After pipeline completion, append to `~/.claude/skills/broker/auto-memory/broker.md`:

```
[{date}] compare-quotes pipeline completed for project {project_id}.
Quotes processed: {N}. Recommended: {recommended_carrier}.
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| extract-quote fails for one PDF | Ask broker to skip or retry; continue with remaining PDFs |
| All extractions fail | Deactivate sentinel and abort with actionable error |
| Comparison endpoint returns 0 carriers | Warn broker — data may not be ready; suggest waiting and re-running |
| PROJECT_ID invalid | Fail immediately before activating sentinel |
| draft-recommendation fails | Report error; all quotes are still saved — broker can re-run `/broker:draft-recommendation` standalone |
