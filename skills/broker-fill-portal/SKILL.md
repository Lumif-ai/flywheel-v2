---
public: true
name: broker-fill-portal
version: "1.2"
web_tier: 3
description: Show a data preview for portal submission and delegate portal fill execution to portals/mapfre.py
context-aware: true
triggers:
  - /broker:fill-portal
tags:
  - broker
  - insurance
  - portal
  - automation
  - playwright
assets: []
depends_on: ["broker"]
dependencies:
  python_packages:
    - "flywheel-ai>=0.4.0"
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# /broker:fill-portal — Fill Carrier Portal with Project Data

Show a preview of the project data that will be submitted, confirm with the
broker, then delegate the actual Playwright portal automation to
`flywheel.broker.portals.mapfre`.

> **NOTE: This step requires an interactive browser session (headless=False).**
> It will pause for the broker to manually log in to the carrier portal.
> This step CANNOT be fully automated — broker login is always manual.

## Step 1: Dependency Check

```python
import os
from flywheel.broker import api_client
missing = []
# Auth: api_client.py auto-reads ~/.flywheel/credentials.json (written by `flywheel login`)
creds_file = os.path.expanduser("~/.flywheel/credentials.json")
if not os.path.exists(creds_file):
    missing.append("~/.flywheel/credentials.json (run: flywheel login)")

try:
    import playwright
except ImportError:
    missing.append("playwright (run: pip install playwright && playwright install chromium)")

# Namespace probe: flywheel-ai ships the mapfre portal as a pip module
from importlib.util import find_spec as _find_spec
if _find_spec("flywheel.broker.portals.mapfre") is None:
    missing.append("flywheel.broker.portals.mapfre (run: pip install --upgrade flywheel-ai)")
if missing:
    raise RuntimeError(
        f"Missing required dependencies: {', '.join(missing)}\n"
        "Resolve the above before running fill-portal."
    )

print("OK: All dependencies satisfied.")
print("mapfre portal importable: flywheel.broker.portals.mapfre")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Input

Ask the user for:
- **PROJECT_ID** — UUID of the broker project
- **Carrier portal** — currently only Mapfre is supported; confirm with the broker:
  > "Which carrier portal are you filling? (Currently supported: Mapfre)"

```python
import os
from flywheel.broker import field_validator
PROJECT_ID = "<user-provided-project-id>"
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")

CARRIER = "mapfre"  # Set from broker's answer; normalise to lowercase
print(f"Validated: project_id={PROJECT_ID}, carrier={CARRIER}")
```

## Step 3: Fetch and Display Data Preview

Retrieve the project data that will be submitted to the portal:

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"

project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
client_name   = project.get("client_name", "Unknown client")
project_name  = project.get("name", "Unnamed project")
coverages     = project.get("coverages", [])
required_limits = [
    {
        "type": c.get("coverage_type"),
        "required": c.get("required_limit"),
        "unit": c.get("limit_unit", "EUR"),
    }
    for c in coverages
    if c.get("required_limit")
]

print(f"\nData Preview — {CARRIER.upper()} Portal Fill")
print("=" * 50)
print(f"Client:  {client_name}")
print(f"Project: {project_name}")
print(f"Project ID: {PROJECT_ID}")
print(f"\nCoverage types to submit ({len(required_limits)}):")
for r in required_limits:
    print(f"  - {r['type']}: {r['required']:,} {r['unit']}")
if not required_limits:
    print("  (no required limits found — run /broker:parse-contract first)")
```

## Step 4: Ask Broker to Confirm

After displaying the preview, ask:

> "Confirm portal fill for **{CARRIER_NAME}** / **{project_name}**? (yes/no)"

Wait for the broker's response.

- If **no**: Stop. Ask what needs to be corrected before proceeding.
- If **yes**: Proceed to Step 5.

## Step 5: Delegate to portals/mapfre.py

When the broker confirms, instruct:

> "Now follow the instructions in `flywheel.broker.portals.mapfre`.
> Read that file and execute it for PROJECT_ID = {PROJECT_ID}."

This delegates all Playwright automation to the Phase 134 implementation.
Do not duplicate the browser-automation steps here.

The broker will need to:
1. Watch the browser window open (headless=False).
2. Log in to the Mapfre portal when prompted — the script will pause.
3. Confirm in the terminal once logged in so the script can continue filling fields.

## Step 6: Report Outcome

After the broker confirms the portal fill is complete, report:

```
Portal fill complete.
  Carrier:    {CARRIER_NAME}
  Project ID: {PROJECT_ID}
  Screenshot: /tmp/mapfre_filled_{timestamp}.png

Next step: Run /broker:draft-emails to create email solicitation drafts
for the remaining email-submission carriers.
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
        "## fill-portal -- {today}\n"
        "- Project {PROJECT_ID}: {carrier} portal filled for project {PROJECT_ID} ({n_coverages} coverages)\n"
    ),
)
```

Do NOT append to any local file -- the context store is the durable home for skill memory.

