# Phase 65: Task Intelligence - Research

**Researched:** 2026-03-28
**Domain:** Meeting-to-task extraction pipeline, tasks data model, CRUD API, signal integration
**Confidence:** HIGH

## Summary

Phase 65 adds a tasks layer that turns meeting commitments into actionable rows. The work spans four requirements: a `tasks` Alembic table with user-level RLS (TASK-01), a new Stage 7 in the meeting processor pipeline that uses Haiku to classify commitments (TASK-02), a 7-endpoint CRUD API at `/api/v1/tasks` (TASK-03), and three new task signal counts added to `GET /signals/` (TASK-04).

The codebase has well-established patterns for every piece: the meeting processor pipeline in `skill_executor.py` (lines 1361-1754) already runs 7 stages with `_append_event_atomic` for SSE events; migrations 032 and 031 demonstrate the exact split-visibility and user-level RLS patterns needed; the signals API uses raw SQL with `FILTER` clauses and a 60-second TTL cache; and CRUD APIs like `accounts.py` show the Pydantic/FastAPI pattern with `get_tenant_db` + `require_tenant` dependencies. The new code should follow these existing patterns exactly.

**Primary recommendation:** Build in 4 plans mapping 1:1 to the 4 requirements. Plan 01 (TASK-01) creates the migration and ORM model. Plan 02 (TASK-02) adds Stage 7 task extraction into the meeting processor. Plan 03 (TASK-03) builds the Tasks CRUD API. Plan 04 (TASK-04) extends the signals endpoint with task counts.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0 (async) | ORM model for Task table | All models in `db/models.py` use SA 2.0 mapped_column |
| Alembic | current | Migration for tasks table | All schema changes use numbered Alembic migrations |
| FastAPI | current | Tasks CRUD API | All endpoints use FastAPI APIRouter |
| Pydantic | v2 | Request/response schemas | All API schemas use Pydantic BaseModel |
| Anthropic SDK | sync wrapped in run_in_executor | Haiku LLM call for task extraction | Per Phase 61 decision: sync SDK in executor |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | current | Already in deps, not directly needed | N/A |

No new dependencies needed. Everything is already in the project.

## Architecture Patterns

### Recommended Project Structure
```
backend/
  alembic/versions/
    034_create_tasks_table.py       # TASK-01: migration
  src/flywheel/
    db/models.py                    # TASK-01: Task ORM model (append to existing)
    engines/meeting_processor_web.py # TASK-02: extract_tasks() helper
    services/skill_executor.py       # TASK-02: Stage 7 insertion in pipeline
    api/tasks.py                    # TASK-03: new 7-endpoint CRUD router
    api/signals.py                  # TASK-04: add task counts
    main.py                         # Register tasks_router
```

### Pattern 1: Alembic Migration with User-Level RLS
**What:** Create table, indexes, enable RLS, create split-visibility or user-level policies
**When to use:** TASK-01
**Example from migration 032:**
```python
# Enable RLS
op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY")
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tasks TO app_user")

# User-level RLS (tasks are personal, not team-visible)
op.execute("""
    CREATE POLICY tasks_user_isolation ON tasks
        FOR ALL
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND user_id = current_setting('app.user_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
            AND user_id = current_setting('app.user_id', true)::uuid
        )
""")
```

### Pattern 2: Meeting Processor Pipeline Stage
**What:** Add a new stage between existing stages 6 (writing) and 7 (done)
**When to use:** TASK-02
**Key detail:** The current Stage 7 is "done" (lines 1684-1727 of skill_executor.py). The new task extraction stage needs to be inserted as a new Stage 7, and the current "done" becomes Stage 8. The stage emits SSE events via `_append_event_atomic`.
```python
# Stage 7: task extraction
await _append_event_atomic(factory, run_id, {
    "event": "stage",
    "data": {"stage": "extracting_tasks", "message": "Extracting commitments and tasks..."},
})

# Call Haiku for commitment classification
tasks = await extract_tasks(
    transcript=content.transcript,
    extracted=extracted,  # from Stage 4
    meeting_type=meeting_type,
    api_key=api_key,
)

# Write Task rows
tasks_created = await write_task_rows(
    factory=factory,
    tenant_id=tenant_id,
    user_id=user_id or meeting.user_id,
    meeting_id=meeting_id,
    account_id=account_id,
    tasks=tasks,
)

# Stage 8: done (previously Stage 7)
```

