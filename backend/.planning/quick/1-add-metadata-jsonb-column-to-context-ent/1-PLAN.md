---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - alembic/versions/017_context_entry_metadata.py
  - src/flywheel/db/models.py
  - src/flywheel/api/context.py
  - src/flywheel/storage.py
  - src/flywheel/api/briefing.py
  - src/flywheel/api/onboarding.py
  - src/flywheel/services/meeting_ingest.py
  - src/flywheel/services/slack_channel_monitor.py
  - frontend/src/types/api.ts
autonomous: true
must_haves:
  truths:
    - "context_entries table has a metadata JSONB column defaulting to empty object"
    - "All API responses for context entries include the metadata field"
    - "Callers can pass metadata when creating entries via append and batch endpoints"
    - "All 6 writer locations pass metadata through to ContextEntry construction"
  artifacts:
    - path: "alembic/versions/017_context_entry_metadata.py"
      provides: "Database migration adding metadata column"
      contains: "metadata"
    - path: "src/flywheel/db/models.py"
      provides: "ContextEntry model with metadata field"
      contains: "metadata"
    - path: "src/flywheel/api/context.py"
      provides: "Serialization and request models with metadata"
      contains: "metadata"
  key_links:
    - from: "src/flywheel/api/context.py"
      to: "src/flywheel/db/models.py"
      via: "ContextEntry.metadata field access"
      pattern: "e\\.metadata"
    - from: "src/flywheel/storage.py"
      to: "src/flywheel/db/models.py"
      via: "ContextEntry construction with metadata"
      pattern: "metadata"
---

<objective>
Add a `metadata JSONB DEFAULT '{}'` column to the context_entries table, thread it through the ORM model, API serialization, request models, frontend type, and all 6 writer locations.

Purpose: Enable arbitrary structured metadata on context entries (e.g., source URLs, classification tags, provenance info) without schema changes for each new field.
Output: Migration, model update, API plumbing, frontend type, and writer updates -- all in one pass.
</objective>

<execution_context>
Working directory: /Users/sharan/Projects/flywheel-v2/backend
Frontend at: /Users/sharan/Projects/flywheel-v2/frontend
</execution_context>

<context>
@src/flywheel/db/models.py (ContextEntry model, lines 155-214)
@src/flywheel/api/context.py (AppendEntryRequest, BatchEntryItem, _entry_to_dict)
@src/flywheel/storage.py (append_entry function)
@alembic/versions/016_nudge_interactions.py (latest migration, for revision chain)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Migration + Model + API serialization</name>
  <files>
    alembic/versions/017_context_entry_metadata.py
    src/flywheel/db/models.py
    src/flywheel/api/context.py
    src/flywheel/storage.py
    /Users/sharan/Projects/flywheel-v2/frontend/src/types/api.ts
  </files>
  <action>
1. Create `alembic/versions/017_context_entry_metadata.py`:
   - Revision ID: `017_context_entry_metadata`, revises `016_nudge_interactions`
   - upgrade: `op.add_column('context_entries', sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False))`
   - downgrade: `op.drop_column('context_entries', 'metadata')`
   - Follow the hand-written migration pattern from 016

2. In `src/flywheel/db/models.py` ContextEntry class (after line ~191, before deleted_at):
   - Add: `metadata: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'::jsonb"), nullable=False)`
   - Add `JSON` to the sqlalchemy imports if not present (from sqlalchemy import JSON, or from sqlalchemy.dialects.postgresql import JSONB -- use JSONB for PostgreSQL)

3. In `src/flywheel/api/context.py`:
   - Add `metadata: dict | None = None` to `AppendEntryRequest` (line ~41, after confidence)
   - Add `metadata: dict | None = None` to `BatchEntryItem` (line ~49, after confidence)
   - Add `"metadata": e.metadata or {}` to `_entry_to_dict` return dict (line ~78, after focus_id)

4. In `src/flywheel/storage.py` `append_entry` function:
   - Add `metadata` to the entry dict extraction: `metadata = entry.get("metadata") or {}`
   - Pass `metadata=metadata` when constructing new ContextEntry (around line 160)
   - When updating existing entry (evidence dedup path, around line 148), merge metadata: `existing.metadata = {**(existing.metadata or {}), **metadata}` if metadata is non-empty

