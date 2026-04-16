---
name: broker-fill-portal
version: "1.0"
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
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/portals/mapfre.py"
---

# /broker:fill-portal — Fill Carrier Portal with Project Data

Show a preview of the project data that will be submitted, confirm with the
broker, then delegate the actual Playwright portal automation to
`~/.claude/skills/broker/portals/mapfre.py`.

> **NOTE: This step requires an interactive browser session (headless=False).**
> It will pause for the broker to manually log in to the carrier portal.
> This step CANNOT be fully automated — broker login is always manual.

## Step 1: Dependency Check

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

missing = []
if not os.environ.get("FLYWHEEL_API_URL"):
    missing.append("FLYWHEEL_API_URL")
if not os.environ.get("FLYWHEEL_API_TOKEN"):
    missing.append("FLYWHEEL_API_TOKEN")

try:
    import playwright
except ImportError:
    missing.append("playwright (run: pip install playwright && playwright install chromium)")

mapfre_path = os.path.expanduser("~/.claude/skills/broker/portals/mapfre.py")
if not os.path.exists(mapfre_path):
    missing.append(f"portals/mapfre.py not found at {mapfre_path}")

if missing:
    raise RuntimeError(
        f"Missing required dependencies: {', '.join(missing)}\n"
        "Resolve the above before running fill-portal."
    )

print("OK: All dependencies satisfied.")
print(f"mapfre.py found at: {mapfre_path}")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Input

Ask the user for:
- **PROJECT_ID** — UUID of the broker project
- **Carrier portal** — currently only Mapfre is supported; confirm with the broker:
  > "Which carrier portal are you filling? (Currently supported: Mapfre)"

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import field_validator

PROJECT_ID = "<user-provided-project-id>"
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")

CARRIER = "mapfre"  # Set from broker's answer; normalise to lowercase
print(f"Validated: project_id={PROJECT_ID}, carrier={CARRIER}")
```

## Step 3: Fetch and Display Data Preview

Retrieve the project data that will be submitted to the portal:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

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

> "Now follow the instructions in `~/.claude/skills/broker/portals/mapfre.py`.
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

Update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Portal Fill History
- Project {PROJECT_ID}: Mapfre portal filled on {today's date}
  - Client: {client_name}
  - Coverages submitted: {count}
  - Screenshot: /tmp/mapfre_filled_{timestamp}.png
```

Done. Portal fill complete.
