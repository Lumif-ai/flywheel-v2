# Concept Brief: Flywheel Ritual — Backend Orchestrator Engine

> Generated: 2026-03-28
> Mode: Deep (with codebase architecture verification)
> Rounds: 3 deliberation rounds
> Active Advisors: 14 (10 core + Slootman, Grove, Ohno, McChrystal)
> Artifacts Ingested: skill_executor.py, tool registry, job_queue.py, seed.py, MCP server, meeting-prep engine, meeting-processor engine, frontend document renderer, REQUIREMENTS.md, 66-RESEARCH.md

## Problem Statement

The `/flywheel` ritual was incorrectly built as a Claude Code slash command (SKILL.md with Bash/curl calls to the backend API). This is architecturally wrong for three reasons:

1. **Distribution model mismatch.** Every other Flywheel skill (meeting-prep, company-intel, meeting-processor) runs server-side with direct DB access, invoked via MCP. Users just run `flywheel login` and get all skills. The curl-based skill requires separate SKILL.md installation and a manual `FLYWHEEL_API_TOKEN` env var — a completely different distribution model.

2. **Circular architecture.** The backend calling its own REST API through curl is pure waste. The engine has direct DB access — no HTTP round-trip needed.

3. **Wrong ambition level.** The current implementation is a thin display client ("show me my day"). The vision is an intelligent orchestrator ("do my day") — sync meetings, process recordings, prep for calls, generate deliverables for pending tasks, all powered by the compounded context store.

**What changed from original framing:** The requirements (FLY-01 through FLY-06) described a "Claude Code skill" which the research phase interpreted literally as client-side. The actual intent is a backend-executed orchestrator skill that's part of the Flywheel platform, invocable via MCP like every other skill.

## Proposed Approach

A **dedicated backend engine** (`_execute_flywheel_ritual`) that runs a deterministic 5-stage pipeline. Within each stage, it calls existing engine functions directly (meeting-processor, meeting-prep) or uses the LLM tool-use loop for intelligent decisions (task execution). New tools added to the backend tool registry enable DB queries and skill chaining.

**Key reframe from deliberation:** The pipeline stages are fixed (sync → process → prep → execute tasks → brief), but the decisions WITHIN each stage are intelligent — the LLM decides which meetings to prep, what context to gather for each task, which skill to invoke. This hybrid approach avoids both "dumb pipeline" and "LLM re-deriving obvious ordering."

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Engine type | Dedicated engine (not generic tool-use) | Pipeline stages are fixed knowledge; explicit error boundaries per stage | Grove (operational rigor), Vogels (failure handling), Carmack (simplest code) | Pure `_execute_with_tools` — would make LLM re-derive execution order every run |
| Task execution | LLM-powered within Stage 4 | Which skill to call, what context to gather — these are judgment calls, not lookups | Hickey (decomplect), Chesky (intelligence, not lookup) | Deterministic dispatch table on `suggested_skill` field |
| Sub-skill invocation | Direct engine function calls (not child SkillRun records) | One stream, one run, one place to check status; avoids job queue deadlock | Vogels (observability), Carmack (simplicity) | Child SkillRun records with polling — adds 5s latency per sub-skill, deadlock risk with single-worker queue |
| Output format | HTML rendered in frontend document library | Already works for meeting-prep; user reviews deliverables in web app | — | CLI text output — doesn't persist, can't share |
| Deliverables | Always for review, never auto-sent | Founder reviews everything; trust is earned over time | User's hard constraint | Auto-execute with trust_level gating |
| Phasing | 3 phases (66 rework + 67 + 68) | Want to implement everything but can phase delivery | Slootman (scope ruthlessly), Grove (dependency chain) | Single monolithic phase |
| Tool extension | New tools in registry (query_meetings, query_tasks, run_skill, etc.) | Composable, reusable by future skills | Hickey (composability), Carmack (extension point) | Hardcoded DB queries in engine function |

## Advisory Analysis

### Theme 1: Pipeline Architecture
**Grove** (operational rigor) and **Ohno** (waste elimination) drove the execution ordering. The flywheel ritual is a dependency chain: sync enriches the meeting list, processing enriches the context store, prep uses enriched context, task execution uses enriched context. Each stage makes the next stage better — this IS the flywheel effect. Ohno identified the curl-to-own-API pattern as pure muda (waste) — direct DB access eliminates an entire layer.

