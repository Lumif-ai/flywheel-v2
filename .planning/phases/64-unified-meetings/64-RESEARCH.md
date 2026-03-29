# Phase 64: Unified Meetings - Research

**Researched:** 2026-03-28
**Domain:** Python backend (Alembic migration, calendar sync rewrite, Granola dedup, lifecycle state machine); React frontend (Upcoming/Past tabs, prep trigger from scheduled meetings)
**Confidence:** HIGH

## Summary

Phase 64 unifies two separate meeting data paths (Google Calendar -> WorkItems and Granola -> Meetings) into a single `meetings` table with lifecycle status tracking. Currently, calendar events are stored as `WorkItem` rows (type="meeting", source="google-calendar") via `upsert_meeting_work_item()` in `calendar_sync.py`, while Granola meeting notes go into `Meeting` rows via `POST /meetings/sync`. This dual-path architecture means the same real-world meeting exists in two different tables with no cross-reference.

The unification requires: (1) a migration adding `calendar_event_id`, `granola_note_id`, `location`, `description` columns to the meetings table; (2) rewriting `calendar_sync.py` to create `Meeting` rows with `processing_status='scheduled'` instead of `WorkItem` rows; (3) adding fuzzy dedup logic in Granola sync to match recorded meetings against scheduled calendar events; (4) a lifecycle status machine (scheduled -> recorded -> processing -> complete | skipped | cancelled); (5) frontend Upcoming/Past tab views; (6) a `POST /meetings/{id}/prep` endpoint; and (7) migrating `get_meeting_prep_suggestions()` to query the meetings table.

All the building blocks exist. The `Meeting` model has all core columns. The `_execute_account_meeting_prep()` in `skill_executor.py` already handles the LLM prep pipeline. The `PrepBriefingPanel` component is already integrated into `MeetingDetailPage`. The work is primarily **rewiring** existing functionality, not building new capabilities.

**Primary recommendation:** Split into 3 plans: (1) Backend migration + calendar sync rewrite + Granola dedup logic + lifecycle state machine, (2) Backend API changes (time param, prep endpoint, suggestions migration), (3) Frontend Upcoming/Past tabs + prep trigger for scheduled meetings.

## Standard Stack

### Core (all already installed -- no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | API endpoints | Already used by all routes |
| SQLAlchemy async | 2.0.x | ORM model updates, queries | Used everywhere |
| Alembic | 1.x | Migration 033 | Standard migration tool |
| google-api-python-client | latest | Calendar API (existing) | Already in calendar_sync.py |
| httpx | latest | Granola API (existing) | Already in granola_adapter.py |
| @tanstack/react-query | ^5.91.2 | Data fetching | Already standard |
| react-router | ^7.13.1 | Navigation | Already used |

### No New Dependencies

This phase is entirely rewiring -- zero new packages needed on backend or frontend.

## Architecture Patterns

### Pattern 1: Meeting Lifecycle State Machine (UNI-03)

**What:** `processing_status` column gains new states. Current valid values: `pending`, `processing`, `complete`, `failed`, `skipped`. New states added: `scheduled`, `recorded`, `cancelled`.

**State transitions:**
```
scheduled  -- (Granola match)   --> recorded
scheduled  -- (>7 days, no data) --> cancelled  [UNI-07, should-have]
recorded   -- (process-pending)  --> processing
pending    -- (process-pending)  --> processing  [backward compat for direct Granola sync]
processing -- (success)          --> complete
processing -- (failure)          --> failed
(any new)  -- (rule match)       --> skipped
```

**Key insight:** The `process-pending` endpoint currently queries `processing_status == 'pending'`. Per UNI-03, it must query both `'pending'` AND `'recorded'` so that Granola-matched calendar events get processed. This is a one-line WHERE clause change.

**Server default change:** The current server_default is `'pending'`. Calendar sync will explicitly set `'scheduled'` on insert; Granola-only sync continues to set `'pending'`. Server default stays `'pending'` for backward compatibility.

### Pattern 2: Dual-ID Dedup Strategy (UNI-01, UNI-02)

