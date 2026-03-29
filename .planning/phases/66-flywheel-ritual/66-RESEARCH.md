# Phase 66: Flywheel Ritual (Backend Orchestrator Engine) - Research

**Researched:** 2026-03-29
**Domain:** Backend engine orchestration, multi-stage pipeline, SQLAlchemy async, Anthropic API
**Confidence:** HIGH

## Summary

Phase 66 creates a backend orchestrator engine at `engines/flywheel_ritual.py` that sequences four stages: Granola sync, meeting processing, meeting prep, and task execution. This replaces the incorrect Phase 66 implementation (a curl-based Claude Code SKILL.md). The engine follows the exact same pattern as existing engines (`_execute_meeting_processor`, `_execute_meeting_prep`, `_execute_company_intel`) — it receives `(factory, run_id, tenant_id, user_id, api_key)` and returns `(html_output, token_usage_dict, tool_calls_list)`.

The core technical challenges are: (1) extracting the ~112-line sync dedup logic from `meetings.py` into a shared function that works with `async_sessionmaker` (engine) instead of `AsyncSession` (endpoint), (2) dispatching task execution to the correct skill engine based on `suggested_skill`, and (3) aggregating token usage across multiple sub-engine calls. All sub-engines already accept a passed-in `run_id` for event emission — verified in the codebase.

**Primary recommendation:** Build as 3 plans. Plan 01: sync refactor + SKILL.md replacement. Plan 02: orchestrator engine (stages 1-3) + dispatch wiring. Plan 03: stage 4 task execution + HTML brief + document creation.

## Standard Stack

### Core (all existing — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (async) | 2.x | Database queries via `async_sessionmaker` | Existing engine pattern |
| anthropic (Python SDK) | current | LLM calls for task execution (Stage 4) | All engines use this |
| httpx | current | Granola API calls (via granola_adapter) | Already used by sync |
| Jinja2 or f-strings | N/A | HTML brief template (Stage 5) | Inline HTML generation |

### No New Dependencies
Everything needed is already in the backend. The engine calls existing functions directly — no HTTP, no new packages.

## Architecture Patterns

### Pattern 1: Engine Function Signature
**What:** All backend engines share the same signature. The orchestrator MUST match it.
**Source:** `skill_executor.py` lines 567-634
```python
async def execute_flywheel_ritual(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    api_key: str | None = None,
) -> tuple[str, dict, list]:
    """Orchestrator engine: sync, process, prep, execute tasks, compose brief."""
```
**Confidence:** HIGH — verified in `_execute_meeting_processor` (line 1361), `_execute_meeting_prep` (line 1799), `_execute_company_intel` (line 837).

### Pattern 2: Event Emission via _append_event_atomic
**What:** All engines use `_append_event_atomic(factory, run_id, event_dict)` for SSE streaming. The function does an atomic JSONB array concatenation on `skill_runs.events_log`.
**Source:** `skill_executor.py` line 3181
```python
await _append_event_atomic(factory, run_id, {
    "event": "stage",
    "data": {"stage": "syncing", "message": "Syncing from Granola... 5 new meetings"},
})
```
**Confidence:** HIGH — function verified at line 3181, uses PostgreSQL `||` operator for atomic append.

### Pattern 3: Sub-Engine Direct Function Calls (NOT child SkillRuns)
**What:** The orchestrator calls sub-engines as direct function calls, passing its own `run_id`. Sub-engines emit events to the parent's event log.
**Why:** Child SkillRun records risk job queue deadlock (single-worker), add 5s+ latency, and split the event stream.
**Source:** Verified — both `_execute_meeting_processor` and `_execute_meeting_prep` use the passed-in `run_id` for ALL `_append_event_atomic` calls (grep confirmed 30+ call sites).
```python
# Stage 2: call meeting processor directly
output, token_usage, tool_calls = await _execute_meeting_processor(
    factory=factory,
    run_id=run_id,  # Parent's run_id — events flow to orchestrator
    tenant_id=tenant_id,
    user_id=user_id,
    meeting_id=meeting.id,
    api_key=api_key,
)
```
**Confidence:** HIGH — grep of all `_append_event_atomic` calls in `_execute_meeting_processor` confirmed they all use the passed-in `run_id`.

