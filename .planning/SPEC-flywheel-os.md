# Flywheel OS v4.0 — Specification

> Status: Reviewed
> Created: 2026-03-28
> Last updated: 2026-03-28 (post-review: 16 findings addressed)
> Source: CONCEPT-BRIEF-flywheel-os.md (brainstorm output, 4 rounds, 14 advisors)
> Scope: Phases A-C only (unified meetings + tasks + /flywheel CLI)

## Overview

Flywheel OS transforms the existing intelligence layer (v1.0-v3.0) into a founder's daily operating system. Conversations automatically become tracked commitments and executed deliverables. The v4.0 milestone ships the minimum viable operating system: a unified meetings timeline (Google Calendar + Granola), automatic task extraction from meeting transcripts, and a `/flywheel` CLI ritual that ties everything together.

## Core Value

**The ONE thing that cannot fail:** When a founder says "we'll send a one-pager" in a meeting, that commitment appears in their `/flywheel` task list the next time they run it — without any manual entry.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (CLI power user) | `/flywheel` in Claude Code | Review daily brief, confirm tasks, trigger processing |
| Founder (meeting-bound) | `/meetings` page (redesigned) | See upcoming + past meetings, trigger prep |
| Founder (web user) | `/brief` page *(Phase H)* | Same daily brief, visual interactive cards |
| Founder (task-tracking) | `/tasks` page *(Phase H)* | Manage detected + manual tasks, review outputs |

## Requirements

### Phase A: Unified Meetings

#### Must Have