### Theme 2: Intelligence Within Structure
**Hickey** (simplicity) and **Carmack** (ship) resolved the LLM-vs-deterministic tension. The pipeline stages are deterministic (fixed order, explicit error boundaries). The decisions within stages — which meetings to prep, what context to gather for a one-pager, how to formulate skill inputs — are where LLM intelligence adds value. This separation keeps the code simple while enabling adaptive behavior.

### Theme 3: Failure as Normal
**Vogels** (failure thinking) and **McChrystal** (adaptive execution) shaped the resilience model. In a multi-skill orchestrator, partial failure is the expected case. Meeting-prep fails for one meeting, sales-collateral can't find enough context for a task, token budget runs thin. The orchestrator must produce value from whatever it completes — never fail atomically. Each stage catches errors, logs them, continues to the next.

### Theme 4: Competitive Moat
**Helmer** (7 powers) identified the compounding data advantage. Every orchestrator run enriches the context store (processed meetings → intelligence → better prep → better deliverables). A competitor would need to rebuild the entire context store to match output quality. This is a cornered resource — the data flywheel the product is named after.

### Execution Advisors
**Slootman** (execution intensity) insisted on phasing: Stages 1-3 (sync/process/prep) first because they leverage existing engines. Stage 4 (task execution) is the hard part — multi-skill LLM orchestration — and should be its own phase. **McChrystal** added: the plan will change once Stage 4 meets real tasks. Ship Stages 1-3, learn from usage, then design Stage 4 with real data.

## Tensions Surfaced

### Tension 1: LLM Planning vs Deterministic Pipeline
- **Carmack/Hickey** argue: Let the LLM plan execution via tool-use loop — more adaptive, less code
- **Grove/Slootman** argue: Pipeline stages are fixed — don't waste tokens re-deriving order
- **Why both are right:** The STAGES are fixed, but the DECISIONS within stages need intelligence
- **User's resolution:** Hybrid — dedicated engine handles stage ordering, LLM handles within-stage decisions
- **User's reasoning:** "It's an orchestrator that identifies what to do and does it" — not just a display, but also not fully autonomous without structure

### Tension 2: Scope of Stage 4 (Task Execution)
- **Chesky** argues: The 11-star version handles every task type — one-pagers, email drafts, research, introductions
- **PG** argues: Quality matters — if auto-generated one-pagers are mediocre, the founder wastes MORE time reviewing
- **Why both are right:** The vision is complete task execution, but quality requires rich context
- **User's resolution:** Start with review-always model. Quality improves as context store compounds.
- **User's reasoning:** "It is never sent. It is for founder to review."

### Unresolved Tensions
- **Token cost at scale**: Running 5+ sub-skills per orchestrator invocation could cost $5-10+ in API calls. No budget enforcement exists today. Needs monitoring after Phase 66 ships.
- **Skill capability on web vs CLI**: Sales-collateral produces docx locally but only HTML on backend. HTML is acceptable for v1 per user confirmation. Full docx generation from backend is a future enhancement.

## Moat Assessment

**Achievable power: Cornered Resource (compounding data flywheel)**
**Moat status: Emerging**

The orchestrator creates a positive feedback loop: more runs → richer context store → better deliverables → more usage → even richer context. Each meeting processed, each prep generated, each one-pager created adds to the compounding advantage. A competitor starting from zero context cannot match output quality.

## Architecture Specification

### Backend Engine: `_execute_flywheel_ritual()`

Located in `backend/src/flywheel/engines/flywheel_ritual.py`. Registered in `skill_executor.py` dispatch logic.

**5-Stage Pipeline:**