### Pattern 4: Sync Logic Refactor (AsyncSession -> async_sessionmaker)
**What:** The sync endpoint uses `AsyncSession` (injected by FastAPI), but engines use `async_sessionmaker`. The refactored shared function must use `async_sessionmaker`.
**Current code:** `meetings.py` lines 142-253 — sync logic is inline in the endpoint, using `db: AsyncSession`.
**Refactor strategy:** Create `sync_granola_meetings(factory, tenant_id, user_id)` that opens its own sessions via `factory()`. The endpoint refactors to call this with `get_session_factory()`.

Key functions that need session adaptation:
- `_find_matching_scheduled(db, tenant_id, raw)` — currently takes `AsyncSession`, needs to work with factory
- `_apply_processing_rules(raw, rules)` — pure function, no DB, no change needed

**Implementation approach:**
```python
async def sync_granola_meetings(
    factory: async_sessionmaker,
    tenant_id: UUID,
    user_id: UUID,
) -> dict:
    """Shared sync logic used by both API endpoint and flywheel engine."""
    async with factory() as session:
        # Set RLS context
        await session.execute(sa_text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
        # ... all existing sync logic, using `session` instead of `db`
```

The endpoint refactors to:
```python
@router.post("/sync")
async def sync_meetings(user: TokenPayload = Depends(require_tenant)):
    factory = get_session_factory()
    return await sync_granola_meetings(factory, user.tenant_id, user.sub)
```
**Confidence:** HIGH — `get_session_factory()` is already imported in meetings.py (line 25), used by `process_pending_meetings`.

### Pattern 5: Dispatch Wiring in skill_executor.py
**What:** Add `flywheel` to the engine dispatch in `execute_run()`.
**Source:** `skill_executor.py` lines 567-634 — the dispatch block uses `has_engine` flag and explicit `is_*` checks.
**Implementation:**
```python
is_flywheel = run.skill_name == "flywheel"
# Add to the dispatch condition at line 581:
if has_engine or is_company_intel or is_meeting_prep or is_email_scorer or is_meeting_processor or is_flywheel:
    # ... existing cases ...
    elif is_flywheel:
        from flywheel.engines.flywheel_ritual import execute_flywheel_ritual
        output, token_usage, tool_calls = await execute_flywheel_ritual(
            factory=factory,
            run_id=run.id,
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            api_key=api_key,
        )
```
**Confidence:** HIGH — follows exact pattern of existing engine dispatch.

### Pattern 6: Subsidy Key Allowlist
**What:** The `flywheel` skill needs to be added to the subsidy key allowlist since it calls sub-engines that use LLM.
**Source:** `skill_executor.py` line 506
**Current list:** `("company-intel", "meeting-prep", "email-scorer", "meeting-processor")`
**Change:** Add `"flywheel"` to the tuple.
**Confidence:** HIGH — direct code reference.

### Pattern 7: HTML Output + Document Creation
**What:** The engine returns HTML as `output`. `execute_run()` stores it as `rendered_html` and creates a Document record.
**Source:** `skill_executor.py` lines 676-744

Key path:
1. Engine returns `(html_output, token_usage, tool_calls)`
2. `execute_run` at line 677: for meeting-prep, `rendered_html = output` (HTML directly)
3. Line 696-709: Updates SkillRun with `rendered_html=rendered_html`
4. Lines 714-744: Creates Document record with `document_type=run.skill_name`, `skill_run_id=run.id`
5. Frontend `SkillRenderer` dispatches based on `skillType`

**CRITICAL finding:** The SkillRenderer currently routes `meeting-prep` to MeetingPrepRenderer (HTML). For `flywheel`, if the engine sets BOTH `output` and `rendered_html`, the GenericRenderer will be used (line 37) — which is wrong for styled HTML. Two options:
- Option A: Add `flywheel` case in SkillRenderer to use MeetingPrepRenderer
- Option B: In `execute_run`, treat flywheel same as meeting-prep: set `rendered_html = output`

