# Email-to-Tasks — Specification

> Status: Reviewed
> Created: 2026-03-29
> Last updated: 2026-03-29
> Source: CONCEPT-BRIEF-email-to-tasks.md (3-round brainstorm)
> Review: 14 findings addressed (5 functional, 5 friction, 4 hygiene)

## Overview

Convert high-priority scored emails into tracked tasks automatically during the flywheel ritual. Layer A: no new LLM calls — uses existing email score metadata (category, priority, suggested_action, reasoning) to create Task rows. Runs as a new channel-agnostic ritual stage between meeting processing and meeting prep. Includes dedup guard and volume control.

The stage is designed as an **extensible channel extraction framework**. Email is the first channel; Slack, calendar events, and future sources plug into the same stage via a shared extractor interface (see Channel Extractor Architecture below).

## Core Value

**Commitments made in any channel are tracked with the same fidelity as commitments made in meetings.** The founder sees one unified task list regardless of which channel the commitment came from.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (primary) | Runs `/flywheel` ritual | See email-sourced tasks alongside meeting-sourced tasks in daily brief |
| Founder (review) | Opens `/tasks` page | Review, confirm, or dismiss email-detected tasks; view full task history with resolution metadata |

## Requirements

### Must Have

- **ETL-01**: New ritual stage "Channel Task Extraction" inserted between Stage 2 (meeting processing) and Stage 3 (meeting prep) — no renumbering of existing stages
  - **Acceptance Criteria:**
    - [ ] Stage executes as part of `execute_flywheel_ritual()` between `_stage_2_process()` and `_stage_3_prep()` calls — existing function names are NOT renamed
    - [ ] Stage emits SSE events via `_append_event_atomic()` with stage name `"extracting_channel_tasks"` and progress messages — existing SSE stage names (`"syncing"`, `"processing"`, `"prepping"`, `"executing"`, `"composing"`) are unchanged
    - [ ] Stage is non-fatal — if it fails, ritual continues to prep/execute/brief stages
    - [ ] Stage results are captured in `stage_results["channel_tasks"]` (channel-agnostic key, not email-specific) for the daily brief
    - [ ] Stage function accepts a list of channel extractors and runs each in sequence — email extractor is the first; future channels (Slack, etc.) register here

- **ETL-02**: Query qualifying emails — emails scored since the last successful ritual run, filtered by `category IN ('action_required', 'meeting_followup') AND priority >= 4`
  - **Acceptance Criteria:**
    - [ ] "Last ritual run" is determined by querying `skill_runs` for `MAX(created_at) WHERE skill_name='flywheel' AND status='complete'` for the current tenant/user (SkillRun has no `completed_at` column — `created_at` is the available timestamp)
    - [ ] Only emails with `email_scores.scored_at > last_ritual_created_at` are candidates
    - [ ] If no prior ritual run exists (first run), lookback is 7 days from now
    - [ ] First-run results are capped at top 15 emails ordered by `priority DESC, received_at DESC`
    - [ ] Emails already linked to a task are excluded via `NOT EXISTS (SELECT 1 FROM tasks t WHERE t.email_id = e.id)` using the FK column (not JSONB metadata) — this is indexed

