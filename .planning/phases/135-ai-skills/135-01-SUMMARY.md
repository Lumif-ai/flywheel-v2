---
phase: 135
plan: "01"
subsystem: broker-skills
tags: [skills, api-client, parse-contract, parse-policies, gap-analysis, pdfplumber]
dependency_graph:
  requires:
    - 134-01 (api_client.py with post/get/run)
    - 134-03 (broker hooks infrastructure)
  provides:
    - api_client.patch() and api_client.upload_file()
    - /broker:parse-contract step skill
    - /broker:parse-policies step skill
    - /broker:gap-analysis step skill
  affects:
    - 135-02 (process-project pipeline uses these steps)
    - 135-03 (fill-portal pipeline)
tech_stack:
  added:
    - pdfplumber (local PDF text extraction in parse-policies)
    - httpx multipart (upload_file uses multipart/form-data)
  patterns:
    - sys.path.insert import pattern for all broker skill Python blocks
    - Spanish-to-English coverage type translation map
    - Polling loop with MAX_POLLS guard (30 polls, 2s interval, 60s max)
    - Inline AI text extraction (Claude reads pdfplumber output directly)
key_files:
  created:
    - ~/.claude/skills/broker/steps/parse-contract.md
    - ~/.claude/skills/broker/steps/parse-policies.md
    - ~/.claude/skills/broker/steps/gap-analysis.md
  modified:
    - ~/.claude/skills/broker/api_client.py (added patch, upload_file)
decisions:
  - "upload_file() re-reads FLYWHEEL_API_TOKEN at call time via os.environ.get() (not module-level API_TOKEN) so tests can set the env var after import"
  - "upload_file() does not use _headers() to avoid Content-Type override — httpx sets multipart boundary automatically"
  - "parse-policies uses inline Claude reading of pdfplumber output rather than an API call — avoids round-trip latency and keeps extraction local"
  - "Spanish-to-English map covers 9 coverage types; unmapped types fall back to Claude best-judgment"
  - "parse-contract polls at 2s intervals, MAX_POLLS=30 (60s max) with explicit error path on 'failed' status"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-15"
  tasks_completed: 3
  files_created: 4
---

# Phase 135 Plan 01: API Client Extensions and Step Skills Summary

**One-liner:** Added patch() and upload_file() to api_client.py and created three step SKILL.md files (parse-contract, parse-policies, gap-analysis) forming the first half of the broker process-project pipeline.

## What Was Built

### Task 1: api_client.py Extensions

Added two async functions after the existing `get()` function:

- **patch(path, payload)** — mirrors `post()` but uses `client.patch()`. Same Bearer auth via `_headers()`.
- **upload_file(project_id, pdf_path)** — multipart/form-data POST to `/broker/projects/{id}/documents`. Re-reads `FLYWHEEL_API_TOKEN` at call time (not the module-level `API_TOKEN` variable) so test environments can set the env var after import.

`api_client.py` now exports 5 functions: `post`, `get`, `patch`, `upload_file`, `run`.

### Task 2: parse-contract.md and gap-analysis.md

Created `~/.claude/skills/broker/steps/` directory with two step skills:

**parse-contract.md** (`/broker:parse-contract`):
- 7-step prompt: dependency check → collect inputs → upload PDF → trigger async analysis → poll for completion → print coverage summary table → memory update
- Uses `upload_file()` for PDF upload
- Polling loop: `MAX_POLLS=30`, 2s sleep, breaks on `completed`/`failed`, times out gracefully
- Coverage summary table: insurance count vs surety count with warnings if < 6 or < 3

**gap-analysis.md** (`/broker:gap-analysis`):
- 5-step prompt: dependency check → collect input → POST analyze-gaps → print gap table → memory update
- Gap status derivation: MISSING (no current coverage), INSUFFICIENT, ADEQUATE, EXCESS
- Status count summary at end

### Task 3: parse-policies.md

Created `~/.claude/skills/broker/steps/parse-policies.md` (`/broker:parse-policies`):
- 7-step prompt: dependency check → collect inputs (project_id + list of PDFs) → fetch existing coverages → extract PDF text with pdfplumber → inline AI reads text → match and PATCH → memory update
- Spanish-to-English translation map for 9 coverage types (RC General, TRC, Fianza de Cumplimiento, etc.)
- Explicit instruction: "You (Claude) will read the text block printed above and extract policy terms. Do not call an API for this — analyze the text directly."
- Match strategy: exact match first, then contains match
- PATCH via `api_client.patch(f"coverages/{coverage_id}", {...})`

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created:
- `~/.claude/skills/broker/api_client.py` — patch and upload_file confirmed via python3 import check
- `~/.claude/skills/broker/steps/parse-contract.md` — triggers, upload_file, MAX_POLLS confirmed
- `~/.claude/skills/broker/steps/gap-analysis.md` — analyze-gaps endpoint confirmed
- `~/.claude/skills/broker/steps/parse-policies.md` — pdfplumber, api_client.patch, Responsabilidad Civil map confirmed

All 5 api_client exports verified:
```
post — (path: str, payload: Optional[dict] = None) -> dict
get — (path: str, params: Optional[dict] = None) -> dict
patch — (path: str, payload: Optional[dict] = None) -> dict
upload_file — (project_id: str, pdf_path: str) -> dict
run — (coro)
```

## Self-Check: PASSED
