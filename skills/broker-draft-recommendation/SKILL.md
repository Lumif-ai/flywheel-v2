---
public: true
name: broker-draft-recommendation
version: "1.2"
web_tier: 3
description: Pre-check comparison data, draft the recommendation narrative via Pattern 3a (extract_recommendation_draft → Claude-inline → save_recommendation_draft), and display the narrative with recommended carrier highlighted
context-aware: true
triggers:
  - /broker:draft-recommendation
tags:
  - broker
  - insurance
  - recommendation
  - quote
assets: []
depends_on: ["broker"]
dependencies:
  python_packages:
    - "flywheel-ai>=0.4.0"
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# /broker:draft-recommendation — Generate Client Recommendation Narrative

Pre-check that comparison data is ready, then call the backend to generate and save
a client recommendation narrative with the recommended carrier highlighted.

## Step 1: Dependency Check

```python
import os
from flywheel.broker import api_client, field_validator
import httpx

missing = []
# Auth: api_client.py auto-reads ~/.flywheel/credentials.json (written by `flywheel login`)
creds_file = os.path.expanduser("~/.flywheel/credentials.json")
if not os.path.exists(creds_file):
    missing.append("~/.flywheel/credentials.json (run: flywheel login)")
if missing:
    raise RuntimeError(f"Missing dependencies: {', '.join(missing)}\n"
                       "If auth is missing, run: flywheel login")

print("OK: All dependencies satisfied.")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Inputs

Ask the user for:
- **PROJECT_ID** — UUID of the broker project (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)
- **RECIPIENT_EMAIL** — (optional) Client's email address for the recommendation.
  May be left blank — backend accepts null.

Validate PROJECT_ID using field_validator:

```python
import os
from flywheel.broker import api_client, field_validator
# Replace with actual user-provided values
PROJECT_ID = "<user-provided-project-id>"
RECIPIENT_EMAIL = "<user-provided-email-or-blank>"

# Validate project ID
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")

# Normalize recipient email — treat blank/none as null
if not RECIPIENT_EMAIL or RECIPIENT_EMAIL.strip() == "":
    RECIPIENT_EMAIL = None

print(f"Validated: project_id={PROJECT_ID}")
print(f"Recipient email: {RECIPIENT_EMAIL or '(none — will be omitted)'}")
```

## Step 3: Pre-Check Comparison Data

Fetch the comparison data to confirm all quotes are extracted and ready before generating
the recommendation narrative:

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"

print(f"Fetching comparison data for project {PROJECT_ID}...")
comparison = api_client.run(api_client.get(f"projects/{PROJECT_ID}/comparison"))

carriers = comparison.get("carriers", comparison.get("quotes", []))
recommended_carrier = comparison.get("recommended_carrier", comparison.get("recommendation", "TBD"))
is_partial = comparison.get("partial", comparison.get("is_partial", False))

print(f"Comparison data found: {len(carriers)} carrier(s)")
print(f"Recommended carrier: {recommended_carrier}")

if is_partial or len(carriers) == 0:
    print()
    print("NOTE: Comparison data is incomplete. Run /broker:extract-quote for all pending")
    print("quotes before drafting a recommendation.")
    print()
    print("You may continue, but the recommendation may be based on partial data.")
elif len(carriers) > 0:
    print(f"\nAll {len(carriers)} carrier(s) ready for recommendation.")
    for c in carriers:
        if isinstance(c, dict):
            name = c.get("carrier_name", c.get("carrier", str(c)))
            status = c.get("status", "ready")
            print(f"  - {name}: {status}")
```

## Step 4: Confirm Before Proceeding

Ask the broker to confirm before making the API call:

```
"Draft recommendation for project {PROJECT_ID}? (yes/no)"
```

If the broker answers "no" or anything other than "yes" / "y", stop and exit cleanly:

```python
answer = "<user-provided-confirmation>"
if answer.lower().strip() not in ("yes", "y"):
    print("Aborted. No recommendation was created.")
    raise SystemExit(0)
```

## Step 5: Draft Recommendation via Pattern 3a (Claude-in-conversation)

v1.2 (Phase 150.1) runs the recommendation-narrative drafting in THIS
conversation using the prompt + tool_schema the backend returns. The backend
owns prompt assembly (comparison summary + project context + taxonomy) and
persistence; it does NOT call Anthropic.

