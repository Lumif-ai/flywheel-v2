---
public: true
name: broker-parse-contract
version: "1.2"
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
assets: []
depends_on: ["broker"]
dependencies:
  python_packages:
    - "flywheel-ai>=0.4.0"
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# /broker:parse-contract — Upload MSA Contract and Extract Coverage Requirements

Upload a contract PDF to a broker project, trigger async analysis on the backend,
poll until complete, and print a summary of extracted coverage requirements.

## Step 1: Dependency Check

Run this block to verify the environment is ready:

```python
import os
from flywheel.broker import api_client, field_validator
# Check auth + dependencies
missing = []
# Auth: api_client.py auto-reads ~/.flywheel/credentials.json (written by `flywheel login`)
creds_file = os.path.expanduser("~/.flywheel/credentials.json")
if not os.path.exists(creds_file):
    missing.append("~/.flywheel/credentials.json (run: flywheel login)")
if missing:
    raise RuntimeError(f"Missing dependencies: {', '.join(missing)}\n"
                       "If auth is missing, run: flywheel login")

# Check pdfplumber and httpx
import pdfplumber
import httpx
print("OK: All dependencies satisfied.")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Inputs

Ask the user for:
- **PROJECT_ID** — UUID of the broker project (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)
- **PDF_PATH** — Absolute path to the MSA contract PDF file (e.g. `/Users/me/contracts/msa.pdf`)

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

## Step 3: Upload PDF

Upload the contract PDF to the project's document store:

```python
import os
from flywheel.broker import api_client, field_validator
PROJECT_ID = "<validated-project-id>"
PDF_PATH = "<validated-pdf-path>"

print(f"Uploading {os.path.basename(PDF_PATH)} to project {PROJECT_ID}...")
result = api_client.run(api_client.upload_file(PROJECT_ID, PDF_PATH))
files = result.get("files", [])
print(f"Upload successful. {len(files)} file(s) stored.")
for f in files:
    print(f"  - {f.get('filename', f.get('id', 'unknown'))}")
```

## Step 4: Analyze Contract via Pattern 3a (Claude-in-conversation)

In v1.2 (Phase 150.1), contract analysis runs **in THIS conversation** —
YOU (Claude) do the extraction using the prompt + tool_schema the backend
returns. The backend owns prompt assembly, PDF retrieval, and persistence;
it does NOT call Anthropic. This closes the subsidy-billing leak.

### 4a. Fetch extraction prompt + documents from the backend

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"

print(f"Fetching extraction prompt + documents for project {PROJECT_ID}...")
extract = api_client.run(api_client.extract_contract_analysis(PROJECT_ID))
# extract = {
#     "prompt": str,                    # fully-rendered extraction prompt (system message)
#     "tool_schema": dict,              # Anthropic tool-use schema (name, description, input_schema)
#     "documents": list[DocumentRef],   # [{file_id, filename, pdf_base64, document_type}]
#     "metadata": dict                  # {project_id, currency, language, ..., tool_schema_version}
# }
print(f"  prompt: {len(extract['prompt'])} chars")
print(f"  tool: {extract['tool_schema'].get('name', 'unknown')}")
print(f"  documents: {len(extract['documents'])} PDF(s)")
print(f"  tool_schema_version: {extract['metadata']['tool_schema_version']}")
```

### 4b. Analyze the contract inline using the returned prompt + tool_schema

**YOU (Claude) now run the analysis.** Do NOT shell out to another API — the
whole point of Pattern 3a is that THIS conversation's reasoning replaces the
deprecated server-side `/analyze` call:

1. Use `extract["prompt"]` as your system message (or first-user-message) for
   this analysis.
2. Use `extract["tool_schema"]` as the single entry in your `tools=` parameter.
3. For each entry in `extract["documents"]`, decode `pdf_base64` and attach
   via the Anthropic document content-block protocol:
   `{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": <pdf_base64>}}`
4. Request a tool-use completion and capture the `tool_use` block's `input`
   dict. It MUST match the tool_schema.input_schema (enforced by backend
   Pydantic validation in Step 4c).

Expected tool-use output keys (from `extract_coverage_requirements` schema):
`coverages` (list), `contract_language` (one of en/es/pt/other), `contract_summary`,
`total_coverages_found` (int), `primary_contract_filename`, `misrouted_documents` (list).

### 4c. Persist the analysis via save_contract_analysis

```python
import os
from flywheel.broker import api_client
PROJECT_ID = "<validated-project-id>"

# Build analysis dict from the tool_use block captured in 4b.
# Replace placeholder values with what YOU extracted from the PDFs above.
analysis = {
    "coverages": [],                         # from tool_use.input.coverages
    "contract_language": "es",               # en|es|pt|other
    "contract_summary": "",                  # 1-2 paragraph executive summary
    "total_coverages_found": 0,
    "primary_contract_filename": "",
    "misrouted_documents": [],
    "tool_schema_version": extract["metadata"]["tool_schema_version"],
}

print(f"Persisting analysis for project {PROJECT_ID}...")
save_result = api_client.run(api_client.save_contract_analysis(PROJECT_ID, analysis))
print(f"Saved: {save_result.get('coverages_saved', 0)} coverage(s); "
      f"status={save_result.get('status')}")
```

### Why this is different from v1.1

v1.1 triggered a server-side `/analyze` endpoint that called Anthropic with
the backend-owned subsidy key (the backend-pays billing leak). v1.2 returns
the SAME prompt + SAME tool_schema + SAME PDFs and has THIS conversation's
Claude run the analysis. Backend cost = zero LLM calls. Same outputs, new
compute boundary. See `skills/broker/MIGRATION-NOTES.md` for the full rationale.

## Step 5 [REMOVED in v1.2]

Polling is gone — Pattern 3a is synchronous. The analysis completes in Step 4b
(inline) and is persisted in Step 4c. Skip straight to Step 6.

## Step 6: Print Coverage Summary

Read project.coverages from the completed project and print a summary table.

```python
import os
from flywheel.broker import api_client
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
        "## parse-contract -- {today}\n"
        "- Project {PROJECT_ID}: {n_coverages} coverages, insurance={n_insurance}, surety={n_surety}\n"
    ),
)
```

Do NOT append to any local file -- the context store is the durable home for skill memory.

