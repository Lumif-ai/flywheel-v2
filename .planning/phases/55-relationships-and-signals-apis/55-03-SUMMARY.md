---
phase: 55-relationships-and-signals-apis
plan: 03
subsystem: api

tags: [fastapi, sqlalchemy, supabase-storage, httpx, signals, context-entries, crm]

requires:
  - phase: 55-01
    provides: "relationships router with RAPI-01..04, graduated_at partition predicate"
  - phase: 55-02
    provides: "SynthesisEngine service, RAPI-07 /synthesize, RAPI-08 /ask"

provides:
  - "POST /relationships/{id}/notes — creates ContextEntry linked to graduated account (RAPI-05)"
  - "POST /relationships/{id}/files — uploads to Supabase Storage via httpx, logs ContextEntry (RAPI-06)"
  - "GET /signals/ — per-type badge counts for sidebar navigation (SIG-01)"
  - "Signal taxonomy: reply_received(P1), followup_overdue(P2), commitment_due(P2), stale_relationship(P3)"
  - "Signals router registered in main.py at /api/v1"

affects: [56-frontend-pipeline-relationships]

tech-stack:
  added: []
  patterns:
    - "httpx upload pattern for Supabase Storage — POST to /storage/v1/object/{bucket}/{path} with Bearer service key (matches document_storage.py)"
    - "File size gate: read full content before upload, 413 if > 10 MB"
    - "Signal computation: 4 separate async queries per relationship type (1 OutreachActivity join, 3 Account queries)"
    - "Boolean OR predicates for stale_relationship using SQLAlchemy | operator with isnot/is_ guards"

key-files:
  created:
    - backend/src/flywheel/api/signals.py
  modified:
    - backend/src/flywheel/api/relationships.py
    - backend/src/flywheel/main.py

key-decisions:
  - "httpx used for Supabase Storage upload (not supabase-py) — matches existing document_storage.py pattern"
  - "File size validated by reading full content before upload — client gets 413 if over 10 MB limit"
  - "Signals computed as 4 separate queries per type (not window functions) — simpler, easier to reason about, DB handles it efficiently"
  - "stale_relationship uses two-branch OR: last_interaction_at < 90d ago OR (IS NULL AND created_at < 90d ago)"
  - "TypeBadge.label derived as {type.capitalize()}s — simple plural for display"

patterns-established:
  - "All signal queries: include Account.graduated_at.isnot(None) in base_filters — pipeline-only accounts always excluded"
  - "Note creation: file_name='relationship-notes', source defaults to 'manual:note'"
  - "File upload ContextEntry: file_name=filename, source='manual:file-upload', detail=storage_path"

duration: ~4min
completed: 2026-03-27
---

# Phase 55 Plan 03: Notes, Files, and Signals Summary

**Notes/files sub-resource endpoints and signals badge count API — RAPI-05/06 complete the relationship write surface, SIG-01/02 provide per-type sidebar badge counts with P1/P2/P3 signal taxonomy, all enforcing the graduated_at partition predicate**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-27
- **Completed:** 2026-03-27
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `POST /relationships/{id}/notes` (RAPI-05) creates a `ContextEntry` with `file_name="relationship-notes"` and `account_id=account.id`, returning a `NoteResponse`. Graduated_at partition predicate enforced.
- `POST /relationships/{id}/files` (RAPI-06) reads the uploaded file, validates size against 10 MB limit (413 on failure), then uploads via httpx to Supabase Storage at path `relationships/{tenant_id}/{account_id}/{filename}`. Logs a `ContextEntry` with `detail=storage_path`. Graduated_at partition predicate enforced.
- `signals.py` router with signal taxonomy constants (SIGNAL_TYPES dict), 4 relationship types, and `_compute_signals_for_type()` helper that fires 4 separate queries per type — all with `graduated_at.isnot(None)` in base_filters.
- `GET /signals/` (SIG-01) iterates all 4 relationship types, builds `TypeBadge` objects, sums signal counts, returns `SignalsResponse`.
- Signals router registered in `main.py` at `/api/v1`.

## Task Commits

Per-plan batch commit (commit_strategy=per-plan):

1. **Tasks 1+2 batch:** `b1f7a95` feat(55-03): add notes/files endpoints and signals badge count API

## Files Created/Modified

- `backend/src/flywheel/api/signals.py` — New: signals router with SIG-01 endpoint and signal taxonomy
- `backend/src/flywheel/api/relationships.py` — Added RAPI-05 (notes) and RAPI-06 (files) endpoints with new Pydantic schemas
- `backend/src/flywheel/main.py` — Import + register signals_router at /api/v1

## Decisions Made

- Used httpx directly for Supabase Storage upload to match the established `document_storage.py` pattern — supabase-py's storage API is not used in this codebase
- File content is fully read before upload so size validation is accurate; this means large files are buffered in memory but 10 MB is a reasonable ceiling for relationship attachments
- Signal queries are 4 separate simple queries per type (not a single complex window function) — easier to test, easier to extend, and Postgres handles them efficiently with the existing indexes

## Deviations from Plan

None — plan executed exactly as written. The httpx upload pattern was adapted from `document_storage.py` as instructed in the plan's note.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 8 relationships endpoints are live at `/api/v1/relationships/`
- Signals endpoint live at `/api/v1/signals/`
- Phase 55 fully complete (Plans 01, 02, 03 done)
- Phase 56 (Frontend Pipeline + Relationships) can now consume all backend APIs

---

## Self-Check

**Files exist:**
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/signals.py` — FOUND
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/relationships.py` — FOUND (RAPI-05/06 present)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/main.py` — FOUND (signals_router registered)

**Commits exist:**
- `b1f7a95` — FOUND

## Self-Check: PASSED

---
*Phase: 55-relationships-and-signals-apis*
*Completed: 2026-03-27*
