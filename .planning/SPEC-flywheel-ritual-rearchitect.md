# Flywheel Ritual — Backend Orchestrator Engine Specification

> Status: Reviewed
> Created: 2026-03-28
> Last updated: 2026-03-28
> Source: CONCEPT-BRIEF-flywheel-ritual-rearchitect.md (3-round brainstorm, 14 advisors)
> Review: 14 findings addressed (5 functional, 6 friction, 3 hygiene)

## Overview

The `/flywheel` ritual is the founder's daily operating system. One invocation syncs meetings from Granola, processes unprocessed recordings into intelligence, prepares briefings for upcoming meetings, and (in Phase 67) executes pending tasks by invoking appropriate skills. It returns a rich HTML daily brief with all deliverables for founder review.

It runs as a **backend engine** — same architecture as meeting-prep and meeting-processor. Invoked via MCP `flywheel_run_skill("flywheel")`. No separate installation, no env vars, no curl. Users just run `flywheel login` and all skills are available.

## Core Value

The founder types one command and their day is prepared. Meetings synced, recordings processed, prep briefings generated, task deliverables produced — all powered by the compounding context store. Every run enriches the context, making the next run better. This is the flywheel.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (primary) | MCP: `flywheel_run_skill("flywheel")` | Start the day with everything prepared |
| Founder (CLI) | Claude Code: Claude invokes MCP tool when user says "run my flywheel" or similar | Same — Claude recognizes intent and calls MCP |
| Founder (web) | Future: `/brief` page with "Run Flywheel" button | Same — browser triggers skill run |

## Requirements

### Must Have

- **ORCH-01**: Dedicated backend engine at `backend/src/flywheel/engines/flywheel_ritual.py` with function signature `async def execute_flywheel_ritual(factory, run_id, tenant_id, user_id, api_key) -> tuple[str, dict, list]`, registered in `skill_executor.py` dispatch logic.
  - **Acceptance Criteria:**
    - [ ] Engine function exists with correct signature matching existing engine pattern (factory: async_sessionmaker, run_id: UUID, tenant_id: UUID, user_id: UUID | None, api_key: str | None)
    - [ ] `skill_executor.py` dispatch routes `skill_name == "flywheel"` to this engine
    - [ ] Engine returns (html_output, token_usage_dict, tool_calls_list) tuple
    - [ ] Engine receives api_key from dispatcher (does NOT fetch it)
    - [ ] Verified: seed.py reads frontmatter key `engine` and maps to `SkillDefinition.engine_module` column (same pattern as email-scorer, email-drafter skills)

- **ORCH-02**: SKILL.md at `skills/flywheel/SKILL.md` with correct backend-skill frontmatter. System prompt body provides instructions for Stage 4 LLM-powered task execution (Phase 67).
  - **Acceptance Criteria:**
    - [ ] Frontmatter has `engine: flywheel_ritual` (seed.py reads `engine` key → maps to `engine_module` DB column — verified in seed.py line 269)
    - [ ] Frontmatter has `web_tier: 1`
    - [ ] Frontmatter has `contract_reads: [contacts, company-intel, competitive-landscape, positioning]`
    - [ ] Frontmatter has `contract_writes: [contacts, company-intel]`
    - [ ] Frontmatter does NOT contain `allowed-tools`
    - [ ] `flywheel db seed` successfully upserts the skill into `skill_definitions` table with `engine_module='flywheel_ritual'`
    - [ ] `GET /api/v1/skills` returns "flywheel" in the skill list
    - [ ] `flywheel_run_skill("flywheel")` via MCP creates a pending SkillRun and the job queue dispatches to the engine