5. In `/Users/sharan/Projects/flywheel-v2/frontend/src/types/api.ts`:
   - Add `metadata?: Record<string, unknown>` to the ContextEntry interface (after `visibility`)
  </action>
  <verify>
    - `python3 -c "from flywheel.db.models import ContextEntry; print('model ok')"` succeeds
    - `python3 -c "from flywheel.api.context import AppendEntryRequest, BatchEntryItem; print(AppendEntryRequest.model_fields.keys())"` shows metadata
    - Migration file exists and has correct revision chain
  </verify>
  <done>
    ContextEntry model has metadata JSONB field, API request/response models include metadata, migration is ready to apply, frontend type updated, storage.py passes metadata through on create and merges on dedup update.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire metadata in all 6 writer locations</name>
  <files>
    src/flywheel/api/briefing.py
    src/flywheel/api/onboarding.py
    src/flywheel/services/meeting_ingest.py
    src/flywheel/services/slack_channel_monitor.py
    src/flywheel/api/context.py
  </files>
  <action>
Each writer location directly constructs `ContextEntry(...)`. Add `metadata={}` to each construction call so the field is explicitly set. For the two API endpoints (append/batch in context.py), pass the user-supplied metadata from the request body.

1. `src/flywheel/api/briefing.py` (~line 353): `ContextEntry(... metadata={})` -- nudge submit creates knowledge-gaps entries

2. `src/flywheel/api/onboarding.py` (~line 192): `ContextEntry(... metadata={})` -- promote creates onboarding entries

3. `src/flywheel/services/meeting_ingest.py` (~line 246): `ContextEntry(... metadata={})` -- meeting ingest creates meetings.md entries

4. `src/flywheel/services/slack_channel_monitor.py` (~line 237): `ContextEntry(... metadata={})` -- slack monitor creates competitive-intel entries

5. `src/flywheel/api/context.py` append endpoint (~line 280-298): When constructing ContextEntry, pass `metadata=body.metadata or {}`. The storage.py path already handles this from Task 1, but if append endpoint constructs ContextEntry directly (check the code path), add it there too.

6. `src/flywheel/api/context.py` batch endpoint (~line 340-380): Same -- pass `metadata=item.metadata or {}` when constructing entries.

Note: The server_default handles the case where metadata is not provided, but explicit `metadata={}` in direct ORM construction is cleaner than relying on server defaults for in-memory objects.
  </action>
  <verify>
    Grep all ContextEntry construction calls to confirm none are missing metadata:
    `grep -n "ContextEntry(" src/flywheel/api/briefing.py src/flywheel/api/onboarding.py src/flywheel/services/meeting_ingest.py src/flywheel/services/slack_channel_monitor.py src/flywheel/api/context.py`
    Each hit should have `metadata=` in the surrounding lines.
  </verify>
  <done>
    All 6 writer locations explicitly pass metadata when constructing ContextEntry objects. API append/batch endpoints forward user-supplied metadata from request body.
  </done>
</task>

</tasks>

<verification>
1. Migration file has correct revision chain (revises 016, revision 017)
2. `python3 -c "from flywheel.db.models import ContextEntry"` succeeds
3. `python3 -c "from flywheel.api.context import AppendEntryRequest; print('metadata' in AppendEntryRequest.model_fields)"` prints True
4. All ContextEntry(...) construction sites include metadata=
5. Frontend ContextEntry type includes metadata field
6. _entry_to_dict includes metadata in serialized output
</verification>

<success_criteria>
- Alembic migration 017 exists and adds metadata JSONB column with '{}' default
- ContextEntry ORM model has metadata field (JSONB, not null, default empty dict)
- AppendEntryRequest and BatchEntryItem accept optional metadata dict
- _entry_to_dict serializes metadata in API responses
- All 6 direct ContextEntry() construction sites pass metadata explicitly
- Frontend ContextEntry interface includes metadata field
- storage.py append_entry extracts and passes metadata, merges on dedup
</success_criteria>

<output>
No SUMMARY needed for quick plans.
</output>