### Pattern 3: Sync Anthropic SDK in run_in_executor
**What:** Wrap sync SDK call in asyncio.get_event_loop().run_in_executor()
**When to use:** TASK-02 Haiku call
**Source:** meeting_processor_web.py lines 248-259
```python
def _call_haiku() -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()

loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, _call_haiku)
```

### Pattern 4: CRUD API with Tenant DB and Status Validation
**What:** FastAPI router with `get_tenant_db` + `require_tenant` dependencies
**When to use:** TASK-03
**Source:** accounts.py pattern
```python
router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/")
async def list_tasks(
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
    status: str | None = Query(None),
) -> TasksListResponse:
    ...
```

### Pattern 5: Signals SQL Extension with FILTER Clauses
**What:** Add task counts to signals response using additional SQL query
**When to use:** TASK-04
**Source:** signals.py pattern with `_ACCOUNT_SIGNALS_SQL`
```python
# New query for task signal counts
_TASK_SIGNALS_SQL = text("""
    SELECT
        COUNT(*) FILTER (WHERE status = 'detected') AS tasks_detected,
        COUNT(*) FILTER (WHERE status = 'in_review') AS tasks_in_review,
        COUNT(*) FILTER (
            WHERE due_date IS NOT NULL AND due_date < :now AND status NOT IN ('done', 'dismissed')
        ) AS tasks_overdue
    FROM tasks
    WHERE tenant_id = :tid
      AND user_id = :uid
""")
```

### Anti-Patterns to Avoid
- **Do NOT use split-visibility RLS for tasks:** Tasks are personal (user-scoped), not team-visible like meetings. Use full user_isolation policy (Pattern 1 from migration 031), NOT the split tenant_read/owner_write pattern from migration 032.
- **Do NOT add task extraction as a separate pipeline:** It must be a stage inside `_execute_meeting_processor`, not a separate post-processing step. The meeting processor already handles all 7 stages sequentially.
- **Do NOT auto-send emails:** Per success criteria #5, all email-related tasks MUST have `trust_level='confirm'`. The system must NEVER auto-execute email tasks.
- **Do NOT cache task signals per tenant only:** Task counts are user-scoped (unlike relationship signals which are tenant-scoped). Cache key must include user_id.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Status transition validation | Custom state machine class | Simple dict mapping of valid transitions | Only 7 statuses, transitions are a small lookup table |
| RLS enforcement | Manual WHERE clauses | PostgreSQL RLS policies + `set_config` | Existing pattern, cannot be bypassed |
| LLM commitment parsing | Regex-based extraction | Haiku with structured JSON prompt | Commitments require natural language understanding |
| Due date extraction | Date parsing library | Let Haiku extract due_date as ISO string from context | "next week", "by Friday" require LLM |

## Common Pitfalls

### Pitfall 1: Pipeline Stage Numbering
**What goes wrong:** The current "Stage 7: done" is the final stage. Inserting a new stage before it requires renumbering.
**Why it happens:** Developer might append Stage 8 instead of inserting Stage 7 and shifting done to Stage 8.
**How to avoid:** The SSE stage names are strings ("extracting_tasks", "done"), not numbers. The "done" stage must remain last. Insert the new task extraction stage before the existing "done" block.
**Warning signs:** If "done" event fires before task extraction completes.

### Pitfall 2: RLS Context for Task Writes Inside Pipeline
**What goes wrong:** Task rows fail to INSERT because `app.user_id` isn't set on the session.
**Why it happens:** Some pipeline stages open new sessions without setting both `app.tenant_id` and `app.user_id`.
**How to avoid:** Every `factory()` session that touches the tasks table must call both `set_config('app.tenant_id', ...)` and `set_config('app.user_id', ...)`.
**Warning signs:** RLS violation errors during meeting processing.

### Pitfall 3: Haiku JSON Parsing Failures
**What goes wrong:** Haiku returns malformed JSON or markdown-wrapped JSON.
**Why it happens:** LLMs occasionally wrap output in code fences or add prose.
**How to avoid:** Use the same JSON cleanup pattern from `extract_intelligence()` (lines 318-325 of meeting_processor_web.py): strip markdown code fences, then json.loads().
**Warning signs:** json.JSONDecodeError in logs.

