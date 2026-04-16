---
name: broker-draft-emails
version: "1.0"
description: Call POST /draft-solicitations with carrier_config_ids (UUIDs) to create email solicitation drafts in the database
context-aware: true
triggers:
  - /broker:draft-emails
tags:
  - broker
  - insurance
  - email
  - solicitation
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:draft-emails — Create Email Solicitation Drafts

Call the draft-solicitations endpoint to create email drafts for the selected
email-submission carriers. Requires carrier_config_ids (UUIDs from the
`/broker:select-carriers` output) — NOT carrier names.

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

## Step 3: Call draft-solicitations Endpoint

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
carrier_config_ids = ["<uuid-1>", "<uuid-2>"]  # from validation step

print(f"\nCreating solicitation drafts for project {PROJECT_ID}...")
print(f"Carriers: {len(carrier_config_ids)} email carrier(s)")

body = {"carrier_config_ids": carrier_config_ids}
result = api_client.run(
    api_client.post(f"projects/{PROJECT_ID}/draft-solicitations", body)
)
```

## Step 4: Print Results

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
carrier_config_ids = ["<uuid-1>", "<uuid-2>"]

body = {"carrier_config_ids": carrier_config_ids}
result = api_client.run(
    api_client.post(f"projects/{PROJECT_ID}/draft-solicitations", body)
)

# Result may contain "drafts", "solicitations", or a top-level list
drafts = result.get("drafts", result.get("solicitations", []))
if isinstance(result, list):
    drafts = result

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
    import json
    print("Raw response:", json.dumps(result, indent=2))

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