**What:** The meetings table gains two new ID columns:
- `calendar_event_id` (TEXT, nullable) -- stores the Google Calendar event ID (e.g., `"abc123xyz"`)
- `granola_note_id` (TEXT, nullable) -- stores the Granola note ID

**Dedup index evolution:**
- Current: `idx_meetings_dedup` on `(tenant_id, provider, external_id)` WHERE `external_id IS NOT NULL`
- New: Add `idx_meetings_calendar_dedup` on `(tenant_id, calendar_event_id)` WHERE `calendar_event_id IS NOT NULL`
- New: Add `idx_meetings_granola_dedup` on `(tenant_id, granola_note_id)` WHERE `granola_note_id IS NOT NULL`

**Calendar events:** `provider='google-calendar'`, `calendar_event_id=event['id']`, `external_id=f"gcal:{event['id']}"` (backward compat with WorkItem external_id format).

**Granola events:** `provider='granola'`, `granola_note_id=raw.external_id`, `external_id=raw.external_id` (existing behavior preserved).

### Pattern 3: Fuzzy Dedup for Granola Match (UNI-02)

**What:** When Granola sync finds a new meeting, check if it matches an existing `scheduled` row from calendar sync.

**Match criteria:**
1. Time window: Granola `meeting_date` within +/-30 minutes of existing `meeting_date`
2. Title similarity: case-insensitive contains or starts-with match
3. Attendee overlap: at least one attendee email in common

**Algorithm:**
```python
async def find_matching_scheduled_meeting(
    db: AsyncSession, tenant_id: UUID, raw: RawMeeting
) -> Meeting | None:
    window_start = raw.meeting_date - timedelta(minutes=30)
    window_end = raw.meeting_date + timedelta(minutes=30)

    candidates = await db.execute(
        select(Meeting).where(
            Meeting.tenant_id == tenant_id,
            Meeting.processing_status == 'scheduled',
            Meeting.meeting_date >= window_start,
            Meeting.meeting_date <= window_end,
            Meeting.deleted_at.is_(None),
        )
    )

    for candidate in candidates.scalars().all():
        if _titles_match(candidate.title, raw.title) or \
           _attendees_overlap(candidate.attendees, raw.attendees):
            return candidate
    return None
```

**On match:** Enrich the existing row with Granola data (`granola_note_id`, `ai_summary`, `transcript_url` potential), set `processing_status='recorded'`.

**No match:** Insert as a new row with `provider='granola'`, `processing_status='pending'` (existing behavior).

### Pattern 4: Calendar Sync Rewrite (UNI-04)

**What:** Replace `upsert_meeting_work_item()` with `upsert_meeting_row()` in `calendar_sync.py`.

**Critical changes:**
1. Import `Meeting` instead of `WorkItem`
2. Use `calendar_event_id` for dedup lookup (not `external_id`)
3. Set `processing_status='scheduled'` (not WorkItem `status='upcoming'`)
4. Set `provider='google-calendar'`
5. **Skip guard:** If existing row has `granola_note_id` set, do NOT overwrite -- Granola data is richer
6. Map calendar event fields: `event['description']` -> `description`, `event['location']` -> `location`
7. Parse attendees in the same format as Granola (`[{email, name, is_external}]`)
8. Remove `MeetingClassification` logic (classification happens during intelligence processing, not at calendar sync time)

**Import changes in calendar_sync.py:**
- Remove: `WorkItem, MeetingClassification, SuggestionDismissal`
- Add: `Meeting`

### Pattern 5: Meetings Page Upcoming/Past (UNI-05)

**What:** Backend `GET /meetings/` gains `time=upcoming|past` query param. Frontend shows two tabs.

**Backend logic:**
```python
now = datetime.now(timezone.utc)
if time_param == "upcoming":
    base_q = base_q.where(Meeting.meeting_date >= now)
    base_q = base_q.order_by(Meeting.meeting_date.asc())  # Soonest first
elif time_param == "past":
    base_q = base_q.where(Meeting.meeting_date < now)
    base_q = base_q.order_by(Meeting.meeting_date.desc())  # Most recent first
```