- **ETL-03**: Create Task rows from qualifying email score metadata
  - **Acceptance Criteria:**
    - [ ] Task `source` = `"email"`
    - [ ] Task `title` = email subject with `Re:`, `Fwd:`, `Fw:` prefixes stripped (case-insensitive)
    - [ ] Task `description` = `"From: {sender_name} ({sender_email})\n{snippet}\n\nScorer reasoning: {reasoning}"`
    - [ ] Task `trust_level` = `"review"` by default, BUT if `suggested_skill` contains "email" (e.g., `"email-drafter"`), override to `"confirm"` — mirrors the existing safety invariant in meeting task extraction (meeting_processor_web.py L933-937)
    - [ ] Task `status` = `"detected"`
    - [ ] Task `commitment_direction`: `"yours"` when `category='action_required'` (email demands action from you), `"mutual"` when `category='meeting_followup'` (direction is ambiguous without body analysis — Layer B can refine)
    - [ ] Task `task_type` = mapped from email score category: `action_required` → `"followup"`, `meeting_followup` → `"followup"`
    - [ ] Task `priority` = mapped from email score priority: 5 → `"high"`, 4 → `"medium"` (category-independent — a priority-5 meeting_followup is still "high")
    - [ ] Task `email_id` = email.id (FK column, used for idempotency)
    - [ ] Task `account_id` = resolved from `email_scores.sender_entity_id` → entity's linked account (if any)
    - [ ] Task `meeting_id` = NULL (email-sourced, not meeting-sourced)
    - [ ] Task `metadata_` includes `{"email_score_id": "<score.id>", "gmail_thread_id": "<email.gmail_thread_id>"}` (no `email_id` in metadata — it has its own FK column)
    - [ ] Task `suggested_skill` = mapped from `suggested_action`: `"draft_reply"` → `"email-drafter"`, others → NULL

- **ETL-04**: Dedup guard — check for potential duplicate tasks before creation
  - **Acceptance Criteria:**
    - [ ] For each candidate email task, query open tasks (status NOT IN `('done', 'dismissed')`) for the same `account_id` (if non-null) OR same tenant/user (if no account)
    - [ ] Normalize titles for comparison: lowercase, strip `Re:/Fwd:/Fw:` prefixes, strip leading/trailing whitespace, remove stop words (`the, a, an, to, for, with, on, in, at, by, up, and, or, of, is, it`)
    - [ ] Match criteria: ≥ 50% of the shorter title's non-stop-words overlap with the other title's non-stop-words, AND existing task was created within 48 hours
    - [ ] Minimum 2 meaningful words required in candidate title to attempt dedup (single-word titles skip dedup)
    - [ ] If match found: still create the task (over-detect principle), but set `metadata_.duplicate_of_task_id` = matched task's ID
    - [ ] If match found: log at INFO level: `"Potential duplicate detected: '{new_title}' ↔ '{existing_title}' (task {existing_id})"`
    - [ ] Tasks with `duplicate_of_task_id` set are visually flagged in the daily brief (see ETL-06)
    - [ ] Dedup is cross-source — email tasks are checked against meeting-sourced tasks too (most important case: same commitment detected in both channels)

- **ETL-05**: Schema migration — add resolution metadata and source linking fields to tasks table
  - **Acceptance Criteria:**
    - [ ] New nullable column `email_id` (UUID, FK → emails.id, ondelete SET NULL) on tasks table — used for idempotency checks and source linking
    - [ ] New nullable column `resolved_by` (TEXT) on tasks table — allowed values: `"user"`, `"system"`. NOTE: these columns will be NULL for all Layer A tasks — they are schema prep for the commitment ledger (Layer B cross-channel resolution). Adding them now avoids a future migration.
    - [ ] New nullable column `resolution_source_id` (UUID, no FK — intentionally unconstrained, polymorphic reference to emails.id, meetings.id, or future resolution sources) on tasks table
    - [ ] New nullable column `resolution_note` (TEXT) on tasks table
    - [ ] New index `idx_tasks_email` on `(email_id)` for idempotency lookups
    - [ ] New index `idx_tasks_source` on `(tenant_id, user_id, source)` for filtering by source
    - [ ] Migration is backwards-compatible — all new columns are nullable, no existing data affected
    - [ ] `duplicate_of_task_id` stored in existing `metadata_` JSONB (no FK constraint, no index — dedup is advisory, not enforced. Layer B may promote to a real column.)
    - [ ] RLS safety: `email_id` FK has no cross-user risk because email task extraction always runs in the context of the current user — both email and task share the same `user_id` by construction