- **UNI-01**: Migrate Google Calendar events from WorkItem to the meetings table
  - Calendar sync creates Meeting rows with `status='scheduled'` instead of WorkItem rows
  - New Alembic migration (e.g., `033_meetings_unified`) adds columns to the existing meetings table: `calendar_event_id` (text, nullable), `granola_note_id` (text, nullable), `location` (text, nullable), `description` (text, nullable). **IMPORTANT: Run against Supabase (DATABASE_URL env var), not just local DB. See Phase 60 migration lesson.**
  - Existing `provider` column used: value `'google-calendar'` for calendar-sourced, `'granola'` for Granola-sourced
  - Existing `external_id` column reused: format `gcal:{event_id}` for calendar events (same as current WorkItem.external_id)
  - `processing_status` repurposed as lifecycle status with new allowed values: `'scheduled'` | `'recorded'` | `'processing'` | `'complete'` | `'skipped'` | `'cancelled'`
  - Calendar sync loop interval unchanged (5 min / SYNC_INTERVAL=300)
  - **Acceptance Criteria:**
    - [ ] Alembic migration 033 adds `calendar_event_id`, `granola_note_id`, `location`, `description` columns to the meetings table (ALTER TABLE, not recreate)
    - [ ] Migration runs successfully against Supabase (not just local DB)
    - [ ] After calendar sync runs, `SELECT * FROM meetings WHERE provider='google-calendar'` returns rows with `processing_status='scheduled'`
    - [ ] WorkItem creation for `type='meeting'` is fully removed from `calendar_sync.py` — no new WorkItems created for calendar events
    - [ ] Existing WorkItem rows remain untouched (no data migration needed — they're ephemeral 14-day lookahead data)
    - [ ] Calendar event cancellation sets `processing_status='cancelled'` on the matching Meeting row
    - [ ] All-day events are handled (meeting_date set to start-of-day, duration_mins=null)

- **UNI-02**: Dedup Google Calendar events with Granola meetings
  - When Granola sync runs (`POST /meetings/sync`), before inserting a new row, check for a matching `scheduled` row
  - Match priority (NOTE: Granola API does NOT return Google Calendar event IDs — only `start_time`, `end_time`, `invitees`, and title. So exact ID matching is not available.):
    1. **Strong match**: Granola's `calendar_event.start_time` within ±30 minutes of a `scheduled` row's `meeting_date` AND (title match OR at least 1 attendee email overlap) → match
    2. **Title-only match**: Same time window AND title match but no attendee overlap → match (covers cases where Calendar has no attendee emails)
    3. **No match**: create a new Meeting row with `provider='granola'` (recording-only meeting, no calendar entry)
  - **Title match definition** (concrete, no fuzzy scoring): titles match if (a) case-insensitive exact match after stripping whitespace, OR (b) either title contains the other as a substring after lowering (e.g., Calendar "Acme Sync" matches Granola "Acme Sync - Notes")
  - On match: UPDATE the existing `scheduled` row — set `granola_note_id`, merge `attendees`, set `ai_summary`, update `processing_status` to `'recorded'`, set `provider` to `'granola'` (Granola becomes the authoritative source since it has the transcript)
  - **Attendee merge logic:** merge by email key. For matching emails: keep Granola's `name` (richer) + Calendar's `is_external` flag. For emails only in Calendar: keep as-is. For emails only in Granola: add with `is_external=true` (Granola invitees are external by default). Result is the union of both attendee lists with best-available data per field.
  - New column: `granola_note_id` (text, nullable) — stores Granola's note ID for content fetching
  - **Acceptance Criteria:**
    - [ ] A meeting that exists in both Google Calendar and Granola appears as ONE row in the meetings table (not two)
    - [ ] The deduplicated row has `granola_note_id` populated (and `calendar_event_id` if the original was from Google Calendar)
    - [ ] The `attendees` JSONB reflects the richer Granola data (names populated) merged with Calendar data (is_external flag)
    - [ ] A Granola meeting with no calendar match creates a new row with `calendar_event_id=null`
    - [ ] A calendar event with no Granola match stays as `processing_status='scheduled'`
    - [ ] Re-running Granola sync does not create duplicate rows for already-matched meetings

- **UNI-03**: Lifecycle status management
  - `scheduled` → Calendar event synced, meeting hasn't happened yet (or no transcript available)
  - `recorded` → Granola transcript available, not yet processed by intelligence pipeline
  - `processing` → Intelligence pipeline running (SkillRun created)
  - `complete` → Intelligence extraction finished, insights in context store
  - `skipped` → Processing rules filtered this meeting out
  - `cancelled` → Calendar event was cancelled
  - Past `scheduled` meetings (meeting_date < now - 24h) are NOT auto-archived — they stay as `scheduled` indicating no recording was made. The UI can filter these visually.
  - **Acceptance Criteria:**
    - [ ] `GET /meetings/?time=upcoming` returns only future meetings (any processing_status)
    - [ ] `GET /meetings/?status=recorded` returns meetings with transcripts awaiting processing (any time period)
    - [ ] Triggering processing on a `recorded` meeting transitions to `processing` then `complete`
    - [ ] The existing `POST /meetings/{id}/process` endpoint accepts meetings with `processing_status='recorded'` (in addition to `'pending'` for backward compat)
    - [ ] `POST /meetings/process-pending` queries for BOTH `processing_status='pending'` AND `processing_status='recorded'` (backward compat + new lifecycle)
    - [ ] The `_apply_processing_rules()` function works on Granola sync (status becomes `'skipped'` or `'recorded'` — NOT `'pending'`)

- **UNI-04**: Update calendar_sync.py to write Meeting rows
  - Replace `upsert_meeting_work_item()` with `upsert_meeting_row()` that writes to the meetings table
  - Preserve: external_id format (`gcal:{event_id}`), attendee parsing, cancellation detection, all-day event handling, classify_meeting() call
  - New: populate `calendar_event_id` = `event['id']` (raw Google Calendar ID, without `gcal:` prefix), `location` from event, `description` from event
  - Dedup by: `(tenant_id, calendar_event_id)` — if row exists with matching calendar_event_id, UPDATE title/attendees/meeting_date/location/description/status; if not, INSERT
  - Do NOT touch rows that have `granola_note_id` set (Granola is authoritative once matched)
  - `meeting_date` = event start time, `duration_mins` = (end - start) in minutes
  - `user_id` = the Integration owner's user_id
  - **Acceptance Criteria:**
    - [ ] `upsert_meeting_work_item()` no longer exists in calendar_sync.py
    - [ ] `upsert_meeting_row()` creates Meeting rows with `provider='google-calendar'`, `processing_status='scheduled'`
    - [ ] An updated calendar event (title change, time change) updates the existing Meeting row
    - [ ] A calendar event that was already matched to Granola (has `granola_note_id`) is NOT overwritten by calendar sync
    - [ ] `classify_meeting()` result stored in Meeting.meeting_type (not in WorkItem.data JSONB)
    - [ ] `has_external_attendees` flag derivable from `attendees` JSONB (at least one entry with `is_external=true`)

- **UNI-05**: Meetings page shows both upcoming and past
  - Frontend `/meetings` page gets two tabs: **Upcoming** and **Past**
  - **Upcoming tab**: meetings where `meeting_date > now()`, sorted by `meeting_date ASC` (soonest first). Shows: title, date/time, attendees, prep status indicator, location
  - **Past tab**: meetings where `meeting_date <= now()`, sorted by `meeting_date DESC` (most recent first). Shows: title, date, attendees, status badge, meeting_type badge, account link
  - Backend `GET /meetings/` endpoint gains `time` query param: `time=upcoming` (meeting_date > now) or `time=past` (meeting_date <= now). Default: no filter (all meetings)
  - Remove the current status filter tabs (pending/processing/complete/skipped) — replaced by upcoming/past temporal split
  - **Acceptance Criteria:**
    - [ ] Opening `/meetings` shows two tabs: "Upcoming" and "Past"
    - [ ] Upcoming tab shows calendar events (scheduled) with prep status indicators
    - [ ] Past tab shows processed meetings with intelligence status badges
    - [ ] A meeting with `processing_status='scheduled'` and `meeting_date` in the future appears in Upcoming
    - [ ] A meeting with `processing_status='complete'` appears in Past with a green "Complete" badge
    - [ ] Sync button in header still triggers Granola sync (POST /meetings/sync)

- **UNI-06**: Update prep trigger to work with scheduled meetings
  - The existing `POST /relationships/{id}/prep` endpoint works for graduated accounts
  - Add `POST /meetings/{id}/prep` endpoint that:
    1. Loads the Meeting row
    2. If `account_id` is set → delegates to existing account prep engine (`_execute_account_meeting_prep`)
    3. If `account_id` is null but attendees have external domains → attempt `auto_link_meeting_to_account()` first, then prep
    4. If no linkable account → return 400 with message "No account linked to this meeting. Link an account first."
  - **Response format:** `{run_id: UUID, stream_url: string}` (same contract as existing `POST /relationships/{id}/prep`)
  - **Error responses:** 404 (meeting not found), 400 (no account linked), 409 (prep already in progress for this meeting)
  - The MeetingDetailPage "Prep for Meeting" button should work for both `scheduled` (upcoming) and `recorded`/`complete` (past) meetings
  - **Acceptance Criteria:**
    - [ ] User can click "Prep for Meeting" on an upcoming calendar event that has a linked account and receive a streaming briefing
    - [ ] User clicking prep on a meeting with unknown attendees gets an informative error (not a 500)
    - [ ] Prep for a past processed meeting still works (uses accumulated intelligence)

- **UNI-08**: Meeting prep suggestions from unified table *(promoted from Should Have — breaks silently without this)*
  - The existing `get_meeting_prep_suggestions()` function in calendar_sync.py queries WorkItems. Migrate to query meetings table instead.
  - Query: `provider='google-calendar'`, `processing_status='scheduled'`, `meeting_date` within next 48 hours, at least one attendee with `is_external=true`
  - Respect existing SuggestionDismissal table
  - **Acceptance Criteria:**
    - [ ] `GET /integrations/suggestions` returns upcoming external meetings from the meetings table (not WorkItems)
    - [ ] Dismissed suggestions remain dismissed

#### Should Have

- **UNI-07**: Auto-archive stale calendar events
  - Background job (runs with calendar sync) marks `processing_status='cancelled'` on meetings where `provider='google-calendar'` AND `meeting_date < now() - 7 days` AND `granola_note_id IS NULL` AND `processing_status='scheduled'`
  - This keeps the meetings list clean — week-old unrecorded meetings fade out
  - **Acceptance Criteria:**
    - [ ] After calendar sync, meetings older than 7 days with no Granola data have `processing_status='cancelled'`
    - [ ] Meetings that were recorded (have `granola_note_id`) are never auto-archived regardless of age

#### Won't Have (this version)

- Granola webhook/polling sync — remains on-demand via `/flywheel sync` or manual button
- Calendar write-back (creating calendar events from Flywheel)
- Multi-provider calendar support (only Google Calendar)
- Automatic meeting_date timezone normalization (stored as-is from provider)

---

### Phase B: Task Intelligence

#### Must Have

- **TASK-01**: Tasks table and ORM model
  - New `tasks` table via Alembic migration with columns:
    - `id` UUID PK, `tenant_id` UUID FK(tenants), `user_id` UUID NOT NULL
    - `source` TEXT NOT NULL — `'meeting'` | `'email'` | `'manual'` *(`'system'` reserved for future: auto-generated reminders, overdue escalations)*
    - `source_id` UUID nullable — polymorphic reference to source record (meeting_id, email_id, etc.). No FK constraint (references multiple tables). Tasks persist independently of source record lifecycle.
    - `account_id` UUID nullable FK(accounts) ON DELETE SET NULL
    - `title` TEXT NOT NULL
    - `description` TEXT nullable
    - `task_type` TEXT NOT NULL — `'collateral'` | `'follow-up'` | `'intro'` | `'research'` | `'scheduling'` | `'custom'`
    - `commitment_direction` TEXT NOT NULL DEFAULT `'ours'` — `'ours'` | `'theirs'` | `'mutual'`
    - `suggested_skill` TEXT nullable — skill name that can execute this task
    - `skill_context` JSONB nullable — parameters for skill execution
    - `trust_level` TEXT NOT NULL DEFAULT `'review'` — `'silent'` | `'inform'` | `'review'` | `'confirm'` | `'never_auto'`
    - `status` TEXT NOT NULL DEFAULT `'detected'` — `'detected'` | `'confirmed'` | `'queued'` | `'in_progress'` | `'review'` | `'complete'` | `'dismissed'`
    - `priority` INTEGER DEFAULT 3 — 1 (low) to 5 (critical)
    - `due_date` TIMESTAMP TZ nullable
    - `skill_run_id` UUID nullable FK(skill_runs) — links to executing SkillRun
    - `output_type` TEXT nullable — `'document'` | `'email_draft'` | `'briefing'`
    - `output_ref` TEXT nullable — file path, draft ID, URL
    - `created_at` TIMESTAMP TZ DEFAULT now(), `updated_at` TIMESTAMP TZ DEFAULT now(), `completed_at` TIMESTAMP TZ nullable
    - `deleted_at` TIMESTAMP TZ nullable — soft delete
  - RLS: user-level isolation (`user_id = current_setting('app.user_id', true)::uuid`). Tasks are Zone 1 (private to the user who owns them).
  - Indexes: `(tenant_id, user_id, status)` WHERE deleted_at IS NULL; `(source, source_id)` for source lookups; `(account_id)` WHERE deleted_at IS NULL
  - **Acceptance Criteria:**
    - [ ] `alembic upgrade head` creates the tasks table with all columns, indexes, and RLS policies
    - [ ] User A's tasks are invisible to User B in the same tenant (RLS enforced)
    - [ ] `Task` ORM model exists in models.py with all columns and relationships

- **TASK-02**: Task extraction from meeting transcripts
  - After the intelligence pipeline completes (Stage 6 "Writing" in `_execute_meeting_processor`), add a new **Stage 7: "Task Extraction"**
  - Call Claude Haiku with a task extraction prompt that receives:
    - Meeting transcript (or AI summary if transcript too long)
    - Meeting title, attendees, account name (if linked)
    - Existing tasks for this account (to avoid duplicates)
  - The LLM classifies each detected commitment into one of 5 categories:
    - **Your commitment** → creates Task with `commitment_direction='ours'`, `status='detected'`
    - **Their commitment** → creates Task with `commitment_direction='theirs'`, `status='detected'`
    - **Mutual next step** → creates Task with `commitment_direction='mutual'`, `status='detected'`
    - **Soft signal** → NOT a task, written as ContextEntry (already handled by existing pipeline)
    - **Idle speculation** → ignored
  - For each "your commitment" task, the LLM also suggests:
    - `task_type` — one of the allowed values
    - `suggested_skill` — a skill name if applicable (e.g., `'sales-collateral'`, `'email-draft'`) or null
    - `skill_context` — JSONB with relevant parameters (account name, vertical, angle, etc.)
    - `priority` — 1-5 based on urgency signals in the transcript
    - `due_date` — if a date/timeframe was mentioned ("by Friday", "next week"), parse to timestamp; otherwise null
  - Task `source='meeting'`, `source_id=meeting.id`, `account_id=meeting.account_id`
  - `trust_level` assignment:
    - Tasks with `suggested_skill` containing email-send actions → `'confirm'`
    - Tasks with `suggested_skill` for content generation → `'review'`
    - Tasks with no suggested_skill → `'inform'`
    - ALL email sending → `'confirm'` (HARD CONSTRAINT — never auto-send)
  - **Acceptance Criteria:**
    - [ ] After processing a meeting with transcript "We'll send them a security one-pager by Friday", a Task row exists with `title` containing "security one-pager", `task_type='collateral'`, `suggested_skill='sales-collateral'`, `due_date` set to next Friday
    - [ ] After processing a meeting where the other party says "I'll send the requirements", a Task row exists with `commitment_direction='theirs'`
    - [ ] "We should grab coffee sometime" does NOT create a task
    - [ ] "Let's schedule a follow-up next week" creates a task with `task_type='scheduling'`, `commitment_direction='mutual'`
    - [ ] Tasks are deduplicated: re-processing the same meeting does not create duplicate tasks (check by `source='meeting'` AND `source_id=meeting_id` AND similar title)
    - [ ] All tasks with email-related skills have `trust_level='confirm'`
    - [ ] Haiku token usage for task extraction is tracked in the same SkillRun.tokens_used field (Stage 7 adds to existing token count, not a separate run)

- **TASK-03**: Tasks CRUD API
  - New router: `backend/src/flywheel/api/tasks.py` mounted at `/api/v1/tasks`
  - Endpoints:
    - `GET /tasks/` — paginated list with filters: `status` (comma-separated), `commitment_direction`, `source`, `account_id`, `priority_min`. Default: excludes `dismissed` and `complete`. Sort by `priority DESC, created_at DESC`. **Response:** `{items: [{id, title, description, source, source_id, account_id, task_type, commitment_direction, suggested_skill, skill_context, trust_level, status, priority, due_date, output_type, output_ref, created_at, completed_at}], total, limit, offset}`
    - `GET /tasks/{id}` — single task detail. **Response:** full task object (same shape as list item). **Errors:** 404 not found.
    - `POST /tasks/` — create manual task. **Body:** `{title, description?, task_type?, account_id?, priority?, due_date?}`. Sets `source='manual'`, `status='detected'`, `commitment_direction='ours'`. **Response:** full task object. **Errors:** 400 if title missing.
    - `PATCH /tasks/{id}` — update task fields (title, description, priority, due_date, status, account_id). Validates status transitions (see state machine below). **Response:** full task object. **Errors:** 400 invalid transition, 404 not found.
    - `POST /tasks/{id}/confirm` — shortcut: sets `status='confirmed'`. **Response:** `{id, status}`. **Errors:** 400 if not in `detected` state, 404 not found.
    - `POST /tasks/{id}/dismiss` — shortcut: sets `status='dismissed'`. **Response:** `{id, status}`. **Errors:** 404 not found.
    - `DELETE /tasks/{id}` — soft delete (sets deleted_at). **Response:** 204 No Content.
  - Status transitions (enforced):
    - `detected` → `confirmed` | `dismissed`
    - `confirmed` → `queued` | `dismissed`
    - `queued` → `in_progress`
    - `in_progress` → `review` | `complete` | `detected` (on failure, reset)
    - `review` → `complete` | `detected` (reject output, redo)
    - `dismissed` → `detected` (un-dismiss / recover)
  - All endpoints scoped by `user_id = user.sub` (Zone 1 privacy)
  - **Acceptance Criteria:**
    - [ ] `GET /tasks/` returns only the calling user's tasks (RLS + API filter)
    - [ ] `POST /tasks/` with `{title: "Call John"}` creates a task with `source='manual'`, `status='detected'`
    - [ ] `POST /tasks/{id}/confirm` transitions from `detected` to `confirmed`
    - [ ] `PATCH /tasks/{id}` with `{status: 'complete'}` from `detected` returns 400 (invalid transition)
    - [ ] `POST /tasks/{id}/dismiss` sets status to `dismissed`; `PATCH` back to `detected` recovers it
    - [ ] `GET /tasks/?status=detected,confirmed` returns only detected and confirmed tasks
    - [ ] Pagination works: `limit`, `offset`, `total` in response

- **TASK-04**: Task counts in signals endpoint
  - Extend `GET /api/v1/signals/` to include task counts:
    - `tasks_detected` — count of tasks with `status='detected'` (need attention)
    - `tasks_in_review` — count with `status='review'` (outputs to approve)
    - `tasks_overdue` — count where `due_date < now()` AND `status NOT IN ('complete', 'dismissed')`
  - These feed the sidebar badge counts and the `/brief` page
  - **Acceptance Criteria:**
    - [ ] `GET /signals/` response includes `tasks_detected`, `tasks_in_review`, `tasks_overdue` integer fields
    - [ ] Creating a new detected task increments `tasks_detected` count on next signals fetch
    - [ ] Completing a task decrements the relevant count

#### Should Have

- **TASK-05**: "Their commitments" surface in relationship detail
  - Tasks with `commitment_direction='theirs'` appear in the relationship detail's Commitments tab under "What They Owe"
  - Requires: relationship detail endpoint includes tasks query filtered by `account_id` and `commitment_direction='theirs'`
  - **Acceptance Criteria:**
    - [ ] Relationship detail for Acme shows "Sarah will send requirements doc" under "What They Owe"
    - [ ] Only tasks linked to that account appear (not all tasks)

- **TASK-06**: Task extraction prompt tuning
  - The extraction prompt must handle these patterns reliably:
    - Explicit: "We'll send the one-pager" → your commitment
    - Implicit: "I can have that to you by Friday" → your commitment with due_date
    - Delegation: "Let me have our team look into that" → your commitment, type=research
    - Polite deflection: "That's interesting, we should explore that" → NOT a task (soft signal)
    - Their action: "I'll loop in our CTO" → their commitment
    - Calendar: "Let's find time next week" → mutual, type=scheduling
  - Include 8-10 few-shot examples in the extraction prompt
  - Use Claude Haiku for cost efficiency (task extraction runs on every processed meeting)
  - **Acceptance Criteria:**
    - [ ] The extraction prompt with few-shot examples is stored as a constant in the meeting processor module
    - [ ] Processing a test transcript with all 6 patterns above produces correct task classifications

#### Won't Have (this version)

- Task extraction from emails (Phase F)
- Task extraction from Slack (deferred)
- Auto-skill execution of detected tasks (Phase E) — tasks are detected and displayed, not auto-executed
- Context assembly cache / context_bundles table (Phase E dependency)
- Task priority auto-adjustment based on account importance

---

### Phase C: The /flywheel Ritual

#### Must Have

- **FLY-01**: `/flywheel` Claude Code skill
  - New skill at `skills/flywheel/SKILL.md`
  - Invoked via `/flywheel` in Claude Code (no subcommand = full brief)
  - The skill reads from the Flywheel API (authenticated via the user's session/token) to assemble the daily brief
  - Sections (all present in full brief):
    1. **UPCOMING** — meetings in next 24h from `GET /meetings/?time=upcoming&limit=10`
    2. **PENDING TASKS** — from `GET /tasks/?status=detected,confirmed&limit=10`
    3. **UNPROCESSED** — meetings with `processing_status='recorded'` from `GET /meetings/?status=recorded&limit=10`
    4. **OUTREACH** — daily quota status (reads from GTM outreach tracker if available, otherwise hidden)
  - Output format: styled CLI output matching the design in the concept brief
  - **Acceptance Criteria:**
    - [ ] User types `/flywheel` in Claude Code and sees a formatted daily brief with all 4 sections
    - [ ] Sections with zero items show "None" (not omitted)
    - [ ] Each section shows correct data from the API
    - [ ] The brief header shows today's date and day of week

- **FLY-02**: `/flywheel sync` subcommand
  - Triggers `POST /meetings/sync` (Granola pull)
  - Shows sync results: `{synced} new, {skipped} filtered, {already_seen} existing`
  - If synced > 0, prompts: "Process {synced} new meeting(s)? (y/n)"
  - On yes: triggers `POST /meetings/process-pending`
  - On no: meetings stay as `recorded`, appear in UNPROCESSED section next run
  - **Acceptance Criteria:**
    - [ ] `/flywheel sync` pulls from Granola and shows counts
    - [ ] User can confirm processing of new meetings
    - [ ] After sync + process, `/flywheel` shows new tasks extracted from processed meetings

- **FLY-03**: `/flywheel tasks` subcommand
  - Shows only the PENDING TASKS section with numbered list
  - For each task, shows: number, title, source, suggested skill, available actions
  - **Conversational interaction model** (Claude Code skills are message-based, not interactive terminals):
    - Skill displays the list and says "Reply with a task number + action (e.g., '1 confirm', '3 dismiss', 'all confirm')"
    - User replies in the next message: `1 confirm`, `1 dismiss`, `all confirm`, `all dismiss`
    - Skill processes the action via API calls (POST /tasks/{id}/confirm, etc.) and re-displays the updated list
    - Each user message is a new conversational turn, not a prompt loop
  - **Acceptance Criteria:**
    - [ ] `/flywheel tasks` shows detected and confirmed tasks with numbered list
    - [ ] User replies "1 confirm" and the skill confirms that task and re-displays
    - [ ] User replies "all confirm" and the skill confirms all detected tasks
    - [ ] User replies "3 dismiss" and the skill dismisses that task
    - [ ] After each action, the updated task list is shown

- **FLY-04**: `/flywheel prep` subcommand
  - Shows only the UPCOMING section with numbered list
  - For meetings with linked accounts: shows prep status (ready / not started)
  - For meetings with unknown contacts: shows "Unknown contact — link account to enable prep"
  - **Conversational interaction:** skill displays list, user replies with `1 prep` or `all prep` (preps all external meetings with linked accounts)
  - Shows SSE streaming progress during prep generation
  - **Acceptance Criteria:**
    - [ ] `/flywheel prep` shows upcoming meetings with prep status
    - [ ] User replies "1 prep" and the skill triggers prep with SSE streaming feedback
    - [ ] User replies "all prep" and external meetings with linked accounts are prepped sequentially
    - [ ] Internal meetings (no external attendees) show "Internal — skipped"
    - [ ] Meetings with unknown contacts show actionable message (not a blank or error)

- **FLY-05**: `/flywheel process` subcommand
  - Shows only the UNPROCESSED section with numbered list
  - Lists meetings with `processing_status='recorded'`
  - **Conversational interaction:** user replies with `1 process`, `all process`
  - Shows progress as meetings are processed
  - **Acceptance Criteria:**
    - [ ] `/flywheel process` shows unprocessed meetings
    - [ ] User replies "all process" and all recorded meetings are queued for processing
    - [ ] After processing, extracted tasks appear in subsequent `/flywheel tasks` call

- **FLY-06**: API authentication for CLI
  - The `/flywheel` skill needs to call Flywheel's REST API
  - Authentication: the skill reads the user's auth token from the Flywheel MCP context store or environment variable (`FLYWHEEL_API_TOKEN`)
  - Base URL: configurable via `FLYWHEEL_API_URL` env var (default: `http://localhost:8000/api/v1`)
  - All API calls include `Authorization: Bearer {token}` header
  - On 401: prompt user to re-authenticate ("Your session has expired. Please re-login in the Flywheel web app.")
  - **Acceptance Criteria:**
    - [ ] `/flywheel` works when `FLYWHEEL_API_TOKEN` is set in the environment
    - [ ] `/flywheel` gives a clear error when no token is configured
    - [ ] Expired tokens produce a re-auth message (not a stack trace)

#### Should Have

- **FLY-07**: `/flywheel` shows outreach section *(lowest ROI in spec — can defer without impacting core value)*
  - If GTM outreach tracker exists (`~/.claude/gtm-stack/outreach-tracker.csv`), show outreach section:
    - Count contacts reached today
    - Show target quota (from memory/config, default 30)
    - Offer to run pipeline: "Run pipeline for next batch? (y/n)"
  - If tracker doesn't exist, hide this section entirely
  - **Acceptance Criteria:**
    - [ ] Outreach section appears when tracker CSV exists
    - [ ] Outreach section is hidden when no tracker exists
    - [ ] Counts reflect today's outreach activity

- **FLY-08**: Smart defaults with "run all"
  - When user selects "(a) Run all with smart defaults":
    1. Sync Granola (if connected)
    2. Process all unprocessed meetings
    3. Confirm all detected tasks (but NOT execute — just confirm)
    4. Skip outreach (never auto-run outreach)
  - Shows summary of what was done
  - **Acceptance Criteria:**
    - [ ] "Run all" syncs, processes, and confirms in sequence
    - [ ] Outreach is never included in "run all"
    - [ ] User sees a summary of actions taken

#### Won't Have (this version)

- Web UI for /brief page (Phase H)
- Web UI for /tasks page (Phase H)
- Contact discovery flow in CLI (Phase D)
- Auto-skill execution from confirmed tasks (Phase E)
- Email task extraction integration (Phase F)
- GTM outreach pipeline execution from CLI (Phase G)
- Push notifications or email summaries

---

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Calendar event with no attendees | Create Meeting row with `attendees=[]`, skip prep suggestions |
| Granola sync when not connected | `POST /meetings/sync` returns 400: "Granola not connected. Add your API key in Settings." |
| Granola meeting matches multiple calendar events (time overlap) | Score by: exact title match (3 points) + substring title match (2 points) + attendee overlap count (1 point each). Pick highest score; if tie, match the closest by meeting_date |
| Calendar event updated after Granola match | Calendar sync skips rows with `granola_note_id` set — Granola is authoritative |
| Task extraction returns empty (no commitments in transcript) | No tasks created, no error — normal for internal/casual meetings |
| LLM task extraction fails (API error) | Log error, skip task extraction, meeting still marked `complete` (intelligence extraction succeeded) |
| Task with `due_date` in the past at time of detection | Create with `due_date` as-is — the overdue count will reflect it immediately |
| User dismisses a task then wants it back | `PATCH /tasks/{id}` with `{status: 'detected'}` recovers the task |
| Manual task with no account link | Valid — `account_id=null`, task exists independently |
| Meeting processed twice (race condition) | Existing guard: `POST /meetings/{id}/process` returns 409 if `processing_status` not in allowed start states. Task extraction also dedup-checks by (source, source_id). |
| `/flywheel` with no meetings and no tasks | Show all sections with "None" — don't show an empty state or error |
| Calendar sync runs while Granola sync is in progress | Safe — calendar sync skips rows with `granola_note_id`. Granola sync uses `external_id` dedup. No conflict. |
| `FLYWHEEL_API_TOKEN` not set | `/flywheel` prints: "Set FLYWHEEL_API_TOKEN to connect. Run `flywheel auth` in the web app to get your token." |
| API returns 500 during `/flywheel` | Show error for that section, continue rendering others. "UPCOMING: Error fetching meetings (500). Other sections unaffected." |

## Constraints

- **Email sending is NEVER automatic.** All email-related tasks require `trust_level='confirm'` and explicit user approval. This is a hard safety constraint from the founder. (Decision #5)
- **Task extraction uses Haiku, not Sonnet.** Cost efficiency — extraction runs on every processed meeting. Sonnet is reserved for intelligence extraction (existing pipeline). (Decision from advisory theme 4: scope discipline)
- **No new packages.** All required libraries (FastAPI, SQLAlchemy, httpx, Anthropic SDK) are already installed.
- **Alembic migration IDs must be <=32 chars.** Constraint from `alembic_version.version_num` varchar(32). (Decision from Phase 54)
- **No FK to profiles table.** Supabase Auth manages profiles — FK constraints fail during migration. Use RLS for user isolation. (Discovered during Phase 60 migration)
- **Calendar sync interval unchanged (5 min).** Don't increase polling frequency — Google Calendar API has rate limits.
- **WorkItem table is not modified or dropped.** Other features may still use WorkItems. Calendar sync stops creating meeting-type WorkItems but the table stays.

## Anti-Requirements

- This is NOT a project management tool. Tasks are conversation-derived commitments, not Jira tickets. No sprints, no story points, no assignments to other people.
- This does NOT auto-execute tasks. Phase B detects and displays tasks. Auto-execution is Phase E. The v4.0 milestone is about VISIBILITY, not automation.
- This does NOT replace the existing meeting intelligence pipeline. Task extraction is an ADDITIONAL stage (Stage 7), not a replacement for Stages 1-6.
- This is NOT multi-user task assignment. Tasks belong to the user who was in the meeting. Team task visibility is a future concern.
- The `/flywheel` CLI is NOT a general-purpose shell. It reads from the API and displays results. It does not modify backend code, run migrations, or manage infrastructure.

## Open Questions

- [x] **Granola calendar_event metadata**: RESOLVED — Granola's `/v1/notes` response includes `calendar_event` with `start_time`, `end_time`, `invitees` but does NOT include a Google Calendar event ID. Dedup uses fuzzy matching only (time window + attendee overlap). Confirmed via code inspection of `granola_adapter.py`.
- [ ] **Task extraction prompt tuning**: The 5-category classification needs iteration with real transcripts. Plan for 2-3 rounds of prompt refinement post-launch.
- [ ] **Multi-tenant task visibility**: Tasks are currently Zone 1 (user-private). If team leads need visibility into team commitments, this requires a `visibility` column and RLS policy change. Deferred.
- [ ] **WorkItem deprecation timeline**: Calendar sync will stop creating meeting-type WorkItems. When can the WorkItem meeting code paths be fully removed? Depends on whether other features reference WorkItem meetings.
- [ ] **`/flywheel` authentication UX**: The current spec uses an env var for the API token. A smoother flow might be: user runs `/flywheel auth` which opens a browser window, user logs in, token is saved to `.env`. This is a UX polish item for later.

## Artifacts Referenced

- CONCEPT-BRIEF-flywheel-os.md — brainstorm output (4 rounds, 14 advisors, 12 locked decisions)
- Existing codebase: models.py (WorkItem lines 405-435, Meeting lines 1245-1322, ContextEntry lines 181-247), calendar_sync.py, granola_adapter.py, meetings.py, meeting_processor_web.py, skill_executor.py
- Existing migrations: 032_create_meetings_table.py (current meetings schema)
- Existing skills: meeting-prep, meeting-processor, sales-collateral, email-draft

---

## Gaps Found and Resolved

*All gaps from generation + review have been addressed in the spec above.*

1. **WorkItem → Meeting migration scope** — RESOLVED: UNI-08 promoted to Must Have.
2. **Granola sync status value change** — RESOLVED: UNI-03 AC explicitly covers `'recorded'` + backward compat with `'pending'`.
3. **Calendar event ID format** — RESOLVED: dual-ID pattern documented in UNI-01 and UNI-04.
4. **`/flywheel` skill HTTP mechanism** — RESOLVED: FLY-06 specifies auth via env var. Skill uses Bash tool (curl) for API calls — standard Claude Code skill pattern. Confirmed during planning.
5. **Alembic migration explicit** — RESOLVED: UNI-01 now specifies migration 033 with ALTER TABLE. Supabase deployment note added.
6. **CLI interactivity model** — RESOLVED: FLY-03/04/05 rewritten as conversational turns (message-based), not interactive terminal prompts.
7. **Dedup title matching** — RESOLVED: replaced vague "≥80% similarity" with concrete rules (exact match OR substring containment).
8. **UNI-03 temporal vs status** — RESOLVED: AC now uses `time=upcoming` for temporal filtering, `status=recorded` for lifecycle filtering.
9. **POST /meetings/{id}/prep response** — RESOLVED: response format `{run_id, stream_url}` and error codes (400/404/409) specified.
10. **TASK-03 response formats** — RESOLVED: all 7 endpoints now have response shapes and error codes.
11. **Attendee merge logic** — RESOLVED: merge-by-email-key rules specified (Granola name + Calendar is_external).
12. **Users & Entry Points** — RESOLVED: web-only entry points annotated as Phase H.
13. **source_id polymorphic FK** — RESOLVED: documented as no FK constraint, tasks persist independently.
14. **'system' source value** — RESOLVED: marked as reserved for future use.
15. **FLY-04 discovery reference** — RESOLVED: replaced with actionable "Unknown contact" message.
16. **Task extraction cost** — RESOLVED: AC added confirming Haiku tokens tracked in same SkillRun.