**Recommendation:** Add `flywheel` to the meeting-prep routing in `execute_run` (line 677) AND add a SkillRenderer case. Both are one-line changes.
**Confidence:** HIGH — code verified.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sync dedup | New dedup logic | Extract existing logic from meetings.py (lines 142-253) | Already battle-tested, includes hard + soft dedup |
| Meeting processing | New processing pipeline | `_execute_meeting_processor()` direct function call | 8-stage pipeline already works |
| Meeting prep | New prep logic | `_execute_meeting_prep()` and `_execute_account_meeting_prep()` | Full web research + HTML generation already works |
| Event streaming | Custom SSE | `_append_event_atomic()` | Atomic JSONB append, already integrated with SSE endpoint |
| Document creation | Custom document storage | Existing pattern in `execute_run()` lines 714-744 | Creates Document record linking to SkillRun |
| Token tracking | Custom aggregation | Simple dict addition `{"input_tokens": sum, "output_tokens": sum}` | Sub-engines return dicts |
| HTML rendering | Custom templates | `output_renderer.render_output()` for generic, or inline HTML for flywheel brief | Existing pipeline |

## Common Pitfalls

### Pitfall 1: Session/Factory Mismatch in Sync Refactor
**What goes wrong:** Using `AsyncSession` methods in a function that receives `async_sessionmaker`, or vice versa.
**Why it happens:** The endpoint injects `AsyncSession` via `Depends(get_tenant_db)`, but engines use `factory()` context manager.
**How to avoid:** The refactored `sync_granola_meetings()` MUST use `async with factory() as session:` pattern. The endpoint gets the factory via `get_session_factory()` (already imported in meetings.py).
**Warning signs:** `AttributeError: 'async_sessionmaker' object has no attribute 'execute'`

### Pitfall 2: RLS Context Not Set in Engine Sessions
**What goes wrong:** Queries return empty results or RLS violations.
**Why it happens:** Every new session opened via `factory()` needs RLS context set.
**How to avoid:** Always call `session.execute(sa_text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})` after opening a session. This is the pattern in ALL existing engines.
**Warning signs:** Empty query results when data exists, or PostgreSQL RLS policy violations.

### Pitfall 3: Task Status Transition Validation
**What goes wrong:** Spec says tasks move `confirmed -> in_review` after execution, but `VALID_TRANSITIONS` in `tasks.py` does NOT allow `confirmed -> in_review`.
**Root cause:** Valid transitions for `confirmed` are only: `{in_progress, dismissed}`.
**How to avoid:** Use `confirmed -> in_progress` when task execution starts. After successful execution, the task stays `in_progress` for founder review. OR update VALID_TRANSITIONS to add `in_review` to confirmed's targets.
**Recommendation:** Use `in_progress` (semantically correct — the task IS in progress of being executed). The spec's "in_review" label was aspirational but conflicts with the actual data model.
**Confidence:** HIGH — `tasks.py` lines 43-51 verified.

### Pitfall 4: Token Usage from _execute_meeting_processor is Zero
**What goes wrong:** Aggregated token counts are wrong because meeting-processor returns `{"input_tokens": 0, "output_tokens": 0}`.
**Why it happens:** `_execute_meeting_processor` (line 1795) returns hardcoded zeroes — the LLM calls happen inside `extract_intelligence()` and `classify_meeting()` which don't propagate token counts.
**How to avoid:** Accept this limitation. Aggregate what we can from `_execute_meeting_prep` (which returns real token counts) and `_execute_with_tools` (real counts). Document that meeting-processor tokens are not tracked.
**Warning signs:** Total token count seems low for many processed meetings.

### Pitfall 5: Prep Detection via skill_runs Query
**What goes wrong:** Incorrect prep detection causes redundant prep runs.
**Why it happens:** Meeting has no `prepped` status. Must query `skill_runs WHERE skill_name='meeting-prep' AND status='completed'` and match by input_text content.
**How to avoid:** Query with `LIKE '%{meeting.title}%'` pattern. Be careful with SQL injection — use parameterized queries.
**Warning signs:** Same meeting gets prepped every flywheel run.

### Pitfall 6: Flywheel Engine Not in Subsidy Allowlist
**What goes wrong:** "No API key configured" error even when subsidy key exists.
**Why it happens:** `execute_run()` line 506 only allows specific skill names for subsidy fallback.
**How to avoid:** Add `"flywheel"` to the tuple at line 506.