**Frontend:** Replace current status filter tabs with Upcoming/Past tabs. Upcoming shows `scheduled` + `recorded` meetings; Past shows `complete` + `processing` + `pending` + `skipped` + `failed`.

### Pattern 6: Meeting Prep from Scheduled (UNI-06)

**What:** `POST /meetings/{id}/prep` auto-links account if possible, delegates to the existing `_execute_account_meeting_prep()` pipeline.

**Key insight:** The existing `POST /relationships/{id}/prep` endpoint already does exactly this (creates a SkillRun with `Account-ID:` prefix, returns `{run_id, stream_url}`). The new `POST /meetings/{id}/prep` is a thin wrapper that:
1. Loads the Meeting row
2. If `account_id` is set, uses it directly
3. If `account_id` is NULL, calls `auto_link_meeting_to_account()` to find/create one
4. Creates a SkillRun with the `Account-ID:` + `Meeting-ID:` format
5. Returns `{run_id, stream_url}`

**Frontend:** The `PrepBriefingPanel` is already mounted on `MeetingDetailPage` when `meeting.account_id` exists. The change: show a "Prep" button even for scheduled meetings WITHOUT an account_id, and handle the auto-link response.

### Anti-Patterns to Avoid

- **Don't change the existing Granola sync path yet:** The `POST /meetings/sync` endpoint currently works for Granola-only. Add the fuzzy dedup as an additional step, not a replacement of the existing dedup-by-external_id logic.
- **Don't remove WorkItem meeting types immediately:** Other code may reference WorkItems with type="meeting". Add Meeting creation alongside WorkItem creation initially, then remove WorkItem creation once verified. Actually, per UNI-04, the requirement is clear: "replaces" -- so the switch should be clean, but verify no other code reads WorkItem meetings.
- **Don't change the processing_status server default:** Keep `'pending'` as default. Calendar sync explicitly sets `'scheduled'`. This avoids breaking existing Granola-only inserts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy time matching | Custom datetime comparison | SQL BETWEEN with timedelta | Simple, performant, handles timezone correctly |
| Title similarity | Levenshtein/fuzzy match library | Case-insensitive contains check | Meeting titles from Calendar and Granola are usually identical or one contains the other; fancy matching is overkill |
| Account linking | Custom domain extraction | Existing `auto_link_meeting_to_account()` from `meeting_processor_web.py` | Already handles domain extraction, multi-match resolution, prospect auto-creation |
| Prep pipeline | Custom LLM call | Existing `_execute_account_meeting_prep()` | Already handles context reading, LLM prompt, HTML rendering |
| SSE streaming | Custom event source | Existing `useSSE` + `SkillRun` + `job_queue_loop` | Battle-tested across 3+ phases |

## Common Pitfalls

### Pitfall 1: RLS Context Not Set for Calendar Sync Background Loop

**What goes wrong:** `calendar_sync_loop()` runs as a background task, not from an HTTP request. The `get_tenant_db` dependency sets RLS context (`app.tenant_id`, `app.user_id`). The sync loop uses `get_session_factory()` directly and must set RLS context manually.

**Why it happens:** Currently `calendar_sync.py` writes to `WorkItem` which may not have strict user-level RLS. But `Meeting` has split-visibility RLS (`meetings_owner_write` requires `user_id` match).

**How to avoid:** The sync loop must set `app.tenant_id` and `app.user_id` on the session before writing Meeting rows. This is the same pattern used elsewhere -- `await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(integration.tenant_id)})` and same for `user_id`.

**Warning signs:** `Meeting` INSERT fails silently or raises RLS violation in background sync logs.

### Pitfall 2: Granola Dedup Race Condition

**What goes wrong:** User triggers Granola sync and Calendar sync runs simultaneously. Both try to create a Meeting for the same real-world meeting.

**How to avoid:** The partial unique indexes (`idx_meetings_calendar_dedup`, `idx_meetings_granola_dedup`) provide database-level dedup. Use `ON CONFLICT DO UPDATE` or catch `IntegrityError` and handle gracefully.