- **ORCH-03**: Stage 1 — Granola Sync. Extract sync logic from the inline `POST /meetings/sync` endpoint into a shared `sync_granola_meetings()` function. Engine and API endpoint both call this shared function.
  - **Acceptance Criteria:**
    - [ ] New shared function `sync_granola_meetings(factory: async_sessionmaker, tenant_id: UUID, user_id: UUID)` extracted from the ~112 lines currently inline in `POST /meetings/sync` endpoint (meetings.py lines 142-253)
    - [ ] Shared function includes: hard dedup (external_id match), soft dedup via `_find_matching_scheduled()` (±30min time window + title match + attendee overlap), processing rules, status assignment
    - [ ] Shared function uses `async_sessionmaker` (factory pattern), NOT raw `AsyncSession` — engine and endpoint both call the same function
    - [ ] `POST /meetings/sync` API endpoint refactored to call `sync_granola_meetings()` instead of inline logic
    - [ ] Engine Stage 1 calls `sync_granola_meetings(factory, tenant_id, user_id)`
    - [ ] Engine loads Integration WHERE provider='granola' AND status='connected', decrypts API key via `decrypt_value()`
    - [ ] Calls `granola_adapter.list_meetings(api_key, since=integration.last_synced_at)`
    - [ ] Updates `Integration.last_synced_at` after sync
    - [ ] Emits SSE event: `{"event": "stage", "data": {"stage": "syncing", "message": "Syncing from Granola... {N} new meetings"}}`
    - [ ] If no Granola integration or disconnected: emits info event, continues to Stage 2
    - [ ] If Granola API call fails: emits warning with error details, continues to Stage 2
    - [ ] Returns sync stats: `{synced: int, skipped: int, already_seen: int}`

- **ORCH-04**: Stage 2 — Process Unprocessed Recordings. Engine queries ALL meetings with unprocessed status, calls `_execute_meeting_processor()` for each.
  - **Acceptance Criteria:**
    - [ ] Queries ALL meetings with `processing_status IN ('pending', 'recorded')` for the tenant, ordered by `meeting_date DESC` (newest first)
    - [ ] No caps — processes all unprocessed meetings in one run
    - [ ] For each meeting: calls `_execute_meeting_processor(factory, run_id, tenant_id, user_id, meeting.id, api_key)` directly (function call, NOT HTTP, NOT child SkillRun)
    - [ ] Verified: `_execute_meeting_processor` uses the passed-in `run_id` for ALL `_append_event_atomic()` calls — sub-engine events flow to the orchestrator's events_log
    - [ ] Emits SSE event per meeting: `{"event": "stage", "data": {"stage": "processing", "message": "Processing: {title}..."}}`
    - [ ] If one meeting fails: logs error, emits warning with meeting title and error, continues to next
    - [ ] After all: emits summary "Processed {N}/{total} meetings. {failures} failed."
    - [ ] Token usage aggregated: sum `input_tokens` and `output_tokens` across all sub-engine calls

- **ORCH-05**: Stage 3 — Prep Today's Meetings. Engine queries today's external meetings, checks for existing prep via `skill_runs` table, calls meeting-prep engine for ALL unprepped ones.
  - **Acceptance Criteria:**
    - [ ] Queries today's meetings: meetings where `DATE(meeting_date) = DATE(now())` for the tenant
    - [ ] Filters: `meeting_type != 'internal'` (NULL meeting_type treated as external)
    - [ ] Prep detection: queries `skill_runs WHERE skill_name IN ('meeting-prep') AND status='completed' AND input_text LIKE '%{meeting.title}%'` to find existing prep. If found, skip. (Note: Meeting table has NO `prepped` status or `prepped_at` column — valid statuses are: pending, scheduled, recorded, complete, failed, skipped)
    - [ ] No caps — preps ALL unprepped external meetings for today
    - [ ] For meetings with `account_id`: calls `_execute_account_meeting_prep(api_key, f"Account-ID:{account_id}", factory, run_id, tenant_id, user_id)`
    - [ ] For meetings without `account_id`: constructs input_text as `"Meeting: {title}\nDate: {meeting_date}\nAttendees: {comma-separated names from attendees JSONB}\nType: {meeting_type or 'discovery'}"` and calls `_execute_meeting_prep(api_key, input_text, factory, run_id, tenant_id, user_id)`
    - [ ] Verified: `_execute_meeting_prep` uses the passed-in `run_id` for event emissions
    - [ ] Stores each prep HTML output for inclusion in the daily brief
    - [ ] Emits SSE event per meeting: `{"event": "stage", "data": {"stage": "prepping", "message": "Preparing brief for: {title}..."}}`
    - [ ] If one prep fails: logs error, emits warning, continues to next
    - [ ] After all: emits summary "Prepared {N}/{total} meeting briefs."