### Pitfall 4: Signal Cache Key Mismatch
**What goes wrong:** User A sees User B's task counts because cache is keyed by tenant_id only.
**Why it happens:** Existing signals cache uses `tenant_id` as key because relationship signals are tenant-scoped. Task signals are user-scoped.
**How to avoid:** Change cache key to `f"{tenant_id}:{user_id}"` or add a separate task signals cache keyed by both.
**Warning signs:** Task counts showing other users' tasks.

### Pitfall 5: Status Transition Enforcement
**What goes wrong:** Client sends invalid transition (e.g., `detected` -> `done` skipping review).
**Why it happens:** Without server-side validation, any PATCH can set any status.
**How to avoid:** Define valid transitions as a dict and validate in the PATCH endpoint.
**Warning signs:** Tasks moving to unexpected states.

### Pitfall 6: Return 404 Not 403 on Ownership Mismatch
**What goes wrong:** Returning 403 leaks information about task existence.
**Why it happens:** Developer checks ownership and returns 403 Forbidden.
**How to avoid:** Per Phase 59 decision: return 404 (not 403) on ownership mismatches. With RLS, this happens naturally since the user simply won't see the row.
**Warning signs:** N/A if using RLS correctly -- the row won't be found at all.

## Code Examples

### Task ORM Model
```python
# Source: follows pattern from db/models.py Account, Meeting classes
class Task(Base):
    """A task detected from meeting intelligence or created manually."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "tenant_id", "user_id", "status"),
        Index(
            "idx_tasks_due",
            "tenant_id", "user_id", "due_date",
            postgresql_where=text("due_date IS NOT NULL AND status NOT IN ('done', 'dismissed')"),
        ),
        Index("idx_tasks_meeting", "meeting_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), nullable=False)
    meeting_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # "meeting-processor", "manual"
    task_type: Mapped[str] = mapped_column(Text, nullable=False)  # "followup", "deliverable", "introduction", "research", "other"
    commitment_direction: Mapped[str] = mapped_column(Text, nullable=False)  # "yours", "theirs", "mutual", "signal", "speculation"
    suggested_skill: Mapped[str | None] = mapped_column(Text)  # "sales-collateral", "email-drafter", etc.
    skill_context: Mapped[dict | None] = mapped_column(JSONB)  # context to pass to skill
    trust_level: Mapped[str] = mapped_column(Text, nullable=False)  # "auto", "review", "confirm"
    status: Mapped[str] = mapped_column(Text, server_default=text("'detected'"), nullable=False)
    # 7 statuses: detected, in_review, confirmed, in_progress, done, dismissed, blocked
    priority: Mapped[str] = mapped_column(Text, server_default=text("'medium'"), nullable=False)
    # "high", "medium", "low"
    due_date: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    meeting: Mapped["Meeting | None"] = relationship()
    account: Mapped["Account | None"] = relationship()
```

### Haiku Task Extraction Prompt
```python
TASK_EXTRACTION_PROMPT = """\
You are a task extraction engine. Given a meeting transcript and extracted intelligence,
identify all commitments, action items, and follow-ups.

For each task, classify:
1. commitment_direction: "yours" (the user/founder committed), "theirs" (other party committed),
   "mutual" (both sides), "signal" (implicit need, nobody committed), "speculation" (might need later)
2. task_type: "followup" (reach back out), "deliverable" (create something), "introduction" (connect people),
   "research" (investigate), "other"
3. suggested_skill: if the task maps to a known skill, suggest it. Known skills:
   - "email-drafter" for follow-up emails
   - "sales-collateral" for one-pagers, decks, proposals
   - "investor-update" for investor updates
   - null if no skill applies
4. trust_level: "auto" (safe to execute without review), "review" (needs user review before execution),
   "confirm" (MUST be explicitly confirmed -- use for ALL email-related tasks)
5. priority: "high" (time-sensitive or explicitly urgent), "medium" (standard), "low" (nice-to-have)
6. due_date: ISO 8601 datetime if mentioned or inferrable, null otherwise

CRITICAL: Any task with suggested_skill containing "email" MUST have trust_level="confirm".

Respond with a JSON array of task objects. Each object:
{
  "title": "short action title",
  "description": "detailed description with context",
  "commitment_direction": "yours|theirs|mutual|signal|speculation",
  "task_type": "followup|deliverable|introduction|research|other",
  "suggested_skill": "skill-name" or null,
  "skill_context": {} or null,
  "trust_level": "auto|review|confirm",
  "priority": "high|medium|low",
  "due_date": "ISO datetime" or null
}

Return an empty array [] if no tasks are found.
"""
```

