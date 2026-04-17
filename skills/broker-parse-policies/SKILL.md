---
public: true
name: broker-parse-policies
version: "1.0"
web_tier: 3
description: Extract coverage data from local policy PDFs using pdfplumber, match to project coverages, and PATCH current limits and carriers
context-aware: true
triggers:
  - /broker:parse-policies
tags:
  - broker
  - insurance
  - policy
  - extraction
  - pdf
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
  python_packages:
    - pdfplumber
---

# /broker:parse-policies — Extract Policy Data and Update Project Coverages

Read local policy PDF files using pdfplumber, extract coverage details (carrier,
limit, policy number), match to the project's coverage records using the canonical
coverage taxonomy API, and PATCH each matched coverage record.

**Important:** You (Claude, running this skill) will read the extracted PDF text
printed to the console and identify the policy terms inline. Do NOT call an external
API for text extraction — analyze the pdfplumber output directly.

## Step 1: Dependency Check

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator
import pdfplumber
import httpx

missing = []
if not os.environ.get("FLYWHEEL_API_URL"):
    missing.append("FLYWHEEL_API_URL")
if not os.environ.get("FLYWHEEL_API_TOKEN"):
    missing.append("FLYWHEEL_API_TOKEN")
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}\n"
                       "Run: export FLYWHEEL_API_URL=https://... && export FLYWHEEL_API_TOKEN=<jwt>")

print("OK: All dependencies satisfied (pdfplumber, httpx, api_client, field_validator).")
```

## Step 2: Collect Inputs

Ask the user for:
- **PROJECT_ID** — UUID of the broker project
- **PDF_PATHS** — One or more absolute paths to existing policy PDF files
  (comma-separated or one per line)

Validate inputs:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

PROJECT_ID = "<user-provided-project-id>"
PDF_PATHS_RAW = "<comma-separated-pdf-paths>"

PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")

# Parse and validate paths
pdf_paths = [p.strip() for p in PDF_PATHS_RAW.split(",") if p.strip()]
validated_paths = []
for path in pdf_paths:
    if not os.path.exists(path):
        print(f"  WARNING: File not found: {path} — skipping")
    else:
        validated_paths.append(path)

if not validated_paths:
    raise ValueError("No valid PDF files provided. Please provide at least one existing PDF path.")

print(f"Validated: project_id={PROJECT_ID}")
print(f"PDF files to process: {len(validated_paths)}")
for p in validated_paths:
    print(f"  - {p}")
```

## Step 3: Fetch Existing Project Coverages

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
coverages = project.get("coverages", [])

print(f"\nProject has {len(coverages)} coverage requirement(s):")
for c in coverages:
    print(f"  [{c.get('id')}] {c.get('coverage_type')} — "
          f"required: {c.get('required_limit', 'N/A')}, "
          f"current: {c.get('current_limit', 'None')}")
```

## Step 4: Extract Text from Each Policy PDF

For each PDF file, extract all text using pdfplumber and print the first 2000
characters so you can read the policy terms:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import pdfplumber

PDF_PATHS = ["<validated-path-1>", "<validated-path-2>"]  # from Step 2

policy_texts = {}
for pdf_path in PDF_PATHS:
    print(f"\n{'='*60}")
    print(f"Extracting text from: {os.path.basename(pdf_path)}")
    print('='*60)
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    policy_texts[pdf_path] = text
    print(f"\n--- Extracted text from {os.path.basename(pdf_path)} ---")
    print(text[:2000])  # Show first 2000 chars for context
    if len(text) > 2000:
        print(f"... [{len(text) - 2000} more characters not shown]")
```

## Step 5: Identify Coverage Details from Extracted Text

**You (Claude) will now read the text blocks printed above and extract policy terms.**
Do not call an API for this — analyze the text directly.

For each policy PDF, identify:
- **current_carrier** — The insurance company name (e.g. "AXA", "MAPFRE", "Zurich")
- **coverage_type** — The type of coverage (use the taxonomy alias_map built below)
- **current_limit** — The policy limit as a number (e.g. 1000000 for 1,000,000)
- **current_policy_number** — The policy number string (may be absent)