### Pitfall 7: SkillRenderer Falls Through to GenericRenderer for HTML
**What goes wrong:** Flywheel's styled HTML daily brief renders as raw text/markdown.
**Why it happens:** SkillRenderer at line 37 routes to GenericRenderer when `output` exists, regardless of `rendered_html`.
**How to avoid:** Add `flywheel` to the meeting-prep-style routing in SkillRenderer AND in `execute_run` line 677.

## Code Examples

### Exact Sync Logic to Extract (meetings.py lines 142-253)
```python
# Source: backend/src/flywheel/api/meetings.py lines 142-253
# This is the CURRENT inline code that must be extracted to a shared function.
# Key dependencies:
#   - Integration model (query by tenant_id, user_id, provider='granola')
#   - decrypt_api_key(integration.credentials_encrypted)
#   - granola_list_meetings(api_key, since=integration.last_synced_at)
#   - _find_matching_scheduled(session, tenant_id, raw)  # fuzzy dedup
#   - _apply_processing_rules(raw, rules)  # pure function
#   - Meeting model (insert new rows)
#   - Integration.last_synced_at update
```

### Sub-Engine Call Pattern (from skill_executor.py)
```python
# Source: skill_executor.py lines 618-628
# This is the EXACT pattern for calling meeting-processor from the orchestrator:
output, token_usage, tool_calls = await _execute_meeting_processor(
    factory=factory,
    run_id=run.id,       # Orchestrator's run_id
    tenant_id=run.tenant_id,
    user_id=run.user_id,
    meeting_id=UUID(run.input_text),  # Meeting UUID
    api_key=api_key,
)
```

### Meeting Prep Call Pattern (two variants)
```python
# Source: skill_executor.py lines 591-607
# Variant 1: Account-scoped prep (has account_id)
output, token_usage, tool_calls = await _execute_account_meeting_prep(
    api_key=api_key,
    input_text=f"Account-ID:{account_id}",  # Key: starts with "Account-ID:"
    factory=factory,
    run_id=run_id,
    tenant_id=tenant_id,
    user_id=user_id,
)

# Variant 2: Standard prep (no account, uses web research)
# input_text format: "Meeting: {title}\nDate: {date}\nAttendees: {names}\nType: {type}"
output, token_usage, tool_calls = await _execute_meeting_prep(
    api_key=api_key,
    input_text=formatted_input,
    factory=factory,
    run_id=run_id,
    tenant_id=tenant_id,
    user_id=user_id,
)
```

### _execute_with_tools for Generic Skill Invocation (Stage 4 task execution)
```python
# Source: skill_executor.py lines 2931-3050
# For tasks with suggested_skill that don't have a dedicated engine
# (e.g., sales-collateral, investor-update), use _execute_with_tools:
from flywheel.tools import create_registry
from flywheel.tools.registry import RunContext
from flywheel.tools.budget import RunBudget

registry = create_registry()
run_context = RunContext(
    tenant_id=tenant_id,
    user_id=user_id,
    run_id=run_id,
    budget=RunBudget(),
    session_factory=factory,
    focus_id=None,
)

# Load system_prompt from DB
skill_meta = await _load_skill_from_db(factory, suggested_skill)
system_prompt = skill_meta["system_prompt"] if skill_meta else None

output, token_usage, tool_calls = await _execute_with_tools(
    api_key=api_key,
    skill_name=suggested_skill,
    input_text=formulated_input,
    registry=registry,
    context=run_context,
    factory=factory,
    run_id=run_id,
    agent_connected=False,
    system_prompt_override=system_prompt,
)
```

### Token Usage Aggregation Pattern
```python
# Source: skill_executor.py convention
# Each sub-engine returns: (output, {"input_tokens": int, "output_tokens": int, ...}, tool_calls)
total_input = 0
total_output = 0
for output, usage, calls in sub_engine_results:
    total_input += (usage or {}).get("input_tokens", 0)
    total_output += (usage or {}).get("output_tokens", 0)

token_usage = {"input_tokens": total_input, "output_tokens": total_output}
```