### Status Transition Map
```python
# Valid status transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "detected":    {"in_review", "confirmed", "dismissed"},
    "in_review":   {"confirmed", "dismissed"},
    "confirmed":   {"in_progress", "dismissed"},
    "in_progress": {"done", "blocked", "dismissed"},
    "blocked":     {"in_progress", "dismissed"},
    "done":        set(),       # terminal
    "dismissed":   {"detected"}, # can re-open
}
```

### Task Signal Counts Query
```python
_TASK_SIGNALS_SQL = text("""
    SELECT
        COUNT(*) FILTER (WHERE status = 'detected') AS tasks_detected,
        COUNT(*) FILTER (WHERE status = 'in_review') AS tasks_in_review,
        COUNT(*) FILTER (
            WHERE due_date IS NOT NULL
              AND due_date < :now
              AND status NOT IN ('done', 'dismissed')
        ) AS tasks_overdue
    FROM tasks
    WHERE tenant_id = :tid
      AND user_id = :uid
""")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Action items as context entries only | Action items + structured Task rows | Phase 65 | Tasks become first-class entities with lifecycle |
| 7-stage meeting pipeline | 8-stage pipeline (task extraction added) | Phase 65 | More intelligence extracted per meeting |
| Signals = relationship-only | Signals include task counts | Phase 65 | Sidebar shows pending work items |

**Key architectural decision:** Tasks are extracted from the same meeting transcript that's already loaded in Stage 4. The Haiku call in Stage 7 receives both the transcript AND the extracted intelligence (from Sonnet in Stage 4), so it has full context without additional LLM cost for content retrieval.

## Open Questions

1. **Column count: 20 columns specified in TASK-01**
   - What we know: The ORM model above has 19 mapped columns (id, tenant_id, user_id, meeting_id, account_id, title, description, source, task_type, commitment_direction, suggested_skill, skill_context, trust_level, status, priority, due_date, completed_at, metadata, created_at, updated_at).
   - What's unclear: Whether the 20th column is a specific requirement or approximate.
   - Recommendation: The 20 columns listed above (counting `metadata` as the JSONB column name) match the spec. If exactly 20 is needed, `updated_at` brings it to 20. Proceed with the model as designed.

2. **Meeting pipeline renumbering**
   - What we know: Current stages are 1-7 (fetching through done). New task extraction inserts before done.
   - What's unclear: Whether frontend SSE listeners depend on specific stage names.
   - Recommendation: Use a new stage name "extracting_tasks" which is additive. The "done" stage name stays the same. No renumbering needed since stages use string names, not numbers.

3. **Skill context shape**
   - What we know: `skill_context` JSONB stores parameters to pass to the suggested skill.
   - What's unclear: Exact schema per skill type.
   - Recommendation: Keep as unstructured JSONB for now. Each skill will define its own expected context shape. The task extraction prompt should produce reasonable context (e.g., recipient email, subject line for email-drafter; topic and audience for sales-collateral).

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/skill_executor.py` lines 1361-1754 -- meeting processor pipeline (7 stages)
- `backend/src/flywheel/engines/meeting_processor_web.py` -- all async helpers (classify, extract, write)
- `backend/src/flywheel/db/models.py` -- all ORM models (Account, Meeting, ContextEntry patterns)
- `backend/alembic/versions/032_create_meetings_table.py` -- split-visibility RLS pattern
- `backend/alembic/versions/031_user_level_rls.py` -- user-level RLS pattern
- `backend/src/flywheel/api/signals.py` -- signals SQL + cache pattern
- `backend/src/flywheel/api/accounts.py` -- CRUD API pattern
- `backend/src/flywheel/api/deps.py` -- get_tenant_db, require_tenant dependencies
- `backend/src/flywheel/main.py` -- router registration pattern
- `.planning/REQUIREMENTS.md` -- TASK-01 through TASK-04 specifications

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` -- Phase 65 success criteria and dependencies

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, no new dependencies
- Architecture: HIGH -- every pattern has an existing codebase example to follow
- Pitfalls: HIGH -- identified from direct code analysis of existing pipeline and RLS patterns
- Task extraction prompt: MEDIUM -- the Haiku prompt is new and will need iteration

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable patterns, no external dependency changes expected)