### Pitfall 3: process-pending Must Query Both 'pending' AND 'recorded'

**What goes wrong:** Calendar events matched by Granola get `processing_status='recorded'` but never get processed because `process-pending` only queries `'pending'`.

**How to avoid:** UNI-03 explicitly requires this. Change the WHERE clause:
```python
Meeting.processing_status.in_(["pending", "recorded"])
```

### Pitfall 4: Calendar Event Cancellation Handling

**What goes wrong:** A calendar event is cancelled in Google Calendar. The sync sees `status=cancelled` but the Meeting row already exists with `processing_status='scheduled'`.

**How to avoid:** In `upsert_meeting_row()`, if `event.status == 'cancelled'` and existing Meeting found, set `processing_status='cancelled'`. If Granola data is already attached (`granola_note_id` is set), do NOT cancel -- the meeting happened despite calendar cancellation.

### Pitfall 5: get_meeting_prep_suggestions() Migration (UNI-08)

**What goes wrong:** `get_meeting_prep_suggestions()` currently queries `WorkItem` with `type="meeting"` and `status="upcoming"`. After Phase 64, calendar events are in `Meeting` with `processing_status='scheduled'`, so the function returns empty results.

**How to avoid:** Rewrite to query `Meeting` table where `processing_status='scheduled'` and `meeting_date` is within 48 hours. The attendee data format is the same (JSONB array of {email, name, is_external}), but `has_external_attendees` is stored differently: WorkItem stores it in `data.has_external_attendees`, Meeting stores attendees directly with `is_external` field per attendee.

### Pitfall 6: Frontend ProcessingStatus Type Needs New Values

**What goes wrong:** The `ProcessingStatus` TypeScript type only includes `'pending' | 'processing' | 'complete' | 'failed' | 'skipped'`. Missing: `'scheduled'`, `'recorded'`, `'cancelled'`.

**How to avoid:** Update the type union. Update any switch statements, filter tabs, and badge styling that use ProcessingStatus.

## Code Examples

### Migration 033: Add Calendar/Granola Columns

```python
# Source: existing migration pattern from 032_create_meetings_table.py
def upgrade() -> None:
    # Add new columns
    op.add_column("meetings", sa.Column("calendar_event_id", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("granola_note_id", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("description", sa.Text(), nullable=True))

    # Calendar dedup index
    op.create_index(
        "idx_meetings_calendar_dedup",
        "meetings",
        ["tenant_id", "calendar_event_id"],
        unique=True,
        postgresql_where=sa.text("calendar_event_id IS NOT NULL"),
    )
    # Granola dedup index
    op.create_index(
        "idx_meetings_granola_dedup",
        "meetings",
        ["tenant_id", "granola_note_id"],
        unique=True,
        postgresql_where=sa.text("granola_note_id IS NOT NULL"),
    )
    # Update pending index to also cover 'scheduled' and 'recorded'
    op.drop_index("idx_meetings_pending", table_name="meetings")
    op.create_index(
        "idx_meetings_processable",
        "meetings",
        ["tenant_id", "processing_status"],
        postgresql_where=sa.text(
            "processing_status IN ('pending', 'scheduled', 'recorded')"
        ),
    )
```

### upsert_meeting_row() Replacing upsert_meeting_work_item()

