---
name: broker-parse-contract
version: "1.0"
web_tier: 3
description: Upload MSA contract PDF and trigger backend async extraction of coverage requirements
context-aware: true
triggers:
  - /broker:parse-contract
tags:
  - broker
  - insurance
  - contract
  - extraction
  - pdf
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:parse-contract — Upload MSA Contract and Extract Coverage Requirements

Upload a contract PDF to a broker project, trigger async analysis on the backend,
poll until complete, and print a summary of extracted coverage requirements.

## Step 1: Dependency Check

Run this block to verify the environment is ready:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

# Check required env vars
missing = []
if not os.environ.get("FLYWHEEL_API_URL"):
    missing.append("FLYWHEEL_API_URL")
if not os.environ.get("FLYWHEEL_API_TOKEN"):
    missing.append("FLYWHEEL_API_TOKEN")
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}\n"
                       "Run: export FLYWHEEL_API_URL=https://... && export FLYWHEEL_API_TOKEN=<jwt>")

# Check pdfplumber and httpx
import pdfplumber
import httpx
print("OK: All dependencies satisfied.")
print(f"API URL: {os.environ.get('FLYWHEEL_API_URL')}")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Inputs

Ask the user for:
- **PROJECT_ID** — UUID of the broker project (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)
- **PDF_PATH** — Absolute path to the MSA contract PDF file (e.g. `/Users/me/contracts/msa.pdf`)

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

## Step 3: Upload PDF

Upload the contract PDF to the project's document store:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

PROJECT_ID = "<validated-project-id>"
PDF_PATH = "<validated-pdf-path>"

print(f"Uploading {os.path.basename(PDF_PATH)} to project {PROJECT_ID}...")
result = api_client.run(api_client.upload_file(PROJECT_ID, PDF_PATH))
files = result.get("files", [])
print(f"Upload successful. {len(files)} file(s) stored.")
for f in files:
    print(f"  - {f.get('filename', f.get('id', 'unknown'))}")
```

## Step 4: Trigger Async Analysis

Call the backend analyze endpoint to start async extraction:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

print(f"Triggering contract analysis for project {PROJECT_ID}...")
response = api_client.run(api_client.post(f"projects/{PROJECT_ID}/analyze"))
print(f"Analysis triggered. Status: {response.get('status', 'accepted')}")
print("Polling for completion...")
```

The backend returns 202 Accepted. Proceed immediately to polling.

## Step 5: Poll for Completion

Poll GET /broker/projects/{project_id} every 2 seconds until analysis_status is
"completed" or "failed". Maximum 30 polls (60 seconds).

```python
import sys, os, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
MAX_POLLS = 30

project = None
for i in range(MAX_POLLS):
    project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
    status = project.get("analysis_status")
    if status == "completed":
        print(f"Analysis completed after {(i+1)*2} seconds.")
        break
    if status == "failed":
        print(f"ERROR: Contract analysis failed")
        print(f"  Reason: {project.get('analysis_error', 'unknown')}")
        break
    print(f"  Waiting for analysis... ({i+1}/{MAX_POLLS})")
    time.sleep(2)
else:
    print("ERROR: Analysis timed out after 60 seconds")
    print("Check backend logs for project", PROJECT_ID)
```

If analysis failed or timed out, report the error and stop. Do not proceed to summary.

## Step 6: Print Coverage Summary

Read project.coverages from the completed project and print a summary table.

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

project = api_client.run(api_client.get(f"projects/{PROJECT_ID}"))
coverages = project.get("coverages", [])

if not coverages:
    print("WARNING: No coverages extracted from contract.")
else:
    print(f"\nExtracted {len(coverages)} coverage requirement(s):\n")
    print(f"{'Coverage Type':<35} {'Category':<12} {'Required Limit':>16} {'Confidence':>12} {'Clause Ref'}")
    print("-" * 90)
    insurance_count = 0
    surety_count = 0
    for c in coverages:
        category = c.get("category", "unknown")
        if category == "insurance":
            insurance_count += 1
        elif category == "surety":
            surety_count += 1
        print(
            f"{c.get('coverage_type', 'Unknown'):<35} "
            f"{category:<12} "
            f"{str(c.get('required_limit', 'N/A')):>16} "
            f"{str(c.get('confidence', 'N/A')):>12} "
            f"{c.get('clause_reference', '')}"
        )
    print()
    print(f"  Insurance types: {insurance_count}")
    print(f"  Surety types:    {surety_count}")

    if insurance_count < 6:
        print(f"  WARNING: Only {insurance_count} insurance coverage types found (expected >= 6)")
    if surety_count < 3:
        print(f"  WARNING: Only {surety_count} surety bond types found (expected >= 3)")
```

## Step 7: Memory Update

After successful extraction, update your memory:

Update `~/.claude/skills/broker/auto-memory/broker.md` (or create it if absent).
Add a note:

```
## Contract Parse History
- Project {PROJECT_ID}: {len(coverages)} coverages extracted on {today's date}
  - Insurance types: {insurance_count}
  - Surety types: {surety_count}
```

Done. The contract has been uploaded, analyzed, and coverage requirements are now
stored in the project. Run `/broker:parse-policies` next to load existing policy PDFs
and match them against these requirements.
