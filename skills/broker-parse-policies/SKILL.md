---
public: true
name: broker-parse-policies
version: "1.2"
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
assets: []
depends_on: ["broker"]
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
  python_packages:
    - pdfplumber
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


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
# Auth: api_client.py auto-reads ~/.flywheel/credentials.json (written by `flywheel login`)
creds_file = os.path.expanduser("~/.flywheel/credentials.json")
if not os.path.exists(creds_file):
    missing.append("~/.flywheel/credentials.json (run: flywheel login)")
if missing:
    raise RuntimeError(f"Missing dependencies: {', '.join(missing)}\n"
                       "If auth is missing, run: flywheel login")

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

## Step 4: Upload Policy PDFs to the Project

Pattern 3a (v1.2) moves policy extraction onto the backend-authoritative flow.
Upload each PDF to the project's coverage zone so the backend can return them
(base64-encoded) from `extract/policy-extraction` in Step 5:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"
PDF_PATHS = ["<validated-path-1>", "<validated-path-2>"]  # from Step 2

for pdf_path in PDF_PATHS:
    print(f"Uploading {os.path.basename(pdf_path)}...")
    result = api_client.run(api_client.upload_file(PROJECT_ID, pdf_path))
    # upload_file stores files with document_type='requirements' by default;
    # the broker can reclassify to 'coverage' via the UI or PATCH endpoint.
    print(f"  stored: {len(result.get('files', []))} file(s)")
```

(If the broker already uploaded these PDFs via the UI, skip this and
continue — the extract endpoint reads every coverage-zone PDF on the project.)

## Step 5: Extract Policy Data via Pattern 3a (Claude-in-conversation)

v1.2 runs policy extraction in THIS conversation using the prompt +
tool_schema the backend returns. The backend owns prompt assembly, taxonomy
load, PDF retrieval, and persistence; it does NOT call Anthropic.

### 5a. Fetch extraction prompt + coverage-zone PDFs

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

extract = api_client.run(api_client.extract_policy_extraction(PROJECT_ID))
# extract = {prompt, tool_schema, documents, metadata}
# documents is restricted to document_type='coverage' (COIs, policy summaries).
print(f"  prompt: {len(extract['prompt'])} chars")
print(f"  tool: {extract['tool_schema'].get('name', 'unknown')}")
print(f"  documents: {len(extract['documents'])} coverage-zone PDF(s)")
print(f"  tool_schema_version: {extract['metadata']['tool_schema_version']}")
```

### 5b. Analyze inline using the returned prompt + tool_schema

**YOU (Claude) now run the extraction.** For each document in
`extract["documents"]`, decode `pdf_base64` and attach via the Anthropic
document content-block protocol. Use `extract["prompt"]` as the system
message and `extract["tool_schema"]` as the single `tools=` entry.

Expected tool-use output keys (from `extract_current_policies` schema):
`documents` (list of `{file_id, filename, policies: [...]}`), `policies`
(flat list with `coverage_type_key`, `raw_coverage_name`, `current_carrier`,
`current_limit`, `current_policy_number`), `total_policies_found` (int).

The backend's persistence helper handles coverage-taxonomy alias matching
and PATCH of each matched `BrokerCoverage` row — the old client-side
alias_map + PATCH loop is no longer needed.

### 5c. Persist the extraction

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

# Build analysis dict from the tool_use block captured in 5b.
analysis = {
    "documents": [],                        # from tool_use.input.documents
    "policies": [],                         # from tool_use.input.policies
    "total_policies_found": 0,
    "tool_schema_version": extract["metadata"]["tool_schema_version"],
}

save_result = api_client.run(api_client.save_policy_extraction(PROJECT_ID, analysis))
print(f"Saved: {save_result.get('policies_extracted', 0)} policies, "
      f"{save_result.get('rows_updated', 0)} coverage row(s) updated")
if save_result.get("orphans"):
    print(f"  orphans (no matching coverage row): {len(save_result['orphans'])}")
    for orphan in save_result["orphans"]:
        print(f"    - {orphan}")
```

### Why this is different from v1.1

v1.1 had THIS skill open the PDFs locally with `pdfplumber`, build a
hardcoded alias_map client-side, and PATCH each coverage row individually.
That worked but split truth across the client (alias_map) and backend
(coverage rows), and the text-only extraction missed structured data hidden
in table layouts. v1.2 keeps truth on the backend — the extract endpoint
returns the rendered prompt + full PDFs to Claude, Claude analyzes them with
the same tool_schema the old server-side path used, and the save endpoint
runs alias matching + PATCH atomically in one transaction. Zero LLM calls on
the backend; fewer roundtrips; no client-side alias drift. Details in
`skills/broker/MIGRATION-NOTES.md`.

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