- **ORCH-12**: Stage 4 — Execute Pending Tasks. For each confirmed task with a `suggested_skill`, the engine gathers context (context store + web search), formulates skill input, and invokes the appropriate skill to produce a deliverable. Tasks move to `in_review` status after execution.
  - **Acceptance Criteria:**
    - [ ] Queries tasks with `status='confirmed' AND suggested_skill IS NOT NULL` for the user
    - [ ] For each task: reads relevant context from context store (account intel, contacts, positioning) using the task's `account_id` or `meeting_id` to scope context
    - [ ] For each task: uses LLM (via `_execute_with_tools` or direct Anthropic call) to analyze the task, gather additional context via `web_search` if needed, and formulate the `input_text` for the target skill
    - [ ] Invokes the target skill engine: maps `suggested_skill` to the appropriate `_execute_*` function (e.g., 'sales-collateral' → `_execute_with_tools` with sales-collateral system_prompt, 'meeting-prep' → `_execute_meeting_prep()`, 'email-drafter' → `_execute_with_tools` with email-drafter system_prompt)
    - [ ] After successful execution: updates task `status` from `confirmed` → `in_review` via direct DB update
    - [ ] Stores each task deliverable (HTML output) for inclusion in the daily brief
    - [ ] Emits SSE event per task: `{"event": "stage", "data": {"stage": "executing", "message": "Executing task: {title} via {suggested_skill}..."}}`
    - [ ] If one task fails: logs error, emits warning, continues to next task. Failed task in "Remaining Items"
    - [ ] Tasks with `trust_level='confirm'` (e.g., email-related) produce deliverables but do NOT auto-send — founder reviews in the brief
    - [ ] After all: emits summary "Executed {N}/{total} tasks. {failures} failed."

- **ORCH-06**: Stage 5 — HTML Daily Brief. Engine aggregates all stage outputs into a styled HTML document.
  - **Acceptance Criteria:**
    - [ ] HTML structure follows this hierarchy:
      ```html
      <div style="font-family: Inter, sans-serif; max-width: 800px; margin: 0 auto;">
        <header> <!-- Date, "Daily Brief" title --> </header>
        <section id="sync"> <!-- Sync Summary: counts, errors --> </section>
        <section id="processed"> <!-- Processing Summary: per-meeting card with title + key intel --> </section>
        <section id="prep"> <!-- Prep: summary card per meeting (title, account, key insight) with "Full brief in Library" note --> </section>
        <section id="tasks"> <!-- Task Execution: deliverables produced per task, with skill used --> </section>
        <section id="remaining"> <!-- Remaining: failed items, overflow items, Phase 67 deferred items --> </section>
      </div>
      ```
    - [ ] Prep section shows summary cards (title, account name, 1-line key insight from prep output), NOT full inline HTML. Full prep briefings are separate documents in the library.
    - [ ] Task Execution section shows: per-task card with title, skill used, deliverable summary (first 2-3 lines of output), link to full deliverable in library. Tasks that were not executed (no suggested_skill, or status != confirmed) listed separately as "Pending review".
    - [ ] Remaining Items lists: meetings that failed processing, meetings that failed prep, tasks that failed execution, detected tasks not yet confirmed
    - [ ] Empty states per ORCH-11: each section handles zero items gracefully
    - [ ] Styled with inline CSS: Inter font, `#E94D35` for accents/highlights, `#121212` headings, `#6B7280` body text, 12px border-radius on cards, white background with warm tints
    - [ ] HTML renders in MeetingPrepRenderer via `dangerouslySetInnerHTML` (tested)
    - [ ] Output stored as `rendered_html` on SkillRun record
    - [ ] Document appears in `/documents` library with `skill_name='flywheel'`