```python
# Source: adapted from existing calendar_sync.py::upsert_meeting_work_item()
async def upsert_meeting_row(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    event: dict,
) -> None:
    """Create or update a Meeting row from a Google Calendar event."""
    cal_event_id = event["id"]

    # Find existing meeting by calendar_event_id
    result = await db.execute(
        select(Meeting).where(
            Meeting.tenant_id == tenant_id,
            Meeting.calendar_event_id == cal_event_id,
        )
    )
    existing = result.scalar_one_or_none()

    # Skip if Granola data already attached
    if existing and existing.granola_note_id:
        return

    # Handle cancelled events
    if event.get("status") == "cancelled":
        if existing is not None:
            existing.processing_status = "cancelled"
        return

    # Parse meeting_date (same as current logic)
    start = event.get("start", {})
    # ... same dateTime/date parsing as current ...

    # Parse attendees into Meeting-compatible format
    attendees_raw = event.get("attendees", [])
    attendees = [
        {
            "email": a.get("email", ""),
            "name": a.get("displayName"),
            "is_external": not a.get("self", False) and not a.get("organizer", False),
        }
        for a in attendees_raw
    ]

    title = event.get("summary") or "Untitled Meeting"

    if existing is not None:
        existing.title = title
        existing.meeting_date = scheduled_at
        existing.attendees = attendees
        existing.location = event.get("location")
        existing.description = event.get("description")
        existing.processing_status = "scheduled"
    else:
        meeting = Meeting(
            tenant_id=tenant_id,
            user_id=user_id,
            provider="google-calendar",
            external_id=f"gcal:{cal_event_id}",
            calendar_event_id=cal_event_id,
            title=title,
            meeting_date=scheduled_at,
            attendees=attendees,
            location=event.get("location"),
            description=event.get("description"),
            processing_status="scheduled",
        )
        db.add(meeting)
```

### Granola Fuzzy Match in Sync

```python
# Source: new logic for POST /meetings/sync
async def _find_matching_scheduled(
    db: AsyncSession,
    tenant_id: UUID,
    raw: RawMeeting,
) -> Meeting | None:
    """Find a scheduled calendar event that matches this Granola meeting."""
    window = timedelta(minutes=30)
    result = await db.execute(
        select(Meeting).where(
            Meeting.tenant_id == tenant_id,
            Meeting.processing_status == "scheduled",
            Meeting.meeting_date >= raw.meeting_date - window,
            Meeting.meeting_date <= raw.meeting_date + window,
            Meeting.deleted_at.is_(None),
        )
    )
    candidates = result.scalars().all()

    raw_title = (raw.title or "").lower().strip()
    raw_emails = {a.get("email", "").lower() for a in (raw.attendees or []) if a.get("email")}

    for c in candidates:
        c_title = (c.title or "").lower().strip()
        c_emails = {a.get("email", "").lower() for a in (c.attendees or []) if a.get("email")}

        title_match = raw_title in c_title or c_title in raw_title
        attendee_overlap = bool(raw_emails & c_emails)

        if title_match or attendee_overlap:
            return c
    return None
```

### GET /meetings/ with time param