```
Stage 1: SYNC
  → Call Granola adapter sync function directly (not via HTTP)
  → Emit SSE events: "Syncing from Granola... {synced} new, {skipped} filtered"
  → Output: sync stats

Stage 2: PROCESS
  → Query meetings WHERE processing_status IN ('pending', 'recorded')
  → For each: call _execute_meeting_processor() directly
  → Emit SSE events per meeting: "Processing: {title}... extracting intelligence..."
  → Output: processed meetings list, intelligence extracted summary

Stage 3: PREP
  → Query meetings WHERE time=upcoming AND processing_status != 'prepped'
  → Filter to external meetings (meeting_type != 'internal')
  → For each: call _execute_meeting_prep() or _execute_account_meeting_prep()
  → Emit SSE events: "Preparing brief for {title}..."
  → Output: prep briefings (HTML per meeting)

Stage 4: EXECUTE TASKS (Phase 67)
  → Query tasks WHERE status='confirmed' AND suggested_skill IS NOT NULL
  → For each task: LLM reads task + context_read + web_search → formulates skill input
  → Call appropriate skill via run_skill tool or direct engine call
  → Mark task status → 'in_review' after deliverable produced
  → Output: deliverables per task (HTML)

Stage 5: BRIEF
  → Aggregate all stage outputs into single HTML daily brief
  → Include: sync summary, processing summary, prep links, task deliverables, remaining items
  → Store as rendered_html on SkillRun
  → Appears in /documents library
```

### New Backend Tools (Tool Registry Extensions)

```python
# All tools use RunContext.factory for DB session access

query_meetings(filters: {time?, processing_status?, limit?})
  → Returns: [{id, title, meeting_date, attendees, processing_status, account_id, meeting_type}]
  → Handler: Direct SQLAlchemy query on Meeting table, tenant-scoped

query_tasks(filters: {status?, priority?, suggested_skill?, limit?})
  → Returns: [{id, title, source, task_type, priority, suggested_skill, trust_level, meeting_id}]
  → Handler: Direct SQLAlchemy query on Task table, user-scoped

update_task_status(task_id: uuid, status: str)
  → Returns: success/failure with validation
  → Handler: Same logic as PATCH /tasks/{id}/status endpoint

run_skill(skill_name: str, input_text: str)
  → Returns: {output: str, rendered_html: str | null}
  → Handler: Calls _execute_* function directly based on skill_name dispatch
  → Events emitted to PARENT run's events_log

sync_meetings()
  → Returns: {synced, skipped, already_seen, total_from_provider}
  → Handler: Calls granola_adapter.sync() directly with tenant's integration credentials
```

### SKILL.md (Seeded to DB)

```yaml
---
name: flywheel
version: "2.0"
description: >
  Intelligent daily operating ritual. Syncs meetings from Granola, processes
  unprocessed recordings, prepares briefings for upcoming meetings, and executes
  pending tasks by invoking appropriate skills. Returns a rich HTML daily brief
  with all deliverables for founder review.
engine: flywheel_ritual
web_tier: 1
contract_reads:
  - contacts
  - company-intel
  - competitive-landscape
  - positioning
contract_writes:
  - contacts
  - company-intel
tags:
  - orchestrator
  - daily-ritual
---
```

The `system_prompt` (body after frontmatter) provides instructions for Stage 4's LLM-powered task execution decisions. Other stages are handled by the deterministic engine code.

### MCP Integration

No MCP changes needed. The existing `flywheel_run_skill("flywheel")` flow works:
1. MCP calls `POST /skills/runs` with `skill_name="flywheel"`
2. Job queue picks up the pending run
3. `execute_run()` dispatches to `_execute_flywheel_ritual()`
4. SSE streams progress events
5. MCP polls until completion, returns link to document library

The MCP tool description should be updated to mention the flywheel skill alongside meeting-prep and company-intel.

### Frontend Rendering

No frontend changes needed for v1. The orchestrator's `rendered_html` output renders in the existing `MeetingPrepRenderer` (which handles any pre-rendered HTML via `dangerouslySetInnerHTML` with sanitization). The document appears in the `/documents` library.

Future enhancement: a dedicated `/flywheel` or `/brief` page that auto-loads the latest flywheel run output.

## Phasing