- **ORCH-07**: SSE event streaming throughout execution. All events emitted to parent run's `events_log`.
  - **Acceptance Criteria:**
    - [ ] Every stage transition emits a `stage` event: `{"event": "stage", "data": {"stage": "<name>", "message": "<human-readable>"}}`
    - [ ] Stage names in order: `syncing`, `processing`, `prepping`, `executing`, `composing` (for brief generation), `done`
    - [ ] Sub-engine calls do NOT create separate SkillRun records — all events to parent `run_id`
    - [ ] MCP polling sees progress via `GET /skills/runs/{run_id}` status
    - [ ] SSE stream at `GET /skills/runs/{run_id}/stream` shows real-time progress
    - [ ] Final `done` event includes `rendered_html`
    - [ ] On fatal error (no API key): emits `error` event with clear message, sets status=failed

- **ORCH-08**: Replace current client-side SKILL.md with backend-engine version.
  - **Acceptance Criteria:**
    - [ ] `skills/flywheel/SKILL.md` replaced with new engine-frontmatter version
    - [ ] `skills/flywheel/references/api-reference.md` deleted
    - [ ] No references to `FLYWHEEL_API_TOKEN`, `curl`, `Bash` tool, or `allowed-tools` remain in `skills/flywheel/`
    - [ ] Git commits for Phase 66-01 and 66-02 (the incorrect implementation) remain in history — we don't rewrite history

### Should Have

- **ORCH-09**: MCP tool description updated to mention flywheel skill.
  - **Acceptance Criteria:**
    - [ ] `flywheel_run_skill` docstring in `cli/flywheel_mcp/server.py` mentions "flywheel" alongside "meeting-prep" and "company-intel"
    - [ ] Default `skill_name` parameter remains "meeting-prep"

- **ORCH-10**: Graceful handling of empty states.
  - **Acceptance Criteria:**
    - [ ] No Granola integration: Sync section shows "Granola not connected. Connect in Settings > Integrations."
    - [ ] No unprocessed meetings: Processing section shows "All meetings up to date."
    - [ ] No upcoming external meetings: Prep section shows "No upcoming external meetings today."
    - [ ] No pending tasks: Tasks section shows "No pending tasks."
    - [ ] All stages empty: Brief renders with date header and "Your day is clear" message

### Won't Have (Phase 66)

- **Composable tools (`run_skill`, `query_meetings`, `query_tasks`, `sync_meetings`)** — The engine queries DB and calls engines directly. Composable tools for the generic `_execute_with_tools` path are a future enhancement for other skills.
- **Smart defaults / "run all"** — FLY-08, deferred to Phase 68.
- **Learned preferences / progressive trust** — Phase 68.
- **Web UI `/brief` page** — Phase H per requirements. Document library is sufficient for now.
- **Multi-user support** — Tasks are Zone 1 (user-private). Single-user orchestration only.
- **docx generation from backend** — HTML output only.
- **Subcommand routing via input_text** — Phase 66 always runs the full pipeline. No "only prep" or "skip sync" modes.

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Granola API key expired/invalid | Stage 1 emits warning "Granola API key invalid. Reconnect in Settings.", continues to Stage 2 |
| Granola API returns 500/timeout | Stage 1 emits warning "Granola sync failed: {error}", continues to Stage 2 |
| Meeting processor fails for 1 meeting | Stage 2 logs error, emits warning, continues to next. Failed meeting in "Remaining Items" |
| Meeting prep fails for 1 meeting | Stage 3 logs error, emits warning, continues to next. Failed meeting in "Remaining Items" |
| Anthropic API key missing (no BYOK, no subsidy) | Engine fails fast: "No API key available. Add your Anthropic API key in Settings." status → failed |
| Anthropic API rate limited (429) | Retry with backoff (existing engine pattern). After 3 retries: fail sub-task, continue to next |
| 30+ unprocessed meetings (returning after absence) | Stage 2 processes ALL — may take a while but gets the user fully caught up |
| Many meetings today need prep | Stage 3 preps ALL today's external meetings — runs as long as needed |
| Task suggested_skill not recognized | Stage 4 attempts generic `_execute_with_tools` with the skill's system_prompt from DB. If skill not found in DB, skips with warning. |
| Task has no account_id or meeting_id (no context to gather) | Stage 4 still executes — uses web_search and general context store. Quality may be lower but still produces a deliverable. |
| Task execution produces empty/poor output | Task still moved to `in_review`. Founder reviews and decides quality. |
| No meetings, no tasks, nothing to do | Brief renders "Your day is clear" — not an error |
| Concurrent flywheel runs (user triggers twice) | Both run independently. Existing `check_concurrent_run_limit` applies |
| Meeting status changed between Stage 1 and Stage 2 | Stage 2 re-queries fresh — already-processed meetings skipped |
| MCP times out (~5 min) while engine still running | MCP returns "still running" with library link. Engine continues. User checks `/documents` later |
| Flywheel skill not seeded to DB | `POST /skills/runs` returns 404 "Skill 'flywheel' not found". User needs `flywheel db seed` |

