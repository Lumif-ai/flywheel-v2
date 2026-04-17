---
public: true
name: broker-extract-quote
version: "1.1"
web_tier: 3
description: Map a carrier quote PDF to an existing quote row, upload the PDF, trigger async extraction, poll until done, and report premium breakdown with critical exclusions
context-aware: true
triggers:
  - /broker:extract-quote
tags:
  - broker
  - insurance
  - quote
  - extraction
  - pdf
assets: []
depends_on: ["broker"]
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:extract-quote — Upload Carrier Quote PDF and Extract Premium Breakdown

Map a carrier quote PDF to an existing quote row in the database, upload the PDF,
trigger async extraction, poll until complete, and print a premium breakdown with
flagged critical exclusions.

**NOTE:** This skill does NOT create a new CarrierQuote row. The quote row must already
exist (brokers create them via the UI or mark-received flow). This skill maps a PDF to
an existing quote and triggers extraction.

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
- **PDF_PATH** — Absolute path to the carrier quote PDF file (e.g. `/Users/me/quotes/hartford.pdf`)

Validate both inputs using field_validator:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

# Replace with actual user-provided values
PROJECT_ID = "<user-provided-project-id>"
PDF_PATH = "<user-provided-pdf-path>"

# Validate
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")
PDF_PATH = field_validator.validate_file_path(PDF_PATH, "PDF_PATH")
print(f"Validated: project_id={PROJECT_ID}, pdf_path={PDF_PATH}")
```

If validation fails, show the error and ask the user to correct the input. Do not proceed.

## Step 3: List Existing Quotes

Fetch existing quotes for the project and display them so the broker can choose which
quote this PDF belongs to:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/quotes"))
quotes = result.get("quotes", [])

if not quotes:
    print(f"ERROR: No quotes found for project {PROJECT_ID}.")
    print("Create quote rows in the Flywheel web app before running this skill.")
    raise SystemExit(1)

# Separate by status — show pending/received first as they are extraction candidates
pending = [q for q in quotes if q.get("status") in ("pending", "received")]
extracted = [q for q in quotes if q.get("status") == "extracted"]
other = [q for q in quotes if q not in pending and q not in extracted]
ordered = pending + other + extracted

all_extracted = len(pending) == 0 and len(extracted) > 0
if all_extracted:
    print(f"WARNING: All quotes for project {PROJECT_ID} already have status 'extracted'.")
    print("Extraction may already be complete for these quotes. Proceeding anyway.\n")

print(f"Existing quotes for project {PROJECT_ID}:")
for idx, q in enumerate(ordered, start=1):
    carrier = q.get("carrier_name", q.get("carrier_id", "Unknown Carrier"))
    status = q.get("status", "unknown")
    quote_id = q.get("id", "N/A")
    marker = " <-- candidate" if q.get("status") in ("pending", "received") else ""
    print(f"  [{idx}] {carrier} | status: {status} | ID: {quote_id}{marker}")
```

## Step 4: Select Quote

Ask the broker which quote this PDF belongs to:

```
"Which quote number does this PDF belong to? (enter number)"
```

Wait for broker to select. Store the selected QUOTE_ID:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/quotes"))
quotes = result.get("quotes", [])

# Build ordered list same as Step 3
pending = [q for q in quotes if q.get("status") in ("pending", "received")]
extracted = [q for q in quotes if q.get("status") == "extracted"]
other = [q for q in quotes if q not in pending and q not in extracted]
ordered = pending + other + extracted

# selection = <user-provided-number>
selection = int("<user-provided-selection>")
if selection < 1 or selection > len(ordered):
    raise ValueError(f"Invalid selection {selection}. Must be between 1 and {len(ordered)}.")

chosen = ordered[selection - 1]
QUOTE_ID = chosen["id"]
CARRIER_NAME = chosen.get("carrier_name", chosen.get("carrier_id", "Unknown Carrier"))
print(f"Selected: {CARRIER_NAME} (ID: {QUOTE_ID})")
```

## Step 5: Upload PDF

Upload the quote PDF to the project's document store:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
PDF_PATH = "<validated-pdf-path>"

print(f"Uploading {os.path.basename(PDF_PATH)} to project {PROJECT_ID}...")
upload_result = api_client.run(api_client.upload_file(PROJECT_ID, PDF_PATH))
files = upload_result.get("files", [])
print(f"Uploaded: {len(files)} file(s) stored.")
for f in files:
    print(f"  - {f.get('filename', f.get('id', 'unknown'))}")
```