### Phase 66 (Rework): Engine + Stages 1-3 + Brief
**Goal:** The flywheel ritual runs via MCP, syncs meetings, processes recordings, preps for upcoming meetings, and produces an HTML daily brief.
- Delete current SKILL.md (curl-based) and references/api-reference.md
- Create `backend/src/flywheel/engines/flywheel_ritual.py`
- Add new tools to tool registry: `query_meetings`, `query_tasks`, `sync_meetings`
- Add dispatch case in `skill_executor.py`
- Create new SKILL.md with correct frontmatter (engine: flywheel_ritual, web_tier: 1)
- Seed to DB via `flywheel db seed`
- Produce HTML daily brief aggregating all stage outputs

### Phase 67 (New): Stage 4 — Task Execution
**Goal:** The orchestrator reads confirmed tasks, gathers context, invokes appropriate skills (sales-collateral, email-drafter, etc.), produces deliverables.
- Add `run_skill` and `update_task_status` tools to registry
- LLM-powered task analysis: read task → context_read → web_search → formulate input → run_skill
- Handle each suggested_skill type (sales-collateral, email-drafter, meeting-prep, etc.)
- Mark tasks as 'in_review' after deliverable produced
- Deliverables embedded/linked in HTML brief

### Phase 68 (New): Smart Defaults + Learning
**Goal:** FLY-08 "run all" smart defaults, learned preferences, progressive trust.
- One-command "do everything sensible" mode
- Learn which tasks the founder always confirms/dismisses
- Improve task execution quality from feedback
- Progressive trust: skills that consistently get approved can skip review queue

## Open Questions

- [ ] **Token cost governance:** Running 5+ sub-skills per invocation. Need monitoring + budget caps after Phase 66 ships. The `token_budget` field on SkillDefinition exists but is unenforced.
- [ ] **Job queue concurrency:** Single-worker queue may bottleneck when orchestrator calls multiple engines. May need to increase worker count or switch to direct function calls (bypassing queue).
- [ ] **Granola sync auth:** The sync function needs the tenant's Granola API key from the Integration table. The engine has DB access via factory, but need to verify the key decryption path works from engine context.
- [ ] **Sales-collateral on backend:** Currently a Claude Code skill with docx dependencies. HTML output is acceptable for v1. Full docx generation from backend needs investigation for v2.
- [ ] **MCP tool discoverability:** No `list_skills` MCP tool exists. Claude Code guesses skill names from the static tool description. Should add a `list_skills` MCP tool or update the description dynamically.

## Recommendation

**Proceed to /spec for Phase 66 rework, then plan and execute.**

The architecture is sound — it follows established patterns (dedicated engine, SSE events, HTML output, document library). Phase 66 rework leverages existing engines (meeting-processor, meeting-prep) and adds composable tools to the registry. Phase 67 (task execution) is the ambitious part and benefits from real-world usage data from Phase 66.

**Critical guard rails for re-planning:**
1. SKILL.md must have `engine: flywheel_ritual` and `web_tier: 1` — NOT `allowed-tools: [Bash, Read]`
2. Engine calls other engines DIRECTLY (function calls) — never via HTTP/curl
3. All events stream to parent run's events_log — one run, one stream
4. HTML output stored as `rendered_html` — renders in existing document library
5. No env vars, no FLYWHEEL_API_TOKEN — auth comes from the authenticated MCP session

## Artifacts Referenced

| Artifact | What was extracted |
|----------|--------------------|
| `skill_executor.py` (3205 lines) | Engine dispatch logic, `_execute_with_tools` generic path, `_execute_meeting_prep` pattern |
| `tools/__init__.py` | Tool registry extension pattern, existing tools inventory |
| `tools/schemas.py` | Tool JSON schema format for Anthropic API |
| `job_queue.py` | Single-worker polling loop, deadlock risk for child runs |
| `seed.py` | SKILL.md frontmatter → skill_definitions mapping, `engine` field |
| `cli/flywheel_mcp/server.py` | MCP tool definitions, polling pattern, no list_skills tool |
| `frontend/documents/` | DocumentViewer, SkillRenderer, MeetingPrepRenderer — HTML rendering path |
| `66-RESEARCH.md` | Original (incorrect) research — identified root cause of misunderstanding |
| `REQUIREMENTS.md` | FLY-01 through FLY-08 requirements, out-of-scope boundaries |
| `PROJECT.md` | Three-layer architecture (Intelligence → Autopilot → Ritual) |