## Constraints

- **Direct DB access only** — Engine queries Meeting, Task, Integration tables via SQLAlchemy. No HTTP calls to own API. No curl.
  - **Why:** The backend calling its own REST API is circular waste. Direct DB access is the established engine pattern.

- **Direct engine function calls for sub-skills** — Call `_execute_meeting_processor()` and `_execute_meeting_prep()` as function calls. No child SkillRun records, no job queue delegation.
  - **Why:** Child SkillRun records risk job queue deadlock (single-worker), add 5s+ latency per sub-skill, and split the event stream.

- **Events on parent run only** — All `_append_event_atomic()` calls use the orchestrator's `run_id`.
  - **Why:** MCP client and SSE endpoint poll ONE run_id. Split event streams are invisible to user.

- **No volume caps** — Process all unprocessed meetings, prep all today's meetings, execute all confirmed tasks. The user controls cost by choosing when to invoke, not by artificial limits.
  - **Why:** One command does everything. Caps force multiple re-runs which defeats the purpose.

- **HTML output only** — No docx, no PDF. HTML stored as `rendered_html`, rendered in existing MeetingPrepRenderer.
  - **Why:** HTML rendering pipeline is proven. docx requires filesystem dependencies not on backend.

- **Auth from MCP session** — No `FLYWHEEL_API_TOKEN` env var. JWT from MCP → backend extracts tenant_id and user_id.
  - **Why:** Every other skill works this way. "Login once, get all skills."

- **Existing engine signature pattern** — `async def func(factory, run_id, tenant_id, user_id, api_key) -> tuple[str, dict, list]`
  - **Why:** Consistency with meeting-processor, meeting-prep. The dispatcher expects this interface.

- **No subcommand routing in Phase 66** — `input_text` is ignored. Full pipeline always runs.
  - **Why:** Subcommand routing adds complexity. Ship the core loop first; add modes in Phase 68.

## Anti-Requirements

- This is NOT a Claude Code slash command skill. It does NOT use Bash, curl, Read, or any Claude Code tools.
- This is NOT a thin display client. It actively syncs, processes, and preps — not just reads and formats.
- This does NOT auto-send anything. All deliverables are for founder review. "Never auto-send" is a hard constraint.
- This does NOT create child SkillRun records. All execution is direct function calls within the parent run.
- This does NOT require any client-side installation beyond `flywheel login` + MCP setup (one-time `flywheel setup-claude-code`).
- Phase 66 does NOT support subcommands via `input_text`. The full pipeline always runs.

## Open Questions

All critical open questions from the draft have been resolved:

| Question | Resolution |
|----------|-----------|
| Sync dedup logic | Extract to shared `sync_granola_meetings()` function — ORCH-03 specifies this |
| Sub-engine event passthrough | Verified: sub-engines use passed-in `run_id` for events — ORCH-04/05 acceptance criteria require verification |
| Meeting prep input format | Defined: `"Meeting: {title}\nDate: {date}\nAttendees: {names}\nType: {type}"` — ORCH-05 |
| Prep detection mechanism | Query `skill_runs` table for completed meeting-prep with matching title — ORCH-05. No `prepped` status exists on Meeting (valid statuses: pending, scheduled, recorded, complete, failed, skipped) |
| Concurrent run behavior | Both run independently; existing `check_concurrent_run_limit` applies |

**Remaining implementation-time verifications:**
- [ ] Verify `_execute_meeting_processor` source: all `_append_event_atomic()` calls use passed-in `run_id` (not internally-created)
- [ ] Verify `_execute_meeting_prep` source: same verification
- [ ] Verify `contract_reads` file names match actual context store file names

## Artifacts Referenced

| Artifact | What was extracted |
|----------|--------------------|
| CONCEPT-BRIEF-flywheel-ritual-rearchitect.md | Architecture decisions, phasing, guard rails, moat assessment |
| skill_executor.py | Engine dispatch, function signatures, sub-engine patterns |
| seed.py (line 269) | Confirmed: frontmatter `engine` key → `engine_module` DB column |
| meeting_processor_web.py | Engine module structure, factory pattern |
| granola_adapter.py | list_meetings() signature, RawMeeting dataclass |
| meetings.py (lines 142-253) | Sync dedup logic: ~112 lines inline, uses AsyncSession, hard+soft dedup |
| meetings.py (list_meetings) | Query pattern: time, processing_status filters |
| tasks.py (list_tasks) | Query pattern: status, priority, meeting_id filters. Valid statuses: detected, in_review, confirmed, in_progress, done, blocked, dismissed |
| models.py (Meeting) | Valid processing_status: pending, scheduled, recorded, complete, failed, skipped. No prepped status. No prepped_at column. processed_at timestamp set on complete. |
| MeetingPrepRenderer.tsx | HTML rendering via dangerouslySetInnerHTML with sanitization |
| REQUIREMENTS.md | FLY-01 through FLY-08, Phase E/F/G/H deferrals |

---

## Review Findings Addressed

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Prep detection contradicts no-child-SkillRun constraint | Critical | Use `skill_runs` table query (not child records — we query existing completed runs from prior invocations). Added to ORCH-05 criteria. |
| 2 | No volume caps on Stage 2/3 | Critical | Added max 5 processed, max 3 prepped per run. Added to constraints. |
| 3 | `engine` vs `engine_module` key unverified | Critical | Verified: seed.py line 269 reads `engine` key. Added verification to ORCH-01/02 criteria. |
| 4 | Sync dedup logic absent | Major | ORCH-03 rewritten: extract shared function, both endpoint and engine call it. |
| 5 | Sub-engine event passthrough unverified | Major | Added verification requirement to ORCH-04/05 acceptance criteria. |
| 6 | HTML brief structure unspecified | Major | Added HTML hierarchy template to ORCH-06 with section structure. |
| 7 | No input_text handling | Major | Added to Anti-Requirements and Won't Have: Phase 66 ignores input_text, full pipeline always runs. |
| 8 | No timeout specification | Minor | Added edge case: MCP timeout is acceptable, engine continues, user checks library. |
| 9 | contract_reads file names unverified | Minor | Added to implementation-time verifications. |
| 10 | ORCH-09 tools not needed for Phase 66 | Minor | Moved to Phase 67 Won't Have. Only MCP description update (ORCH-09) remains as Should Have. |
| 11 | ORCH-09 premature | Subtraction | Removed from Phase 66 scope. Tools deferred to Phase 67. |
| 12 | Prep briefings inline too large | Subtraction | Changed to summary cards with "View in Library" note. Full briefings are separate documents. |
| 13 | Phase 66 scope assessment | Scope | 3 plans confirmed: Plan 01 (sync refactor + SKILL.md), Plan 02 (engine + dispatch), Plan 03 (HTML brief + wiring) |
| 14 | Open questions should be resolved | Scope | All 5 resolved with verified facts. Only implementation-time verifications remain. |
