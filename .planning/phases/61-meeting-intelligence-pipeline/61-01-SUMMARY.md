---
phase: 61-meeting-intelligence-pipeline
plan: 01
subsystem: backend/engines + backend/api
tags: [meeting-intelligence, context-entries, skill-executor, granola, supabase-storage]
dependency_graph:
  requires:
    - 60-01: Meeting ORM model with processing_status, transcript_url, summary JSONB
    - 60-02: granola_adapter with get_meeting_content()
    - 60-03: POST /meetings/sync endpoint
  provides:
    - meeting_processor_web.py: classify_meeting, extract_intelligence, upload_transcript, write_context_entries
    - skill_executor._execute_meeting_processor(): 7-stage pipeline
    - POST /meetings/{id}/process endpoint
  affects:
    - ContextEntry rows written for each processed meeting
    - Meeting.summary JSONB, processing_status, meeting_type, transcript_url
tech_stack:
  added:
    - asyncio.get_event_loop().run_in_executor() for sync Anthropic SDK calls in async context
    - httpx async upload to Supabase Storage (POST /storage/v1/object/uploads/...)
  patterns:
    - 3-layer classification (DB lookup → domain check → LLM)
    - 7-stage SSE event streaming pipeline in skill_executor
    - CONTEXT_FILE_MAP for MPP-04 aligned key→file_name mapping
    - Dedup pattern: check (file_name, source, detail, tenant_id) before insert
key_files:
  created:
    - backend/src/flywheel/engines/meeting_processor_web.py
  modified:
    - backend/src/flywheel/services/skill_executor.py
    - backend/src/flywheel/api/meetings.py
decisions:
  - "Sync Anthropic SDK wrapped in run_in_executor — avoids blocking event loop while keeping simple SDK usage"
  - "Stage 5 (account linking) is a deliberate placeholder — Plan 02 replaces with auto_link_meeting_to_account"
  - "upload_transcript uses httpx POST (not PUT/upsert) — 409 response treated as non-fatal"
  - "write_context_entries deduplicates on (file_name, source, detail, tenant_id) — safe to re-run without duplicates"
  - "classify_meeting Layer 2 skipped entirely when tenant.domain IS NULL — logged at DEBUG level"
metrics:
  duration: "5 min"
  completed: "2026-03-28"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 61 Plan 01: Meeting Intelligence Pipeline Summary

**One-liner:** 7-stage meeting processor with Granola transcript fetch, Supabase Storage upload, 3-layer classification (contact match → domain check → Haiku LLM), Sonnet extraction into 7 MPP-04 context file types, and POST /meetings/{id}/process endpoint.

## What Was Built

### meeting_processor_web.py (NEW — 285 lines)

Four async helper functions comprising the engine's building blocks:

1. **classify_meeting()** — 3-layer classification returning one of 8 types:
   - Layer 1: Query `AccountContact` for attendee emails; derive type from account `relationship_type` array
   - Layer 2: Domain check — all internal emails → `internal` (≤3 attendees) or `team-meeting` (>3); skipped if `tenant.domain` IS NULL
   - Layer 3: Haiku LLM call with title + attendees + first 500 chars of transcript (sync SDK in `run_in_executor`)
   - Default fallback: `discovery`

2. **extract_intelligence()** — Sonnet extraction into 9-key dict:
   - 7 context file keys matching `CONTEXT_FILE_MAP`: `competitive_intel`, `pain_points`, `icp_profiles`, `contacts`, `insights`, `action_items`, `product_feedback`
   - 2 summary-only keys (not written as context entries): `tldr`, `key_decisions`
   - Strips ```` ```json ```` fences, handles parse errors gracefully

3. **upload_transcript()** — httpx async upload to `uploads/transcripts/{tenant_id}/{meeting_id}.txt`

4. **write_context_entries()** — ORM-based ContextEntry creation:
   - Sets `source="ctx-meeting-processor"`, `detail=meeting_slug`, `confidence="medium"`
   - Sets `account_id` directly on ORM object when provided
   - Deduplicates on `(file_name, source, detail, tenant_id)` before insert

**`CONTEXT_FILE_MAP`** (7 entries, MPP-04 aligned):
```python
{
    "competitive_intel": "competitive-intel",
    "pain_points": "pain-points",
    "icp_profiles": "icp-profiles",
    "contacts": "contacts",
    "insights": "insights",
    "action_items": "action-items",
    "product_feedback": "product-feedback",
}
```

### skill_executor.py (MODIFIED)

- Added `is_meeting_processor = run.skill_name == "meeting-processor"` dispatch flag
- Added `elif is_meeting_processor:` dispatch block calling `_execute_meeting_processor()`
- Added `"meeting-processor"` to subsidy API key allowlist
- Added `_execute_meeting_processor()` function (~200 lines) with 7 SSE stages:
  1. `fetching` — load Meeting + Integration rows, decrypt Granola key, call `get_meeting_content()`
  2. `storing` — call `upload_transcript()`, update `meeting.transcript_url` and `meeting.attendees`
  3. `classifying` — call `classify_meeting()` with 3-layer detection
  4. `extracting` — call `extract_intelligence()` with existing context preloaded
  5. `linking` — placeholder log: "Account linking deferred to Plan 02"
  6. `writing` — call `write_context_entries()`, generate `meeting_slug`
  7. `done` — update `meeting.summary` JSONB, `processing_status="complete"`, `processed_at=now()`

### meetings.py (MODIFIED)

Added `POST /{meeting_id}/process` endpoint:
- Requires `require_tenant` auth
- 404 if meeting not found
- 409 if `processing_status` is already `processing` or `complete`
- Sets `processing_status = "processing"` immediately as race condition guard
- Creates `SkillRun(skill_name="meeting-processor", input_text=str(meeting_id))`
- Links `meeting.skill_run_id = run.id`
- Returns `{"run_id": ..., "meeting_id": ...}`

## Decisions Made

- **Sync SDK in run_in_executor**: `asyncio.get_event_loop().run_in_executor(None, lambda: ...)` for both Haiku and Sonnet calls. Avoids blocking the event loop while keeping simple sync SDK usage (no streaming needed here).
- **Stage 5 placeholder**: Account linking is an explicit deliberate stub — logged + commented for Plan 02 replacement.
- **upload_transcript 409 non-fatal**: Supabase returns 409 on duplicate object; treated as successful no-op (transcript already stored).
- **Dedup on (file_name, source, detail, tenant_id)**: Makes write_context_entries idempotent — safe to re-run processing on a meeting without creating duplicate context entries.
- **Layer 2 NULL guard**: classify_meeting Layer 2 is silently skipped (with DEBUG log) when `tenant.domain IS NULL`, rather than raising an error.

## Deviations from Plan

None — plan executed exactly as written. Stage 5 placeholder is per-plan specification.

## Spec Gaps Discovered

None.

## Self-Check

### Files exist:
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/engines/meeting_processor_web.py` — created, 285 lines
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/skill_executor.py` — modified
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/meetings.py` — modified

### Commits:
- `676cbee` — feat(61-01): meeting intelligence pipeline — processor engine + API endpoint

## Self-Check: PASSED