```python
# Source: adapted from existing list_meetings endpoint
@router.get("/")
async def list_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
    status: str | None = None,
    time: str | None = None,  # NEW: "upcoming" | "past"
    limit: int = 50,
    offset: int = 0,
) -> dict:
    now = datetime.now(timezone.utc)
    base_q = select(Meeting).where(
        Meeting.tenant_id == user.tenant_id,
        Meeting.deleted_at.is_(None),
    )

    if time == "upcoming":
        base_q = base_q.where(Meeting.meeting_date >= now)
        base_q = base_q.order_by(Meeting.meeting_date.asc())
    elif time == "past":
        base_q = base_q.where(Meeting.meeting_date < now)
        base_q = base_q.order_by(Meeting.meeting_date.desc())
    else:
        base_q = base_q.order_by(Meeting.meeting_date.desc())

    if status is not None:
        base_q = base_q.where(Meeting.processing_status == status)
    # ... rest of pagination unchanged
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Calendar events -> WorkItems | Calendar events -> Meeting rows | Phase 64 | Single source of truth for all meetings |
| Granola sync standalone | Granola sync with calendar dedup | Phase 64 | One meeting = one row, regardless of data source |
| Status filters (pending/complete/etc) | Time-based tabs (Upcoming/Past) | Phase 64 | More intuitive user mental model |
| WorkItem-based prep suggestions | Meeting-based prep suggestions | Phase 64 | Prep works for calendar-only meetings too |

**Deprecated after Phase 64:**
- `upsert_meeting_work_item()` in calendar_sync.py -- replaced by `upsert_meeting_row()`
- WorkItem rows with type="meeting" -- no longer created (existing ones remain but become stale)
- `get_meeting_prep_suggestions()` querying WorkItems -- migrated to Meeting table

## Existing Code Reference Map

Key files that need modification:

| File | Change | Impact |
|------|--------|--------|
| `backend/alembic/versions/033_*.py` | NEW migration adding 4 columns + 2 indexes | Schema |
| `backend/src/flywheel/db/models.py` | Add `calendar_event_id`, `granola_note_id`, `location`, `description` to Meeting model; update `__table_args__` indexes | ORM |
| `backend/src/flywheel/services/calendar_sync.py` | Replace `upsert_meeting_work_item()` with `upsert_meeting_row()`; update imports; add RLS context setting in sync loop | Calendar integration |
| `backend/src/flywheel/api/meetings.py` | Add `time` param to `list_meetings()`; add `POST /{id}/prep` endpoint; update `process-pending` WHERE clause; add Granola fuzzy dedup in sync | API |
| `backend/src/flywheel/services/calendar_sync.py` | `get_meeting_prep_suggestions()` rewrite to query Meeting table | Prep suggestions |
| `frontend/src/features/meetings/types/meetings.ts` | Add `scheduled`, `recorded`, `cancelled` to ProcessingStatus | Types |
| `frontend/src/features/meetings/components/MeetingsPage.tsx` | Replace status filter tabs with Upcoming/Past tabs | UI |
| `frontend/src/features/meetings/api.ts` | Add `time` param to `fetchMeetings()`, add `prepMeeting()` API function | API client |
| `frontend/src/features/meetings/components/MeetingDetailPage.tsx` | Show PrepBriefingPanel for scheduled meetings (even without account_id) | UI |

## Open Questions

1. **WorkItem cleanup timing**
   - What we know: After Phase 64, no new WorkItems with type="meeting" are created. Existing ones remain.
   - What's unclear: Should we add a migration or background task to migrate historical WorkItem meetings to Meeting rows?
   - Recommendation: Out of scope for Phase 64. Historical WorkItems stay as-is. Only new events go to Meeting table.

2. **Calendar sync RLS context pattern**
   - What we know: The background sync loop uses `get_session_factory()` directly. Meeting table has user-level RLS.
   - What's unclear: Whether the current background sync session already sets RLS variables.
   - Recommendation: Verify in Plan 01 implementation. The pattern `SET LOCAL app.tenant_id` and `SET LOCAL app.user_id` is used elsewhere and should be applied here.

3. **UNI-07 (auto-archive stale events) scope**
   - What we know: UNI-07 is marked "Should Have" in requirements. It auto-cancels scheduled meetings >7 days old with no Granola data.
   - What's unclear: Whether to include in Phase 64 or defer.
   - Recommendation: Include as a minor addition to the calendar sync loop (simple age check + status update). Low effort, high value for keeping the Upcoming tab clean.

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/src/flywheel/db/models.py` -- Meeting model (lines 1245-1321)
- Codebase: `backend/alembic/versions/032_create_meetings_table.py` -- Current schema + RLS
- Codebase: `backend/src/flywheel/services/calendar_sync.py` -- Full calendar sync implementation
- Codebase: `backend/src/flywheel/api/meetings.py` -- All meeting endpoints
- Codebase: `backend/src/flywheel/services/granola_adapter.py` -- Granola API adapter
- Codebase: `backend/src/flywheel/engines/meeting_processor_web.py` -- auto_link_meeting_to_account()
- Codebase: `backend/src/flywheel/services/skill_executor.py` -- _execute_account_meeting_prep()
- Codebase: `frontend/src/features/meetings/` -- All frontend meeting components
- Requirements: `.planning/REQUIREMENTS.md` -- UNI-01 through UNI-08

### Secondary (MEDIUM confidence)
- Prior phase research: `.planning/phases/63-meeting-prep-loop/63-RESEARCH.md` -- Prep pipeline architecture

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, zero new dependencies
- Architecture: HIGH -- all patterns derived from existing codebase with clear requirements
- Pitfalls: HIGH -- identified from direct code analysis of RLS policies, query patterns, and type definitions

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable codebase, internal architecture)
