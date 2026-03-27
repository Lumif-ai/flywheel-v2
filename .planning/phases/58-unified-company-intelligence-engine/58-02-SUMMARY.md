---
phase: 58
plan: 02
subsystem: backend-api
tags: [profile, skill-run, enrichment, refactor]
dependency_graph:
  requires: [58-01]
  provides: [analyze-document-skillrun, refresh-endpoint, reset-endpoint]
  affects: [frontend-profile-page, skill-executor-job-queue]
tech_stack:
  added: []
  patterns: [skillrun-routing, soft-delete-reset]
key_files:
  modified:
    - backend/src/flywheel/api/profile.py
decisions:
  - "enrichment_status field retained on CompanyProfileResponse but hardcoded to None — avoids frontend breakage while removing all enrichment logic"
  - "refresh_profile called directly (not via HTTP) from reset_profile — keeps db session shared across both operations"
  - "profile_linked flag set on UploadedFile in analyze-document before creating SkillRun — ensures file appears in subsequent refresh aggregation"
metrics:
  duration: "~2 min"
  completed: "2026-03-27"
  tasks_completed: 1
  files_changed: 1
---

# Phase 58 Plan 02: Profile API — SkillRun Routing Summary

**One-liner:** Rewired `analyze-document`, `refresh`, and `reset` profile endpoints to create pending SkillRuns instead of running inline analysis, eliminating the dual-path background enrichment system.

## What Was Built

Three API-level changes to `backend/src/flywheel/api/profile.py`:

1. **`POST /profile/analyze-document`** — Replaced 170-line inline `structure_intelligence` + background enrichment flow with a 20-line SkillRun creator. The endpoint validates the file, marks it `profile_linked`, creates a `SkillRun(skill_name="company-intel", input_text="DOCUMENT_FILE:{file_id}", status="pending")`, and returns `{"run_id": ...}`. The job queue worker picks it up and calls `_execute_company_intel`.

2. **`POST /profile/refresh`** — New endpoint. Fetches tenant domain and all `profile_linked` uploaded files with extracted text. Assembles `input_text` as URL on first line (if domain exists) followed by `DOCUMENT_FILE:{id}` lines for each linked document. Creates a single SkillRun and returns `{"run_id": ...}`. Returns 400 if neither URL nor documents are available.

3. **`POST /profile/reset`** — New endpoint. Soft-deletes all `company-intel-onboarding` ContextEntry rows for the tenant (sets `deleted_at = now()`), commits, then calls `refresh_profile()` directly to queue a fresh SkillRun. Returns `{"run_id": ..., "deleted_count": N}`.

## Dead Code Removed

- `_run_background_enrichment` async function (~150 lines of retry-looping enrichment logic)
- `_build_enrichment_section_map` helper (~60 lines)
- `MAX_ENRICHMENT_RETRIES` constant
- `RetryEnrichmentRequest` Pydantic model
- `POST /profile/retry-enrichment` endpoint (~90 lines)
- `enrichment_status` calculation block in `get_company_profile` (was reading file metadata for active enrichment states)
- `BackgroundTasks` import from fastapi
- `asyncio` import (no longer needed)

**Net change:** 102 insertions, 483 deletions — a 78% reduction in profile.py line count for the affected section.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- `backend/src/flywheel/api/profile.py` — FOUND

### Commits exist:
- `174c0f2` — FOUND (`feat(58-02): route profile endpoints through SkillRun engine`)

### Verification results:
- Module loads: `Routes: 7` — PASSED
- `def analyze_document` at line 314 — FOUND
- `def refresh_profile` at line 360 — FOUND
- `def reset_profile` at line 419 — FOUND
- `_run_background_enrichment` occurrences: 0 — PASSED
- `retry_enrichment`/`RetryEnrichmentRequest` occurrences: 0 — PASSED
- `deleted_at` in reset soft-delete values: FOUND (line 434)
- `SkillRun` usage count: 4 (import + analyze-document + refresh + within reset) — PASSED

## Self-Check: PASSED
