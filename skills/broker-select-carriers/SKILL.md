---
public: true
name: broker-select-carriers
version: "1.0"
web_tier: 3
description: Retrieve carrier matches from the backend, split into portal vs email routing buckets, and ask broker to confirm the routing plan
context-aware: true
triggers:
  - /broker:select-carriers
tags:
  - broker
  - insurance
  - carrier
  - routing
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:select-carriers — Retrieve and Route Carrier Matches

Retrieve matched carriers for a project, split them into portal-submission
vs email-submission buckets, print the routing plan, and wait for broker
confirmation before proceeding to the next pipeline step.

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

Validate using field_validator:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import field_validator

PROJECT_ID = "<user-provided-project-id>"
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")
print(f"Validated: project_id={PROJECT_ID}")
```

## Step 3: Call carrier-matches Endpoint

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

print(f"Fetching carrier matches for project {PROJECT_ID}...")
result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/carrier-matches"))
matches = result.get("matches", [])
print(f"Received {len(matches)} carrier match(es).")
```

## Step 4: Split into Routing Buckets

```python
portal_carriers = [m for m in matches if m.get("submission_method") == "portal"]
email_carriers  = [m for m in matches if m.get("submission_method") != "portal"]

print(f"Routing split: {len(portal_carriers)} portal | {len(email_carriers)} email")
```

## Step 5: Print Routing Plan

Print the full routing plan in this format:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/carrier-matches"))
matches = result.get("matches", [])

portal_carriers = [m for m in matches if m.get("submission_method") == "portal"]
email_carriers  = [m for m in matches if m.get("submission_method") != "portal"]

print(f"\nCarrier Routing Plan for Project {PROJECT_ID}")
print("=" * 55)

print(f"\nPortal Submission ({len(portal_carriers)} carrier(s)):")
if portal_carriers:
    for m in portal_carriers:
        name  = m.get("carrier_name", "Unknown")
        score = m.get("match_score", "N/A")
        url   = m.get("portal_url", "N/A")
        print(f"  - {name} | score: {score} | portal: {url}")
else:
    print("  (none)")

print(f"\nEmail Submission ({len(email_carriers)} carrier(s)):")
if email_carriers:
    for m in email_carriers:
        name  = m.get("carrier_name", "Unknown")
        score = m.get("match_score", "N/A")
        days  = m.get("avg_response_days", "N/A")
        print(f"  - {name} | score: {score} | avg_response: {days} days")
else:
    print("  (none)")

print(f"\nTotal: {len(matches)} carrier(s) matched")
```

## Step 6: Print Email Carrier Config IDs for Next Step

Capture carrier_config_ids for the email carriers and print them so the
broker can copy them into `/broker:draft-emails`:

```python
# Extract carrier_config_ids for email submission carriers
email_carrier_config_ids = [
    m.get("carrier_config_id")
    for m in email_carriers
    if m.get("carrier_config_id")
]

print("\nEmail carrier_config_ids for next step (/broker:draft-emails):")
if email_carrier_config_ids:
    print("  " + ", ".join(email_carrier_config_ids))
else:
    print("  (none — all carriers are portal-only or no email carriers matched)")

# Also summarise portal carriers for /broker:fill-portal
portal_carrier_names = [m.get("carrier_name", "Unknown") for m in portal_carriers]
if portal_carrier_names:
    print("\nPortal carriers for /broker:fill-portal:")
    for name in portal_carrier_names:
        print(f"  - {name}")
```

**Save the following structured summary to memory for subsequent pipeline steps:**

```
carrier_routing_plan = {
    "project_id": PROJECT_ID,
    "portal_carriers": [{"name": m.get("carrier_name"), "portal_url": m.get("portal_url")} for m in portal_carriers],
    "email_carrier_config_ids": email_carrier_config_ids,
    "total_matched": len(matches),
}
```

## Step 7: Ask for Broker Confirmation

After printing the routing plan, ask:

> "Proceed with this routing plan? (yes/no)"

Wait for the broker's response before continuing.

- If **yes**: proceed, print "Routing plan confirmed. Next steps:"
  - For portal carriers: "Run `/broker:fill-portal` for each portal carrier listed above."
  - For email carriers: "Run `/broker:draft-emails` with the carrier_config_ids printed above."
- If **no**: ask what adjustment is needed (e.g., exclude a specific carrier, change submission method).

## Step 8: Memory Update

After confirmation, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Carrier Selection History
- Project {PROJECT_ID}: carrier-matches fetched on {today's date}
  - Portal: {count} carrier(s) — {names}
  - Email: {count} carrier(s)
  - email_carrier_config_ids: [{ids}]
  - Broker confirmed routing plan: yes
```

Done. Carrier routing plan confirmed.
To submit via portal: use `/broker:fill-portal`.
To create email drafts: use `/broker:draft-emails` with the carrier_config_ids printed above.