### Document Creation Pattern (already in execute_run)
```python
# Source: skill_executor.py lines 714-744
# Document creation happens automatically in execute_run() after engine returns.
# The engine just needs to return HTML as its output string.
# execute_run() will:
# 1. Store rendered_html on SkillRun
# 2. Create Document record with document_type=run.skill_name
# 3. The Document title for "flywheel" will use the fallback:
#    "Flywheel - 2026-03-29" (from _generate_title line 105)
```

## Key Research Findings

### Finding 1: Task Execution Skill Mapping
**Question:** What skills exist that could be invoked for task execution?
**Answer:** Tasks have `suggested_skill` which maps to:

| suggested_skill | Engine Type | Invocation |
|----------------|-------------|------------|
| `meeting-prep` | Dedicated engine | `_execute_meeting_prep(api_key, input_text, factory, run_id, ...)` |
| `email-drafter` | Engine module | Has `engine: email_drafter` in SKILL.md, but also works via `_execute_with_tools` |
| `sales-collateral` | Generic (LLM + tools) | `_execute_with_tools(api_key, "sales-collateral", input_text, registry, context, ...)` |
| `investor-update` | Generic (LLM + tools) | `_execute_with_tools(api_key, "investor-update", input_text, registry, context, ...)` |
| `account-research` | Generic (LLM + tools) | `_execute_with_tools(...)` |
| `null` | None | Skip execution — task has no automatable skill |

**Recommendation:** Use `_execute_with_tools` as the default dispatch for Stage 4. Only use dedicated engines for skills that have them (`meeting-prep`). The `_execute_with_tools` path loads the system_prompt from DB and gives the LLM access to web_search and all registered tools.

**Confidence:** HIGH — verified by checking all SKILL.md frontmatter for `engine:` key (only email-drafter and email-scorer have it).

### Finding 2: input_text Formulation for Task Execution
**Question:** How to construct proper input_text for each skill type from task context?
**Answer:** Use an LLM call to formulate the input. The task has:
- `title`, `description` — what to do
- `skill_context` (JSONB) — additional context from extraction
- `account_id` — links to Account for context store reads
- `meeting_id` — links to Meeting for transcript/intel

The orchestrator should:
1. Load relevant context (account intel, contacts, positioning) using `preload_tenant_context`
2. Load meeting summary if `meeting_id` is set
3. Formulate `input_text` as a structured prompt combining task details + context
4. Pass to `_execute_with_tools` which appends tenant context to the system prompt

**Confidence:** MEDIUM — the exact prompt formulation will need iteration, but the mechanism is clear.

### Finding 3: Sync Refactor is Straightforward
**Question:** How to extract sync logic to work with both AsyncSession and async_sessionmaker?
**Answer:** Standardize on `async_sessionmaker`. The endpoint calls `get_session_factory()` (already imported at line 25 of meetings.py). The helper function `_find_matching_scheduled` currently takes `AsyncSession` — move it inside the shared function's session context. `_apply_processing_rules` is a pure function, no change needed.

Total lines to extract: ~112 (lines 161-253 of meetings.py endpoint body).
Helper functions to move: `_find_matching_scheduled` (lines 78-134), `_apply_processing_rules` (lines 37-75).

**Confidence:** HIGH — code verified, `get_session_factory` already available.

### Finding 4: HTML Rendering Path for Flywheel Brief
**Question:** How does rendered_html get saved and served?
**Answer:**
1. Engine returns HTML string as first element of tuple
2. `execute_run()` at line 677 checks if skill is meeting-prep; needs to also check for flywheel
3. Sets `rendered_html = output` on SkillRun record (line 702)
4. Creates Document record linking to SkillRun (lines 714-744)
5. Frontend: `fetchDocument(id)` returns `{ output, rendered_html }`
6. `SkillRenderer` dispatches based on `skillType`

**Action needed:**
- Add `is_flywheel` check at line 677: `if is_meeting_prep or is_account_meeting_prep or is_flywheel:`
- Add SkillRenderer case: `if (skillType === 'flywheel') { return <MeetingPrepRenderer ... /> }`

**Confidence:** HIGH — full code path verified.

### Finding 5: Existing SKILL.md Must Be Replaced
**Current flywheel SKILL.md:** curl-based Claude Code skill with `allowed-tools: [Bash, Read]`, `FLYWHEEL_API_TOKEN` env var, subcommand routing via CLI output. **This is completely wrong.**