## Step 6: Trigger Async Extraction

Call the backend extract endpoint to start async quote extraction for the selected quote:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

QUOTE_ID = "<selected-quote-id>"

print(f"Triggering extraction for quote {QUOTE_ID}...")
trigger = api_client.run(api_client.post(f"quotes/{QUOTE_ID}/extract"))
print(f"Extraction triggered: {trigger.get('status', 'accepted')}")
print("Polling for completion...")
```

The backend returns 202 Accepted. Proceed immediately to polling.

## Step 7: Poll for Completion

Poll GET /broker/projects/{project_id}/quotes every 2 seconds until the selected quote
status changes to "extracted" or "error". Maximum 30 polls (60 seconds).

```python
import sys, os, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
QUOTE_ID = "<selected-quote-id>"
MAX_POLLS = 30

target = None
for i in range(MAX_POLLS):
    result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/quotes"))
    quotes = result.get("quotes", [])
    target = next((q for q in quotes if q["id"] == QUOTE_ID), None)
    if target and target.get("status") == "extracted":
        print(f"Extraction completed after {(i+1)*2} seconds.")
        break
    if target and target.get("status") == "error":
        print(f"ERROR: Extraction failed for quote {QUOTE_ID}")
        print(f"  Reason: {target.get('extraction_error', 'unknown')}")
        break
    print(f"  Waiting for extraction... ({i+1}/{MAX_POLLS})")
    time.sleep(2)
else:
    print("ERROR: Extraction timed out after 60 seconds")
    print("Check backend logs for quote", QUOTE_ID)
```

If extraction failed or timed out, report the error and stop. Do not proceed to reporting.

## Step 8: Print Extraction Results

Read the updated quote object and print the premium breakdown and critical exclusions.

The `critical_exclusions` field is populated by the backend's quote_extractor.py, which
cross-references extracted exclusion clauses against the MSA contract's required coverages
to flag conflicts. This field must always be displayed — it surfaces contract compliance issues.

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
QUOTE_ID = "<selected-quote-id>"
CARRIER_NAME = "<selected-carrier-name>"

# Fetch the final quote object
result = api_client.run(api_client.get(f"projects/{PROJECT_ID}/quotes"))
quotes = result.get("quotes", [])
quote = next((q for q in quotes if q["id"] == QUOTE_ID), {})

total_premium = quote.get("total_premium", "N/A")
currency = quote.get("currency", "USD")
coverages = quote.get("coverages", [])
critical_exclusions = quote.get("critical_exclusions", [])
effective_date = quote.get("effective_date", "N/A")
expiry_date = quote.get("expiry_date", "N/A")

print(f"\nExtraction Complete for {CARRIER_NAME}:")
print("=========================================")
print(f"Total Premium: {total_premium} {currency}")
print(f"Effective Date: {effective_date}")
if expiry_date and expiry_date != "N/A":
    print(f"Expiry Date: {expiry_date}")

if coverages:
    print("\nCoverage breakdown:")
    for cov in coverages:
        cov_type = cov.get("coverage_type", "Unknown")
        premium = cov.get("premium_amount", cov.get("limit", "N/A"))
        print(f"  - {cov_type}: {premium}")
else:
    print("\nCoverage breakdown: (no line items extracted)")

exclusion_count = len(critical_exclusions) if isinstance(critical_exclusions, list) else 0
print(f"\nCritical Exclusions: {exclusion_count} flagged")
if exclusion_count > 0:
    for exc in critical_exclusions:
        if isinstance(exc, dict):
            desc = exc.get("description", exc.get("exclusion", str(exc)))
        else:
            desc = str(exc)
        print(f"  - {desc}")
elif exclusion_count == 0:
    print("  None — no exclusions conflict with MSA requirements.")
```

## Step 9: Memory Update

After successful extraction, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Extract Quote History
- Project {PROJECT_ID}, Quote {QUOTE_ID} ({CARRIER_NAME}): extraction run on {today's date}
  - Total Premium: {total_premium} {currency}
  - Critical Exclusions flagged: {exclusion_count}
```

Done. The quote PDF has been uploaded and extracted. Run `/broker:compare-quotes` to see
the full comparison matrix, or `/broker:draft-recommendation` to generate a client
recommendation narrative.
