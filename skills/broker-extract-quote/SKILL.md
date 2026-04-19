---
public: true
name: broker-extract-quote
version: "1.2"
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
  python_packages:
    - "flywheel-ai>=0.4.0"
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# /broker:extract-quote — Upload Carrier Quote PDF and Extract Premium Breakdown

Map a carrier quote PDF to an existing quote row in the database, upload the PDF,
trigger async extraction, poll until complete, and print a premium breakdown with
flagged critical exclusions.

**NOTE:** This skill does NOT create a new CarrierQuote row. The quote row must already
exist (brokers create them via the UI or mark-received flow). This skill maps a PDF to
an existing quote and triggers extraction.

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
- **PDF_PATH** — Absolute path to the carrier quote PDF file (e.g. `/Users/me/quotes/hartford.pdf`)

Validate both inputs using field_validator:

```python
import os
from flywheel.broker import api_client, field_validator
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
import os
from flywheel.broker import api_client
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
import os
from flywheel.broker import api_client
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
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"
PDF_PATH = "<validated-pdf-path>"

print(f"Uploading {os.path.basename(PDF_PATH)} to project {PROJECT_ID}...")
upload_result = api_client.run(api_client.upload_file(PROJECT_ID, PDF_PATH))
files = upload_result.get("files", [])
print(f"Uploaded: {len(files)} file(s) stored.")
for f in files:
    print(f"  - {f.get('filename', f.get('id', 'unknown'))}")
```

## Step 6: Extract Quote via Pattern 3a (Claude-in-conversation)

v1.2 (Phase 150.1) has THIS conversation run the quote-text extraction using
the prompt + tool_schema the backend returns. The backend owns prompt
assembly, quote-row lookup, PDF retrieval, and persistence; it does NOT
call Anthropic.

### 6a. Fetch extraction prompt + quote PDFs

```python
import os
from flywheel.broker import api_client
QUOTE_ID = "<selected-quote-id>"

extract = api_client.run(api_client.extract_quote_extraction(QUOTE_ID))
# extract = {prompt, tool_schema, documents, metadata}
# documents = quote PDFs attached to this quote row.
print(f"  prompt: {len(extract['prompt'])} chars")
print(f"  tool: {extract['tool_schema'].get('name', 'unknown')}")
print(f"  documents: {len(extract['documents'])} quote PDF(s)")
print(f"  tool_schema_version: {extract['metadata']['tool_schema_version']}")
```

### 6b. Analyze inline using the returned prompt + tool_schema

**YOU (Claude) now run the extraction.** For each document in
`extract["documents"]`, decode `pdf_base64` and attach via the Anthropic
document content-block protocol. Use `extract["prompt"]` as the system
message and `extract["tool_schema"]` as the single `tools=` entry.

Expected tool-use output keys (from `extract_quote_terms` schema):
`carrier_name`, `quote_date` (ISO date or null), `quote_reference` (string
or null), `currency` (ISO 4217), `total_premium` (number), `line_items`
(list of coverage-level premium rows).

### 6c. Persist the extraction

The backend's `persist_quote_extraction` helper writes the quote row, builds
the exclusion cross-check against the project's MSA contract requirements,
and populates `critical_exclusions` — no client-side work needed.

```python
import os
from flywheel.broker import api_client
QUOTE_ID = "<selected-quote-id>"

analysis = {
    "carrier_name": "",                      # from tool_use.input.carrier_name
    "quote_date": None,
    "quote_reference": None,
    "currency": "USD",
    "total_premium": 0.0,
    "line_items": [],
    "tool_schema_version": extract["metadata"]["tool_schema_version"],
}

save_result = api_client.run(api_client.save_quote_extraction(QUOTE_ID, analysis))
print(f"Saved quote {QUOTE_ID}: status={save_result.get('status')}")
```

### Why this is different from v1.1

v1.1 called `/quotes/{id}/extract` which ran Anthropic server-side with the
backend's subsidy key, then persisted the result. The broker had to poll
`/projects/{id}/quotes` for up to 60 seconds waiting for completion. v1.2
returns the SAME prompt + SAME tool_schema + SAME PDFs and has THIS
conversation's Claude run the extraction, so the flow is synchronous (no
polling) and the backend cost is zero LLM calls. Details in
`skills/broker/MIGRATION-NOTES.md`.

## Step 7 [REMOVED in v1.2]

Polling is gone — Pattern 3a is synchronous. Proceed to Step 8.

## Step 8: Print Extraction Results

Read the updated quote object and print the premium breakdown and critical exclusions.

The `critical_exclusions` field is populated by the backend's quote_extractor.py, which
cross-references extracted exclusion clauses against the MSA contract's required coverages
to flag conflicts. This field must always be displayed — it surfaces contract compliance issues.

```python
import os
from flywheel.broker import api_client
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
        "## extract-quote -- {today}\n"
        "- Project {PROJECT_ID}: {n_line_items} line items extracted from {carrier} quote ({total_premium} {currency})\n"
    ),
)
```

Do NOT append to any local file -- the context store is the durable home for skill memory.