**New SKILL.md should have:**
```yaml
---
name: flywheel
version: "2.0"
description: >
  Daily operating ritual. One command syncs meetings, processes recordings,
  preps today's external meetings, executes confirmed tasks, and produces
  an HTML daily brief. Invoked via MCP flywheel_run_skill("flywheel").
engine: flywheel_ritual
web_tier: 1
contract_reads:
  - contacts
  - company-intel
  - competitive-intel
  - positioning
contract_writes:
  - contacts
  - company-intel
---
```
**No `allowed-tools`.** No Bash. No curl. The system prompt body provides Stage 4 LLM instructions.

**Confidence:** HIGH — spec ORCH-02 is explicit.

## Open Questions

1. **Stage 4 LLM prompt for input_text formulation**
   - What we know: Tasks have title, description, skill_context, account_id, meeting_id
   - What's unclear: Exact prompt structure for the LLM that formulates input_text from task context
   - Recommendation: Use a simple prompt template. Start minimal, iterate. The LLM receives task context + account context and produces a skill-specific input_text.

2. **Email-drafter engine invocation from orchestrator**
   - What we know: email-drafter has `engine: email_drafter` in frontmatter. It's a background skill called by gmail_sync.
   - What's unclear: Whether `_execute_with_tools` with the email-drafter's system_prompt would work, or if the dedicated engine path is needed.
   - Recommendation: Use `_execute_with_tools` for all Stage 4 skills. The system_prompt from DB gives the LLM the right instructions. The dedicated engine module is for the sync worker path.

3. **Brief HTML template complexity**
   - What we know: Brief has 5 sections (sync, processed, prep, tasks, remaining)
   - What's unclear: Whether to use Jinja2 templates or inline f-string HTML
   - Recommendation: Use inline f-string HTML. The brief is generated once per run, and the template logic is straightforward. Jinja2 adds a dependency for no real benefit at this scale.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/skill_executor.py` — engine dispatch (lines 567-634), `_execute_meeting_processor` (line 1361), `_execute_meeting_prep` (line 1799), `_execute_account_meeting_prep` (line 2585), `_execute_with_tools` (line 2931), `_append_event_atomic` (line 3181), subsidy allowlist (line 506)
- `backend/src/flywheel/api/meetings.py` — sync endpoint (lines 142-253), `_find_matching_scheduled` (line 78), `_apply_processing_rules` (line 37)
- `backend/src/flywheel/api/tasks.py` — `VALID_TRANSITIONS` (lines 43-51): `confirmed -> {in_progress, dismissed}` (NOT in_review)
- `backend/src/flywheel/engines/meeting_processor_web.py` — helper functions, factory pattern usage
- `backend/src/flywheel/services/granola_adapter.py` — `RawMeeting` dataclass, `list_meetings()` signature
- `backend/src/flywheel/services/document_storage.py` — `_generate_title`, `_extract_document_metadata`
- `backend/src/flywheel/db/seed.py` — line 269: `engine_module = data.get("engine")`
- `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` — routing logic
- `.planning/SPEC-flywheel-ritual-rearchitect.md` — full spec with ORCH-01 through ORCH-12
- `skills/*/SKILL.md` — only email-drafter and email-scorer have `engine:` key

### Secondary (MEDIUM confidence)
- `backend/src/flywheel/db/models.py` — Task model (line 1342), field types and constraints
- `backend/src/flywheel/auth/encryption.py` — `decrypt_api_key()` function

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all patterns verified in codebase
- Architecture: HIGH — engine dispatch, sub-engine calls, event emission all verified in source
- Sync refactor: HIGH — exact lines identified, `get_session_factory()` already imported
- Task execution dispatch: MEDIUM — mechanism clear, but exact prompt formulation needs iteration
- HTML brief: HIGH — rendering path verified end-to-end (engine -> SkillRun -> Document -> SkillRenderer)
- Pitfalls: HIGH — all identified from code analysis, especially task status transition conflict

**Research date:** 2026-03-29
**Valid until:** 2026-04-29 (backend architecture stable, no expected changes)
