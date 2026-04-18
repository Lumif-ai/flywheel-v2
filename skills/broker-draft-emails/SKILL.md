---
public: true
name: broker-draft-emails
version: "1.2"
web_tier: 3
description: Draft carrier solicitation emails via Pattern 3a (extract_solicitation_draft → Claude-inline → save_solicitation_draft), one per carrier_config_id, and persist to the database
context-aware: true
triggers:
  - /broker:draft-emails
tags:
  - broker
  - insurance
  - email
  - solicitation
assets: []
depends_on: ["broker"]
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# /broker:draft-emails — Create Email Solicitation Drafts

Draft email solicitations for the selected email-submission carriers via the
Pattern 3a flow: for each carrier, fetch the extract prompt + tool_schema,
analyze inline, then persist the draft. Requires carrier_config_ids (UUIDs
from the `/broker:select-carriers` output) — NOT carrier names.

> **NOTE: This endpoint requires `carrier_config_id` UUIDs (from the
> `/carrier-matches` response), not carrier names. Using names will cause
> 422 Unprocessable Entity errors.**
>
> The correct IDs were printed by `/broker:select-carriers` in the
> "Email carrier_config_ids for next step" section.

## Step 1: Dependency Check

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator
import httpx

missing = []
if not os.environ.get("FLYWHEEL_API_URL"):
    missing.append("FLYWHEEL_API_URL")
if not os.environ.get("FLYWHEEL_API_TOKEN"):
    missing.append("FLYWHEEL_API_TOKEN")
try:
    import httpx
except ImportError:
    missing.append("httpx (run: pip install httpx)")

if missing:
    raise RuntimeError(
        f"Missing required dependencies: {', '.join(missing)}\n"
        "Run: export FLYWHEEL_API_URL=https://... && export FLYWHEEL_API_TOKEN=<jwt>"
    )

print("OK: All dependencies satisfied.")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Input

Ask the user for:
- **PROJECT_ID** — UUID of the broker project
- **CARRIER_CONFIG_IDS** — comma-separated list of carrier_config_id UUIDs
  (these were printed by `/broker:select-carriers`)

Validate both inputs:

```python
import sys, os, uuid
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import field_validator

PROJECT_ID = "<user-provided-project-id>"
CARRIER_CONFIG_IDS_RAW = "<user-provided-comma-separated-uuids>"

# Validate project ID
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")

# Parse and validate carrier_config_ids
raw_ids = [cid.strip() for cid in CARRIER_CONFIG_IDS_RAW.split(",") if cid.strip()]
if not raw_ids:
    raise ValueError("CARRIER_CONFIG_IDS must be a non-empty list of UUID strings.")

carrier_config_ids = []
for raw_id in raw_ids:
    try:
        # Validate UUID format
        uuid.UUID(raw_id)
        carrier_config_ids.append(raw_id)
    except ValueError:
        raise ValueError(
            f"Invalid carrier_config_id: '{raw_id}'\n"
            "carrier_config_ids must be UUIDs (e.g. 'a1b2c3d4-...'). "
            "Do NOT use carrier names — use the UUIDs printed by /broker:select-carriers."
        )

print(f"Validated: project_id={PROJECT_ID}")
print(f"Validated: {len(carrier_config_ids)} carrier_config_id(s)")
for cid in carrier_config_ids:
    print(f"  - {cid}")
```

## Step 3: Draft Solicitation Emails via Pattern 3a (one per carrier)

v1.2 (Phase 150.1) drafts each solicitation email in THIS conversation using
the prompt + tool_schema the backend returns **per carrier**. The legacy
v1.1 endpoint accepted a list of carriers and drafted all of them
server-side with Anthropic; v1.2 loops client-side so the backend stays
zero-LLM.

For each carrier_config_id, call `extract_solicitation_draft` → analyze
inline → `save_solicitation_draft`.

### 3a. Per-carrier: fetch prompt + tool_schema + context docs

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
carrier_config_ids = ["<uuid-1>", "<uuid-2>"]  # from validation step

drafts = []
for cid in carrier_config_ids:
    print(f"\n--- Drafting solicitation for carrier_config_id={cid} ---")
    extract = api_client.run(
        api_client.extract_solicitation_draft(PROJECT_ID, cid)
    )
    # extract = {prompt, tool_schema, documents, metadata}
    print(f"  prompt: {len(extract['prompt'])} chars")
    print(f"  tool: {extract['tool_schema'].get('name', 'unknown')}")
    print(f"  documents: {len(extract['documents'])} context PDF(s)")

    # 3b. Analyze inline: YOU (Claude) run the drafting.
    # Use extract["prompt"] as the system message and extract["tool_schema"]
    # as the single tools= entry. Expected tool-use output keys (from
    # draft_solicitation_email schema): subject (str), body_html (str).
    #
    # Replace these placeholders with what YOU generated for this carrier:
    analysis = {
        "subject": "",                                    # from tool_use.input.subject
        "body_html": "",                                  # from tool_use.input.body_html
        "tool_schema_version": extract["metadata"]["tool_schema_version"],
    }

    # 3c. Persist (zero LLM calls server-side).
    save_result = api_client.run(
        api_client.save_solicitation_draft(PROJECT_ID, cid, analysis)
    )
    drafts.append(save_result)
    print(f"  saved: subject=\"{analysis['subject'][:60]}...\" "
          f"id={save_result.get('id', save_result.get('solicitation_id', 'n/a'))}")
```

### Why this is different from v1.1

v1.1 had a single `POST /projects/{id}/draft-solicitations` endpoint that
accepted a list of carrier_config_ids and called Anthropic server-side
(once per carrier) with the backend's subsidy key. v1.2 returns the SAME
prompt + SAME tool_schema per carrier and has THIS conversation's Claude
draft each email inline, looping client-side. Net behavior identical to the
broker: same subjects, same body_html shape, drafts saved to the same DB
rows. Backend cost = zero LLM calls. Details in
`skills/broker/MIGRATION-NOTES.md`.

## Step 4: Print Results

```python
print(f"\nCreated {len(drafts)} solicitation draft(s):")
for draft in drafts:
    carrier_name = draft.get("carrier_name", draft.get("carrier", "Unknown carrier"))
    subject      = draft.get("subject", draft.get("email_subject", "(no subject)"))
    draft_id     = draft.get("id", draft.get("solicitation_id", ""))
    print(f"  - {carrier_name}: subject: \"{subject}\"")
    if draft_id:
        print(f"    id: {draft_id}")

if not drafts:
    print("  (no drafts returned — check the API response for details)")

print("\nDrafts saved to database. View them in the Flywheel web app under Solicitations.")
```

## Step 5: Memory Update

After drafts are created, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Email Draft History
- Project {PROJECT_ID}: {N} draft(s) created on {today's date}
  - Carrier config IDs used: [{ids}]
  - Drafts: {carrier_name_1}, {carrier_name_2}, ...
```

Done. Email solicitation drafts have been created.
View and send them in the Flywheel web app under Solicitations.
