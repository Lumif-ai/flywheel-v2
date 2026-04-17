---
public: true
name: broker-draft-recommendation
version: "1.0"
web_tier: 3
description: Pre-check comparison data, call POST /draft-recommendation, and display the recommendation narrative with recommended carrier highlighted
context-aware: true
triggers:
  - /broker:draft-recommendation
tags:
  - broker
  - insurance
  - recommendation
  - quote
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:draft-recommendation — Generate Client Recommendation Narrative

Pre-check that comparison data is ready, then call the backend to generate and save
a client recommendation narrative with the recommended carrier highlighted.

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
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}\n"
                       "Run: export FLYWHEEL_API_URL=https://... && export FLYWHEEL_API_TOKEN=<jwt>")

print("OK: All dependencies satisfied.")
print(f"API URL: {os.environ.get('FLYWHEEL_API_URL')}")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Inputs

Ask the user for:
- **PROJECT_ID** — UUID of the broker project (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)
- **RECIPIENT_EMAIL** — (optional) Client's email address for the recommendation.
  May be left blank — backend accepts null.

Validate PROJECT_ID using field_validator:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

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
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

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

## Step 5: Call POST /draft-recommendation

Call the backend to generate and persist the recommendation narrative:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
RECIPIENT_EMAIL = "<validated-recipient-email-or-None>"

body = {}
if RECIPIENT_EMAIL:
    body["recipient_email"] = RECIPIENT_EMAIL

print(f"Generating recommendation for project {PROJECT_ID}...")
result = api_client.run(api_client.post(
    f"projects/{PROJECT_ID}/draft-recommendation",
    body
))

rec = result.get("recommendation", result)
```

## Step 6: Display the Recommendation

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

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

After successful recommendation, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Draft Recommendation History
- Project {PROJECT_ID}: recommendation drafted on {today's date}
  - Recommended carrier: {recommended_carrier}
  - Recipient email: {RECIPIENT_EMAIL or 'none'}
  - Recommendation ID: {rec_id}
```

Done. The recommendation narrative has been generated and saved to the database.
View the full draft in the Flywheel web app. Share the recommendation with the client
by sending the draft from the project's recommendation tab.