- **ETL-06**: Daily brief integration — new "Detected Tasks" section for channel-extracted tasks
  - **Acceptance Criteria:**
    - [ ] New section "DETECTED TASKS" added to the HTML daily brief, rendered by a new `_render_detected_tasks_section()` helper — separate from the existing `_render_tasks_section()` which shows *executed* tasks
    - [ ] Section appears after Processing Summary and before Meeting Prep in the brief layout
    - [ ] Each email task shows: title, sender name, "Source: email" badge, priority indicator (high=red, medium=amber)
    - [ ] Tasks with `duplicate_of_task_id` in metadata show a "possible duplicate" label with the matched task's title
    - [ ] First-run message appears above the section: "Found {N} actionable emails from the last 7 days. Showing top 15 by priority."
    - [ ] First-run message only appears when `is_first_run=true` in stage summary (see ETL-10)
    - [ ] If no email tasks detected, section shows "No new email tasks" (don't omit the section — confirms the stage ran)
    - [ ] Section is source-agnostic in structure — when Slack extraction lands, Slack-sourced tasks render in the same section with "Source: slack" badge

- **ETL-07**: Task API — expose new fields in existing endpoints and add `source` filter
  - **Acceptance Criteria:**
    - [ ] `GET /tasks/` supports `source` query parameter for filtering (e.g., `?source=email`). If the existing endpoint doesn't have this filter, add it as an optional `Query(default=None)` param with `WHERE source = :source` when provided.
    - [ ] `GET /tasks/{id}` response includes `email_id`, `resolved_by`, `resolution_source_id`, `resolution_note` when non-null
    - [ ] `PATCH /tasks/{id}` accepts `resolved_by`, `resolution_source_id`, `resolution_note` for updates
    - [ ] `GET /tasks/summary` counts include email-sourced tasks (verify it's source-agnostic — no change needed if it counts all tasks)
    - [ ] Task response serialization includes `metadata_.duplicate_of_task_id` when present

### Should Have

- **ETL-08**: Suggested skill mapping from email score signals
  - **Acceptance Criteria:**
    - [ ] `suggested_action="draft_reply"` → `suggested_skill="email-drafter"`, `skill_context={"email_id": ..., "gmail_thread_id": ...}`, `trust_level="confirm"` (email-sending safety invariant)
    - [ ] `category="meeting_followup"` → `suggested_skill=null` (meeting follow-ups are context-dependent)
    - [ ] Skill context includes enough data for task execution stage to invoke the skill without additional lookups

- **ETL-09**: Entity-to-account resolution for email tasks
  - **Acceptance Criteria:**
    - [ ] When `sender_entity_id` is set on the email score, look up the entity's linked account
    - [ ] If entity has `entity_type="company"` and a linked account exists, set task `account_id`
    - [ ] If entity is a person, check if any account has that person as a contact, set task `account_id`
    - [ ] If no account link found, `account_id` remains NULL
    - [ ] Check if a reusable `entity_to_account()` helper exists in the codebase (CRM, account intelligence) before building a new one — if not, implement as a shared utility in `db/` or `services/` for reuse by future channel extractors

- **ETL-10**: Stage output summary for brief composition
  - **Acceptance Criteria:**
    - [ ] Stage returns a summary dict: `{"total_scored": N, "tasks_created": M, "duplicates_found": D, "skipped_existing": S, "is_first_run": bool}`
    - [ ] Summary is logged at INFO level
    - [ ] Summary is included in stage_results for brief rendering

### Won't Have (this version)

- **Layer B body extraction** — Ephemeral Gmail body fetch + Haiku extraction prompt. Deferred until Layer A usage data shows whether subject+snippet+reasoning is sufficient. Trigger: task dismissal rate > 50%.
- **Cross-channel dedup** — Email task auto-resolving a meeting-extracted task (e.g., "they said they'd send the doc" in meeting → doc arrives via email → meeting task auto-resolved). Requires body understanding (Layer B).
- **Slack channel extraction** — Same Stage 3 will host it, but extraction logic is out of scope.
- **Push notifications** — No alerting for detected email tasks. Founder sees them in the next ritual run.
- **Bi-directional email_id FK** — Task model gets `email_id` column, but Email model does not get a `task_id` back-reference. One-directional is simpler.

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| No emails scored since last ritual | Stage 3 completes immediately, summary shows `tasks_created: 0`, brief shows "No new email tasks" |
| Email has no subject (null) | Title falls back to `"(No subject) — from {sender_name}"` |
| Email's sender_entity_id points to deleted entity | `account_id` stays NULL, task is still created with sender info from email row |
| Same email qualifies in two consecutive ritual runs | Excluded by idempotency check (`email_id` FK column on tasks table), `skipped_existing` counter increments |
| First run finds 100+ qualifying emails | Cap at 15, message shows "Found 100+ actionable emails from the last 7 days. Showing top 15 by priority." |
| Dedup match found but matched task is now `dismissed` | No duplicate flag — dismissed tasks are excluded from dedup candidate pool |
| Dedup match found with task from a different source (meeting) | Duplicate flagged — cross-source duplicates are the most important to catch |
| Email score has `priority=4` but `category='informational'` | Excluded — category filter is AND with priority filter, not OR |
| Email score has `category='action_required'` but `priority=3` | Excluded — doesn't meet priority >= 4 threshold |
| `skill_runs` table has no prior "flywheel" runs | First-run path triggers (7-day lookback, capped at 15) |
| Multiple emails in same Gmail thread qualify | Each email creates its own task — thread-level dedup is Layer B territory. Dedup guard may catch obvious overlaps via title similarity. |
| Migration runs on existing database with tasks | All new columns nullable, no backfill needed, existing tasks unaffected |
| Stage 3 throws an unhandled exception | Caught by ritual orchestrator's try/except pattern, logged, ritual continues to Stage 3 prep (existing `_stage_3_prep`) |
| Email task with `suggested_skill="email-drafter"` | `trust_level` overridden to `"confirm"` — matches meeting extraction safety invariant for email-sending skills |
| Dedup with very common subject like "Follow up" | Stop words stripped, remaining words ("follow") below 2-word minimum — dedup skipped, task created normally |

## Constraints

- **No new LLM calls** — Layer A uses existing email score metadata only. Cost impact is zero beyond database queries. This is a hard constraint for this phase.
- **Caller-commits pattern** — Task creation follows the existing pattern: function creates rows, caller commits. Enables atomic batch creation.
- **RLS compliance** — All queries must set `app.tenant_id` and `app.user_id` via `set_config()` before execution. Tasks are user-level isolated.
- **Non-fatal stage** — Stage 3 failure must not prevent the rest of the ritual from completing. Matches existing pattern in Stages 1-4.
- **Subsidy API key** — No API key needed for this stage (no LLM calls), but the stage function signature should accept `api_key` parameter for consistency with other stages and future Layer B.

## Anti-Requirements

- This is NOT a real-time email-to-task pipeline. Tasks are created during the ritual, not when emails arrive.
- This is NOT a replacement for email scoring. The scorer runs in the Gmail sync loop (every 5 min). This stage consumes scores, it doesn't produce them.
- This does NOT auto-execute email tasks. All email tasks start as `status="detected"`, `trust_level="review"`. Execution happens in Stage 4 only after user confirmation.
- This does NOT store or access email bodies. Layer A works entirely from metadata (subject, snippet, sender) and score data (category, priority, reasoning).
- This does NOT implement thread-level intelligence. Each email is treated independently. Thread collapsing is Layer B.

## Technical Design

### Channel Extractor Architecture

The stage is built around a simple extractor interface. Each channel implements one function that returns candidate tasks. The stage orchestrator handles dedup, creation, and brief integration.

```python
# Type signature for channel extractors
from typing import TypedDict

class CandidateTask(TypedDict):
    """Output of a channel extractor. Channel-agnostic shape."""
    title: str
    description: str
    source: str              # "email", "slack", "calendar", etc.
    source_id: UUID          # email.id, slack_message.id, etc.
    account_id: UUID | None
    task_type: str
    commitment_direction: str
    suggested_skill: str | None
    skill_context: dict | None
    trust_level: str
    priority: str
    email_id: UUID | None    # Only for email-sourced tasks (FK)
    metadata: dict           # Channel-specific metadata (thread_id, score_id, etc.)

# Each channel extractor has this signature:
async def extract_email_tasks(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    last_ritual_at: datetime | None,  # None = first run
) -> tuple[list[CandidateTask], dict]:
    """Returns (candidates, summary_dict)"""
    ...

# Stage orchestrator calls extractors in sequence:
CHANNEL_EXTRACTORS = [
    extract_email_tasks,
    # extract_slack_tasks,   # future
    # extract_calendar_tasks, # future
]
```

Future channels register by adding to `CHANNEL_EXTRACTORS`. The stage orchestrator, dedup guard, brief rendering, and task creation are all source-agnostic.

### Stage Integration Point

```python
# In flywheel_ritual.py — NO renumbering of existing stages.
# Insert new call between _stage_2_process() and _stage_3_prep().

async def execute_flywheel_ritual(...):
    ...
    # Stage 1: Granola Sync
    await _stage_1_sync(...)

    # Stage 2: Process Unprocessed Meetings
    await _stage_2_process(...)

    # Channel Task Extraction (NEW — inserted, not renumbered)
    try:
        await _extract_channel_tasks(
            factory, run_id, tenant_id, user_id,
            stage_results,
        )
    except Exception as e:
        logger.error("Channel task extraction failed: %s", e)
        await _append_event_atomic(factory, run_id, {
            "event": "stage",
            "data": {"stage": "extracting_channel_tasks",
                     "message": f"Channel task extraction skipped: {e}"},
        })

    # Stage 3: Prep Today's Meetings (UNCHANGED name)
    await _stage_3_prep(...)

    # Stage 4: Execute Confirmed Tasks (UNCHANGED name)
    await _stage_4_execute(...)

    # Stage 5: Compose Brief (UNCHANGED name)
    ...
```

### Email Task Extraction Query

```sql
-- Qualifying emails since last ritual
WITH last_ritual AS (
    SELECT MAX(created_at) AS last_run_at
    FROM skill_runs
    WHERE skill_name = 'flywheel'
      AND tenant_id = :tenant_id
      AND user_id = :user_id
      AND status = 'complete'
)
SELECT e.id, e.subject, e.snippet, e.sender_email, e.sender_name,
       e.gmail_thread_id, e.received_at,
       es.priority, es.category, es.suggested_action, es.reasoning,
       es.sender_entity_id
FROM emails e
JOIN email_scores es ON es.email_id = e.id
LEFT JOIN last_ritual lr ON TRUE
WHERE e.tenant_id = :tenant_id
  AND e.user_id = :user_id
  AND es.category IN ('action_required', 'meeting_followup')
  AND es.priority >= 4
  AND es.scored_at > COALESCE(lr.last_run_at, NOW() - INTERVAL '7 days')
  -- Idempotency: exclude emails already linked to tasks via FK column (indexed)
  AND NOT EXISTS (
      SELECT 1 FROM tasks t WHERE t.email_id = e.id
  )
ORDER BY es.priority DESC, e.received_at DESC
LIMIT CASE WHEN lr.last_run_at IS NULL THEN 15 ELSE 100 END;
```

### Dedup Logic (Python pseudocode)

```python
_STOP_WORDS = frozenset({
    "the", "a", "an", "to", "for", "with", "on", "in", "at",
    "by", "up", "and", "or", "of", "is", "it", "re", "fwd", "fw",
})

def normalize_title(title: str) -> set[str]:
    """Strip prefixes, remove stop words, return meaningful word set."""
    cleaned = re.sub(r'^(Re|Fwd|Fw)\s*:\s*', '', title, flags=re.IGNORECASE)
    words = set(cleaned.strip().lower().split())
    return words - _STOP_WORDS

def find_duplicate(db, tenant_id, user_id, account_id, title, cutoff_hours=48):
    """Check for potential duplicate among open tasks. Returns matched task ID or None."""
    new_words = normalize_title(title)
    if len(new_words) < 2:
        return None  # Too few meaningful words to compare

    candidates = query_open_tasks(
        tenant_id=tenant_id,
        user_id=user_id,
        account_id=account_id,  # NULL-safe: if NULL, search all user tasks
        created_after=now() - timedelta(hours=cutoff_hours),
        status_not_in=("done", "dismissed"),
    )
    for task in candidates:
        existing_words = normalize_title(task.title)
        if not existing_words:
            continue
        shorter = min(len(new_words), len(existing_words))
        overlap = len(new_words & existing_words)
        if shorter > 0 and overlap / shorter >= 0.5:
            return task.id
    return None
```

### Migration

```python
# alembic/versions/XXX_add_email_task_fields.py

def upgrade():
    # Source linking
    op.add_column('tasks', sa.Column('email_id', sa.dialects.postgresql.UUID(),
                  sa.ForeignKey('emails.id', ondelete='SET NULL'), nullable=True))

    # Resolution metadata (NULL for Layer A — schema prep for commitment ledger)
    op.add_column('tasks', sa.Column('resolved_by', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('resolution_source_id',
                  sa.dialects.postgresql.UUID(), nullable=True))
    # ^ No FK constraint — intentionally polymorphic. May reference emails.id,
    #   meetings.id, or future resolution source tables.
    op.add_column('tasks', sa.Column('resolution_note', sa.Text(), nullable=True))

    op.create_index('idx_tasks_email', 'tasks', ['email_id'])
    op.create_index('idx_tasks_source', 'tasks', ['tenant_id', 'user_id', 'source'])
```

## Open Questions

- [ ] **Account resolution via person entities** — The entity model supports `entity_type` and account linking, but the exact join path (person entity → account contact → account) needs verification against the schema during implementation.
- [ ] **Layer B trigger criteria** — What signal from Layer A usage would indicate it's time to build Layer B? Task dismissal rate > 50%? User feedback? Define the threshold before shipping Layer A.

### Resolved During Review

- [x] **SkillRun `completed_at` field** — Resolved: SkillRun has NO `completed_at` column. Use `MAX(created_at) WHERE status='complete'` instead. Accepted as slightly imprecise (measures run start, not end) but sufficient for email scoring timestamp comparison.
- [x] **Stage renumbering impact** — Resolved: Do NOT renumber. Insert new stage call between existing `_stage_2_process()` and `_stage_3_prep()`. Keep all existing function names and SSE stage names unchanged.
- [x] **Word overlap threshold** — Resolved: Changed from fixed "3+ words" to ratio-based "≥ 50% of shorter title's non-stop-words." Stop words stripped before comparison. May still need tuning with real data but the ratio approach is more robust.
- [x] **Idempotency check approach** — Resolved: Use `email_id` FK column (indexed) instead of JSONB `metadata->>'email_id'` query. No performance concern.

## Artifacts Referenced

- `CONCEPT-BRIEF-email-to-tasks.md` — 3-round brainstorm establishing Layer A/B split, volume control, dedup strategy
- `backend/src/flywheel/engines/flywheel_ritual.py` — 5-stage orchestrator (stages 1-5)
- `backend/src/flywheel/engines/email_scorer.py` — Haiku scoring engine, `SCORE_SYSTEM_PROMPT`
- `backend/src/flywheel/db/models.py` — Task (L1342), Email (L932), EmailScore (L980), SkillRun (L288)
- `backend/src/flywheel/api/tasks.py` — Task CRUD API, status transitions, valid enums
- `CONCEPT-BRIEF-flywheel-os.md` — Parent architecture (three-layer OS, trust ladder, over-detect principle)