### Load Coverage Taxonomy from API

Before matching, fetch the canonical coverage types with their aliases from the
taxonomy API. This replaces any hardcoded translation maps and supports all
languages automatically:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

# Get project details to determine country and line of business
project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
country = project.get("country_code", "")
lob = project.get("line_of_business", "")

# Fetch canonical coverage types with aliases for this market
params = []
if country:
    params.append(f"country={country}")
if lob:
    params.append(f"lob={lob}")
query = "&".join(params)
taxonomy = api_client.run(api_client.get(f"coverage-types?{query}"))

# Build a lookup: alias (lowered) → canonical coverage_type key
alias_map = {}
for ct in taxonomy.get("coverage_types", []):
    key = ct["key"]
    alias_map[key.lower()] = key
    alias_map[ct.get("display_name", "").lower()] = key
    for lang, aliases in ct.get("aliases", {}).items():
        for alias in aliases:
            alias_map[alias.lower()] = key

print(f"Loaded {len(taxonomy.get('items', []))} coverage types with {len(alias_map)} aliases")
```

Use `alias_map` to match coverage names found in the PDF text (lowered) to
canonical keys. The aliases include contract-language terms (e.g. Spanish,
Portuguese names) so they will match policy documents in any supported language.

If a coverage name from the PDF does not match any alias, use your best judgment
based on context. If you cannot determine the coverage type, skip the file and
note it as unmatched.

## Step 6: Match Coverages and PATCH Records

For each identified coverage, find the matching record in the project's coverages list
(from Step 3) and PATCH it with the extracted data.

Match strategy:
1. Exact match on coverage_type (case-insensitive)
2. If no exact match, try contains match (e.g. "Liability" matches "General Liability")

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

# These values come from your inline reading of the PDF text in Step 5.
# Replace with actual extracted values per PDF.
extracted_policies = [
    {
        "pdf_path": "<path>",
        "coverage_type": "<english-coverage-type>",  # canonical key from taxonomy
        "current_carrier": "<carrier-name>",
        "current_limit": 0,           # number
        "current_policy_number": None  # string or None
    }
    # ... one entry per identified coverage
]

project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
coverages = project.get("coverages", [])

updated_count = 0
unmatched_pdfs = []

for policy in extracted_policies:
    target_type = policy["coverage_type"].lower()
    match = None

    # Try exact match first
    for c in coverages:
        if c.get("coverage_type", "").lower() == target_type:
            match = c
            break

    # Try contains match
    if not match:
        for c in coverages:
            if target_type in c.get("coverage_type", "").lower() or \
               c.get("coverage_type", "").lower() in target_type:
                match = c
                break

    if not match:
        print(f"  WARNING: No matching coverage found for '{policy['coverage_type']}'")
        unmatched_pdfs.append(policy["pdf_path"])
        continue

    coverage_id = match["id"]
    coverage_type = match["coverage_type"]

    result = api_client.run(api_client.patch(
        f"coverages/{coverage_id}",
        {
            "current_limit": policy["current_limit"],
            "current_carrier": policy["current_carrier"],
            "current_policy_number": policy["current_policy_number"]
        }
    ))
    print(f"  Updated {coverage_type}: limit={policy['current_limit']:,}, "
          f"carrier={policy['current_carrier']}")
    updated_count += 1

print(f"\nResult: {updated_count} coverage(s) updated out of {len(coverages)} total.")
if unmatched_pdfs:
    print(f"\nUnmatched files ({len(unmatched_pdfs)}):")
    for path in unmatched_pdfs:
        print(f"  - {os.path.basename(path)}")
```

## Step 7: Memory Update

After processing, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Policy Parse History
- Project {PROJECT_ID}: {updated_count} coverages updated from {len(PDF_PATHS)} PDFs on {today's date}
  - Files processed: {comma-separated filenames}
  - Unmatched: {unmatched_pdfs if any}
```

Done. Policy data has been extracted and pushed to the project. Run `/broker:gap-analysis`
next to see the current gap status with updated coverage limits.