### 5a. Fetch prompt + tool_schema + context

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"
RECIPIENT_EMAIL = "<validated-recipient-email-or-None>"

print(f"Fetching recommendation prompt for project {PROJECT_ID}...")
extract = api_client.run(api_client.extract_recommendation_draft(PROJECT_ID))
# extract = {prompt, tool_schema, documents, metadata}
print(f"  prompt: {len(extract['prompt'])} chars")
print(f"  tool: {extract['tool_schema'].get('name', 'unknown')}")
print(f"  tool_schema_version: {extract['metadata']['tool_schema_version']}")
```

### 5b. Analyze inline using the returned prompt + tool_schema

**YOU (Claude) now draft the recommendation narrative.** Use
`extract["prompt"]` as the system message — it contains the full comparison
summary, project context, and narrative guidelines — and
`extract["tool_schema"]` as the single `tools=` entry. If
`extract["documents"]` has attachments (supporting policy PDFs), decode
`pdf_base64` and attach via the Anthropic document content-block protocol.

Expected tool-use output keys (from `draft_recommendation_email` schema):
`subject` (str), `body_html` (str, rich client-facing narrative),
`recipient_email` (optional — override the Step 2 input if the prompt
recommends a different stakeholder).

### 5c. Persist the draft

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"
RECIPIENT_EMAIL = "<validated-recipient-email-or-None>"

analysis = {
    "subject": "",                                       # from tool_use.input.subject
    "body_html": "",                                     # from tool_use.input.body_html
    "tool_schema_version": extract["metadata"]["tool_schema_version"],
}
if RECIPIENT_EMAIL:
    analysis["recipient_email"] = RECIPIENT_EMAIL

print(f"Persisting recommendation draft for project {PROJECT_ID}...")
result = api_client.run(api_client.save_recommendation_draft(PROJECT_ID, analysis))

rec = result.get("recommendation", result)
```

### Why this is different from v1.1

v1.1 called `POST /projects/{id}/draft-recommendation` which ran Anthropic
server-side with the backend's subsidy key to generate the narrative, then
persisted. v1.2 returns the SAME prompt (comparison summary, project
context, narrative guidelines) + SAME tool_schema and has THIS conversation
write the narrative. Same recommendation row, same subject + body_html
shape, backend cost = zero LLM calls. Details in
`skills/broker/MIGRATION-NOTES.md`.

## Step 6: Display the Recommendation

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"

# result already fetched in Step 5
rec = result.get("recommendation", result)

recommended_carrier = rec.get("recommended_carrier", rec.get("carrier", "N/A"))
narrative = rec.get("narrative", rec.get("reasoning", ""))
coverage_summary = rec.get("coverage_summary", "")
critical_findings = rec.get("critical_findings", rec.get("findings", "None"))
rec_id = rec.get("id", "N/A")

# Truncate narrative for display — full narrative saved to DB
narrative_preview = (narrative[:500] + "...") if len(narrative) > 500 else narrative

print()
print("Recommendation Draft Created")
print("============================")
print(f">>> Recommended Carrier: {recommended_carrier} <<<")
print()
print(f"Reasoning:")
print(f"  {narrative_preview}")
print()

if coverage_summary:
    print("Coverage Summary:")
    print(f"  {coverage_summary}")
    print()

print("Critical Findings:")
if critical_findings and critical_findings != "None":
    if isinstance(critical_findings, list):
        for finding in critical_findings:
            print(f"  - {finding}")
    else:
        print(f"  {critical_findings}")
else:
    print("  None")

print()
print(f"Recommendation ID: {rec_id}")
print("Status: Saved to database. View full draft in Flywheel web app.")
if RECIPIENT_EMAIL:
    print(f"Recipient: {RECIPIENT_EMAIL}")
```

## Step 7: Memory Update

After this step succeeds, persist a session summary to the Flywheel context store
via the MCP tool `mcp__flywheel__flywheel_write_context`:

- `file_name="broker"`
- `content` = a short markdown summary of what was done (project id, key metrics,
  and the skill-specific signals -- see example below)

Example call shape:

```python
mcp__flywheel__flywheel_write_context(
    file_name="broker",
    content=(
        "## draft-recommendation -- {today}\n"
        "- Project {PROJECT_ID}: recommendation drafted ranking {n_quotes} quotes for project {PROJECT_ID}\n"
    ),
)
```

Do NOT append to any local file -- the context store is the durable home for skill memory.

