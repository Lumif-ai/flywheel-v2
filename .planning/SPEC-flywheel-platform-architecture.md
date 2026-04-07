# Flywheel Platform Architecture — Specification

> Status: Draft
> Created: 2026-03-30
> Last updated: 2026-03-30
> Source: CONCEPT-BRIEF-flywheel-platform-architecture.md (brainstorm, 4 rounds, 14 advisors)

## Overview

Transform Flywheel from a backend-executed skill runner into a platform where Claude Code
is the brain and Flywheel is the data layer. Founders install one MCP server, get 20 curated
skills, and their business intelligence compounds automatically. When interactive (Claude Code),
ALL LLM work runs through Claude Code's subscription. When scheduled (cron), the existing
backend ritual runs unchanged.

## Core Value

**A founder says something natural in Claude Code ("prep my RMR meeting", "create a one-pager
for COverage", "morning brief") and the right skill is discovered from the Flywheel catalog,
context is loaded, the skill executes via Opus with interactive clarification if needed, and
the result appears in the Flywheel library UI.**

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (interactive) | Claude Code terminal with Flywheel MCP installed | Run skills, compound context, see results in UI |
| Founder (passive) | Any Claude Code conversation | Business intel auto-routed to context store |
| Scheduled ritual | Cron trigger | Morning brief runs unattended, results in library |
| Design partner | First install of Flywheel MCP | Get value in first 10 minutes |

## Requirements

### Must Have

#### Wave 0: MCP Primitives

- **MCP-01**: `flywheel_fetch_skills` — List all enabled skills from `skill_definitions`
  table with name, description, tags, contract_reads, contract_writes, and triggers.
  - **Tool Description (visible to Claude Code):**
    > "List all available Flywheel skills with descriptions, categories, and trigger
    > phrases. Call this to discover what Flywheel can do for the user, or to find
    > the right skill for a user's request. Returns skill names, descriptions,
    > categories, trigger phrases, and context store contracts (what each skill
    > reads/writes). Use trigger phrases to match natural language requests to skills."
  - **Acceptance Criteria:**
    - [ ] Returns JSON array of skill objects from `skill_definitions WHERE enabled = true`
    - [ ] Each object includes: name, description, tags (first tag = category), contract_reads, contract_writes
    - [ ] Response includes a `triggers` field derived from `parameters->>'triggers'` JSONB
    - [ ] Claude Code can read the response and match a natural language request to a skill
    - [ ] Latency < 500ms (single DB query, no LLM)

- **MCP-02**: `flywheel_fetch_skill_prompt` — Load the full system prompt for a named skill.
  - **Tool Description (visible to Claude Code):**
    > "Load the full execution instructions for a Flywheel skill by name. Returns
    > the system prompt that you should follow to execute the skill. Call this after
    > identifying which skill to run via flywheel_fetch_skills. The prompt contains
    > step-by-step instructions, output format, and quality criteria."
  - **Implementation:** Authenticated API call to `GET /api/v1/skills/{name}/prompt`.
    Requires same `require_tenant` auth as all other endpoints. Prompt travels over
    the same authenticated HTTP connection as context store reads.
  - **Acceptance Criteria:**
    - [ ] Parameter: `skill_name` (string, required)
    - [ ] Returns the `system_prompt` text from `skill_definitions` for that skill
    - [ ] Wraps `GET /api/v1/skills/{name}/prompt` (new endpoint, standard auth)
    - [ ] Returns error message if skill not found or disabled
    - [ ] Claude Code uses this prompt as instructions to execute the skill
    - [ ] Latency < 200ms (single row lookup by unique name)

- **MCP-03**: `flywheel_fetch_meetings` — Return unprocessed meetings with transcripts.
  - **Tool Description (visible to Claude Code):**
    > "Fetch meetings that haven't been processed yet, including full transcripts.
    > Use this during the morning brief to find meetings that need summarization
    > and insight extraction. Returns meeting title, time, attendees, and transcript.
    > Process each meeting's transcript, then save the summary via
    > flywheel_save_meeting_summary."
  - **Acceptance Criteria:**
    - [ ] Returns meetings where `ai_summary IS NULL` (not yet processed)
    - [ ] Each meeting includes: id, title, start_time, attendees, transcript text
    - [ ] Ordered by start_time ascending (oldest first)
    - [ ] Optional parameter: `limit` (default 10, max 50)
    - [ ] Full transcript returned (no chunking — Opus has 1M context)
    - [ ] Wraps existing `GET /api/v1/meetings` with appropriate filters

- **MCP-04**: `flywheel_fetch_upcoming` — Return today's upcoming meetings with attendees.
  - **Tool Description (visible to Claude Code):**
    > "Fetch today's upcoming meetings with attendee details and linked accounts.
    > Use this to identify meetings that need preparation. Returns meeting title,
    > time, attendees (name + email), meeting type, and linked account if any.
    > After fetching, prepare each meeting using the meeting-prep skill."
  - **Acceptance Criteria:**
    - [ ] Returns meetings where start_time is today and in the future
    - [ ] Each meeting includes: id, title, start_time, end_time, attendees (name + email),
      meeting_type, external flag, account_id if linked
    - [ ] Ordered by start_time ascending
    - [ ] Wraps existing `GET /api/v1/meetings` with date filter

- **MCP-05**: `flywheel_fetch_tasks` — Return pending/confirmed tasks with context.
  - **Tool Description (visible to Claude Code):**
    > "Fetch tasks that need attention — pending triage, confirmed for execution,
    > or deferred. Returns task title, status, priority, due date, and suggested
    > skill if any. Use this during morning brief to surface action items, or
    > anytime the user asks about their tasks or commitments."
  - **Acceptance Criteria:**
    - [ ] Returns tasks where status IN ('detected', 'in_review', 'confirmed', 'in_progress', 'deferred')
    - [ ] Each task includes: id, title, description, status, priority, due_date,
      commitment_direction, source, suggested_skill, skill_context, account_id
    - [ ] Ordered by: due_date ASC NULLS LAST, then priority (high > medium > low)
    - [ ] Wraps existing `GET /api/v1/tasks/` with status filter

- **MCP-06**: `flywheel_fetch_account` — Return account details with linked context.
  - **Tool Description (visible to Claude Code):**
    > "Fetch detailed information about an account (prospect, customer, or partner).
    > Search by account ID or name (fuzzy match). Returns company details, contacts,
    > recent meetings, context store entries, and outreach history. Use this before
    > meeting prep, outreach drafting, or any account-specific skill execution."
  - **Acceptance Criteria:**
    - [ ] Parameter: `account_id` (UUID) OR `name` (string, fuzzy match)
    - [ ] When name provided: case-insensitive ILIKE search, return best match
    - [ ] Returns: account details, contacts, linked meetings (last 5), linked context
      entries, outreach history
    - [ ] Wraps existing `GET /api/v1/accounts/{id}` + related endpoints

- **MCP-07**: `flywheel_sync_meetings` — Trigger Granola sync and return result.
  - **Tool Description (visible to Claude Code):**
    > "Sync meetings from Granola calendar integration. Call this at the start of
    > the morning brief or when the user asks to refresh their meeting data. Returns
    > count of new and updated meetings. After syncing, use flywheel_fetch_meetings
    > to get unprocessed meetings."
  - **Acceptance Criteria:**
    - [ ] Triggers `POST /api/v1/meetings/sync`
    - [ ] Returns: count of new meetings synced, count of updated meetings
    - [ ] Waits for sync to complete (sync is fast, < 10s typically)
    - [ ] Returns error with message if Granola integration not connected

- **MCP-08**: `flywheel_save_document` — Save skill output to the library as raw content.
  - **Tool Description (visible to Claude Code):**
    > "Save a skill's output to the Flywheel library. Send the raw content
    > (markdown or structured text) — Flywheel renders it with the design system.
    > The document appears in the library UI immediately. Use this after every
    > skill execution to persist the deliverable. Optionally link to a skill name
    > and account."
  - **Acceptance Criteria:**
    - [ ] Parameters: `title` (string), `content` (string, markdown/text),
      `skill_name` (string, optional), `account_id` (UUID, optional)
    - [ ] Creates a `skill_runs` record with output=content, status="completed"
    - [ ] Backend renders content to HTML using Flywheel design system (on save or on read)
    - [ ] Returns: run_id, URL to view in library (`/documents/{run_id}`)
    - [ ] Document appears immediately in library UI
    - [ ] Export to PDF/DOCX handled by library UI (separate feature, not MCP)

- **MCP-09**: `flywheel_save_meeting_summary` — Write processed summary back to a meeting.
  - **Tool Description (visible to Claude Code):**
    > "Save a processed meeting summary back to Flywheel. Call this after you've
    > analyzed a meeting transcript and extracted insights. Updates the meeting
    > record so the summary appears on the meeting detail page. Write extracted
    > business intelligence to the context store separately via flywheel_write_context."
  - **Acceptance Criteria:**
    - [ ] Parameters: `meeting_id` (UUID), `summary` (string), `insights` (JSON, optional)
    - [ ] Updates `meetings.ai_summary` and `meetings.ai_insights` for the given meeting
    - [ ] Returns confirmation with meeting title
    - [ ] Meeting detail page in UI reflects the new summary immediately

- **MCP-10**: `flywheel_update_task` — Update task status or fields.
  - **Tool Description (visible to Claude Code):**
    > "Update a task's status, priority, or suggested skill. Use this to confirm
    > tasks, mark them done, assign a skill for execution, or change priority.
    > Call this after executing a task's skill to mark it complete, or during
    > triage to confirm or dismiss detected tasks."
  - **Acceptance Criteria:**
    - [ ] Parameters: `task_id` (UUID), `status` (string, optional),
      `suggested_skill` (string, optional), `priority` (string, optional)
    - [ ] Validates status transitions (e.g., can't go from 'done' to 'detected')
    - [ ] Wraps existing `PATCH /api/v1/tasks/{id}/status` or `PATCH /api/v1/tasks/{id}`
    - [ ] Returns updated task object

#### Wave 0: MCP Observability

- **OBS-01**: Structured logging for every MCP tool call.
  - **Acceptance Criteria:**
    - [ ] Every tool call logs: tool name, key parameters (redacted if sensitive),
      response size (bytes), duration (ms), success/fail
    - [ ] Implemented as a decorator or wrapper — not duplicated per tool
    - [ ] Logs to stderr (captured by Claude Code) and/or `~/.flywheel/mcp.log`
    - [ ] Log format: `[YYYY-MM-DD HH:MM:SS] tool=<name> params=<redacted> duration=<ms> status=<ok|error> size=<bytes>`
    - [ ] Errors log the exception type and message (not full stack trace)
    - [ ] Sensitive fields redacted: content bodies, system_prompt text, auth tokens

#### Wave 0: Skill Catalog Infrastructure

- **CAT-01**: Add `triggers` to skill metadata — either as a new JSONB column or
  stored in existing `parameters` JSONB field.
  - **Acceptance Criteria:**
    - [ ] Each skill has an array of trigger phrases (e.g., ["one-pager", "case study"])
    - [ ] `flywheel_fetch_skills` includes triggers in response
    - [ ] Triggers are populated from SKILL.md frontmatter during seed
    - [ ] `seed_skills.py` extracts trigger phrases from SKILL.md and stores them

- **CAT-02**: ~~Add `category` column~~ — REMOVED. Use `tags[0]` as de facto category.
  Existing `tags` array on `skill_definitions` already supports this. No migration needed.
  Ensure each skill's first tag is its category (meetings, sales, gtm, legal, strategy, content).

- **CAT-03**: Seed the 20 founder-facing skills into `skill_definitions` with
  metadata (triggers, tags, contract declarations). Existing prompts seeded as-is.
  - **Acceptance Criteria:**
    - [ ] All 20 skills from concept brief are in DB with enabled=true
    - [ ] Each has: name, description, system_prompt (existing, unchanged), triggers
      (in parameters JSONB), tags (first tag = category), contract_reads, contract_writes
    - [ ] Skills NOT in the catalog (dev tools, archived) have enabled=false or are not seeded
    - [ ] `seed_skills.py --verbose` shows all 20 as added/updated
    - [ ] Prompts are seeded AS-IS from current SKILL.md files — no adaptation in Wave 0

- **CAT-04**: Adapt Wave 1 skill prompts for MCP execution — **deferred to Wave 1**.
  - Adapt 5 core skill prompts (flywheel, meeting-processor, meeting-prep,
    sales-collateral, account-research) to use `flywheel_read_context` instead
    of local file paths, `flywheel_save_document` for output, etc.
  - This is content rewrite work, not mechanical seeding. Needs its own phase.

#### Wave 0: Feature Flags

- **FLAG-01**: Frontend route-level feature flags.
  - **Acceptance Criteria:**
    - [ ] `frontend/src/config/features.ts` exports a `FEATURES` config object
    - [ ] Routes for email, tasks, focus areas are gated behind flags
    - [ ] When flag is false: route not in nav, direct URL access redirects to home
    - [ ] When flag is true: route appears in nav and is accessible
    - [ ] Default state: email=false, tasks=false
    - [ ] Flags are compile-time constants (not API-driven) for simplicity

#### Wave 0: CLAUDE.md Seeding

- **SEED-01**: Flywheel installer writes CLAUDE.md integration rules.
  - **Acceptance Criteria:**
    - [ ] Install script writes to project-level CLAUDE.md (or appends if exists)
    - [ ] Three rules included: context store routing, flywheel-first skill lookup,
      output saving to library
    - [ ] Business intelligence → context store (contacts, companies, meetings, competitive,
      pain points, positioning, pricing signals)
    - [ ] Non-business data → local files are fine
    - [ ] Deliverables → save to Flywheel library AND optionally local
    - [ ] Skill lookup hierarchy: Flywheel catalog → local skills → general Claude Code

#### ~~Wave 0: Install Script~~ — DEFERRED to post-Wave 0

- **INST-01**: One-command Flywheel installation — **deferred**.
  - Manual setup for yourself and first 2-3 design partners is sufficient.
  - Build the install script when manual setup becomes a bottleneck (5+ users).
  - CLAUDE.md seeding (SEED-01) can be done manually for now.

### Should Have

- **MCP-11**: `flywheel_fetch_meetings` supports filtering by account or attendee name
  for targeted prep (e.g., "get me all meetings with RMR").

- **MCP-12**: `flywheel_save_document` supports markdown input with auto-conversion to
  HTML using the Flywheel design system (brand colors, typography).

- **CAT-04**: Skill catalog versioning — `flywheel_fetch_skills` returns version per skill
  so Claude Code can detect when a skill was updated.

- **FLAG-02**: Backend skill-level flags — `enabled` column on `skill_definitions` controls
  which skills appear in `flywheel_fetch_skills`. Already exists but ensure disabled skills
  are excluded from MCP responses.

- **PERF-01**: MCP tool response caching — `flywheel_fetch_skills` caches the skill catalog
  for 5 minutes to avoid repeated DB queries in a single conversation.

### Won't Have (this version)

- Hosted browser service — founders install Playwright locally via install script
- Skill marketplace / sharing between founders — deferred to post-Wave 1
- Version pinning for skills — latest always wins for now
- Real-time MCP notifications (skill completion events) — polling is fine
- Frontend redesign for the reduced feature set — just hide routes
- Mobile / responsive optimization
- Skill creation UI in Flywheel web app

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| No skills in DB (empty catalog) | `flywheel_fetch_skills` returns empty array with message: "No skills available. Run seed_skills.py to populate." |
| Skill prompt is NULL | `flywheel_fetch_skill_prompt` returns error: "Skill '{name}' has no system prompt configured." |
| Meeting has no transcript | `flywheel_fetch_meetings` includes the meeting but with `transcript: null`. Claude Code decides whether to skip. |
| Account name fuzzy match returns multiple | `flywheel_fetch_account` returns the best match (highest similarity) with a note if confidence is low. |
| MCP auth token expired | API client catches 401, calls `clear_credentials()`, returns "Authentication expired. Run `flywheel auth` to reconnect." |
| Save document with empty content | `flywheel_save_document` rejects with error: "Content cannot be empty." |
| Task status invalid transition | `flywheel_update_task` rejects with error: "Cannot transition from '{current}' to '{requested}'." |
| Granola not connected | `flywheel_sync_meetings` returns: "Granola integration not connected. Run flywheel setup to connect." |
| Skill execution produces questions not deliverable | Claude Code is the brain — it asks the user directly. No backend output validation needed (that was the old architecture's problem). |
| Context store write with duplicate content | `flywheel_write_context` checks for near-duplicate via existing dedup logic, increments evidence_count instead of creating new entry. |
| Install on machine without Python 3.12+ | Install script checks Python version first, shows clear error with install instructions. |
| CLAUDE.md already exists with custom content | Install script appends Flywheel section, does not overwrite existing content. |

## Constraints

- **No LLM calls in MCP tools**: Every MCP tool is a thin wrapper around a REST API call.
  Zero LLM inference in the MCP server or backend when called from Claude Code.
  WHY: All reasoning happens through Claude Code's subscription, not the user's API key.

- **Existing backend unchanged**: The flywheel ritual (`flywheel_ritual.py`) stays as-is
  for scheduled/cron runs. New MCP tools wrap existing API endpoints, they don't replace them.
  WHY: Working code shouldn't be rewritten. Two execution paths share one data layer.

- **Stdio transport only**: MCP server uses stdio (not HTTP/SSE) per current implementation.
  WHY: Claude Code's MCP integration uses stdio. No need for HTTP transport yet.

- **Auth via existing CLI flow**: MCP tools use the same Bearer token from `flywheel_cli.auth`.
  WHY: Already works. No new auth mechanism needed.

- **PostgreSQL 16**: All queries must be compatible with PostgreSQL 16 and asyncpg.
  WHY: Production database is PostgreSQL 16 via Supabase.

- **Tenant isolation via RLS**: Every MCP tool query is scoped to the authenticated tenant.
  WHY: Multi-tenancy is enforced at the database level. MCP tools inherit this automatically
  through the API's `require_tenant` dependency.

## Anti-Requirements

- This is NOT a rewrite of the backend. Backend API stays unchanged. MCP tools wrap it.
- This is NOT a frontend redesign. Feature flags hide routes, nothing else changes in the UI.
- This is NOT a skill rewrite. Wave 0 seeds existing skill prompts adapted for MCP context
  access. Deep skill adaptation happens in Waves 1-4.
- This is NOT about supporting non-Claude-Code clients. The MCP server targets Claude Code
  specifically. Web UI skill execution continues via the existing backend path.
- This does NOT add new database tables. We use existing tables (skill_definitions,
  skill_runs, documents, meetings, tasks, context_entries) with at most minor column additions.

## Technical Architecture

### MCP Server Changes (cli/flywheel_mcp/server.py)

```
Current (3 tools):
├── flywheel_run_skill        → POST /api/v1/skills/runs (keep unchanged)
├── flywheel_read_context     → GET /api/v1/context/search (keep unchanged)
└── flywheel_write_context    → POST /api/v1/context/files/{name}/entries (keep unchanged)

New (10 tools):
├── flywheel_fetch_skills     → GET /api/v1/skills (+ triggers from parameters JSONB)
├── flywheel_fetch_skill_prompt → GET /api/v1/skills/{name}/prompt (standard auth)
├── flywheel_fetch_meetings   → GET /api/v1/meetings?unprocessed=true
├── flywheel_fetch_upcoming   → GET /api/v1/meetings?today=true&upcoming=true
├── flywheel_fetch_tasks      → GET /api/v1/tasks/?status=detected,in_review,confirmed,in_progress,deferred
├── flywheel_fetch_account    → GET /api/v1/accounts/{id} or search by name
├── flywheel_sync_meetings    → POST /api/v1/meetings/sync
├── flywheel_save_document    → POST /api/v1/skills/runs (raw content, backend renders)
├── flywheel_save_meeting_summary → PATCH /api/v1/meetings/{id} (new endpoint)
└── flywheel_update_task      → PATCH /api/v1/tasks/{id}/status

Output routing (2 paths, all via MCP):
├── Content (markdown/text) → flywheel_save_document → backend renders HTML → library UI
├── Business intelligence   → flywheel_write_context → context store (compounds)
└── Export (PDF/DOCX)       → library UI feature (user-initiated, not MCP)
```

### API Client Changes (cli/flywheel_mcp/api_client.py)

Add methods to `FlywheelClient` for each new MCP tool, wrapping the corresponding
backend endpoints. Pattern matches existing `search_context()`, `start_skill_run()` methods.

### Backend API Changes

Most MCP tools wrap existing endpoints. New endpoints needed:

| Endpoint | Purpose | Why New |
|----------|---------|---------|
| `GET /api/v1/skills/{name}/prompt` | Return system_prompt for a skill (standard `require_tenant` auth) | Current list endpoint omits system_prompt for performance. Separate endpoint for on-demand prompt loading. |
| `PATCH /api/v1/meetings/{id}` | Write ai_summary + processing_status back to meeting | No update endpoint exists. Backend processing writes directly to DB. Claude Code needs a write-back path after processing transcripts. |

Backend rendering (new logic, not new endpoint):
- `POST /api/v1/skills/runs` receives raw markdown/text in `output` field
- Backend renders to HTML using Flywheel design system, stores in `rendered_html`
- Library UI displays `rendered_html` as before — no frontend change needed

### Database Changes

| Change | Table | Type |
|--------|-------|------|
| Store triggers in `parameters` JSONB | skill_definitions | No migration — existing JSONB field |
| Use `tags[0]` as category | skill_definitions | No migration — existing array column |
| Ensure `ai_summary` is writable via API | meetings | New PATCH endpoint exposes existing column |

### Frontend Changes

| Change | File(s) | Type |
|--------|---------|------|
| Feature flags config | `src/config/features.ts` (new) | New file |
| Route gating wrapper | `src/app/routes.tsx` | Modify existing |
| Nav gating | `src/components/nav` or layout | Modify existing |

## Execution Plan

### Wave 0 (this spec — the foundation)

```
Phase 1: Backend API + Seed (no MCP yet)
├── Add GET /api/v1/skills/{name}/prompt endpoint (return system_prompt, standard auth)
├── Add PATCH /api/v1/meetings/{id} endpoint (write ai_summary back)
├── Add markdown → HTML renderer for skill_run output (design system)
├── Update seed_skills.py to extract triggers from SKILL.md frontmatter
├── Ensure tags[0] = category for each skill (no new column needed)
└── Seed 20 founder-facing skills with existing prompts + triggers/tags

Phase 2: MCP Tools (10 new tools)
├── Add methods to FlywheelClient (api_client.py)
├── Add 10 @mcp.tool() functions to server.py with optimized descriptions
├── Add logging decorator (OBS-01) on every tool
└── Test each tool end-to-end

Phase 3: Feature Flags (frontend)
├── Create features.ts config
├── Gate email, tasks, focus routes
├── Gate corresponding nav items
└── Verify hidden routes redirect to home

Phase 4: CLAUDE.md + Manual Setup
├── CLAUDE.md template with three integration rules
├── Manual MCP server config for yourself + first design partners
├── Test: configure MCP → "morning brief" works
└── (Install script deferred to post-Wave 0)
```

### Waves 1-4 (future specs, not this document)

- Wave 1: Adapt 5 core skill prompts for MCP context (flywheel, meeting-processor,
  meeting-prep, sales-collateral, account-research)
- Wave 2: GTM skills + Playwright integration
- Wave 3: Specialist skills (legal, investor, brainstorm, spec, pricing)
- Wave 4: Content + demos

## Open Questions

None for Wave 0. All resolved in concept brief.

## Gaps Found During Generation (All Verified & Resolved)

1. **Skill system_prompt access** — `GET /api/v1/skills/` omits system_prompt.
   **Resolution:** New `GET /api/v1/skills/{name}/prompt` endpoint with standard
   `require_tenant` auth. Same security as context store reads. Reversed from
   CEO review (direct DB doesn't scale to design partners on Supabase).

2. **Document save path** — No `POST /api/v1/documents` exists.
   **Resolution:** `flywheel_save_document` wraps `POST /api/v1/skills/runs`
   with raw content. Backend renders markdown → HTML using design system.
   Library UI displays rendered_html as before.

3. **Meeting summary write-back** — No way to write ai_summary from Claude Code.
   **Resolution:** New `PATCH /api/v1/meetings/{id}` endpoint (~25 lines).

4. **Trigger phrases** — Not all SKILL.md files have triggers in frontmatter.
   **Resolution:** Store in `parameters` JSONB. No migration. Manual triggers
   for skills that lack them. Update seed_skills.py.

5. **Job queue re-execution risk** — `POST /skills/runs` with status="completed"
   could be picked up by job_queue_loop for re-execution.
   **Resolution:** Verify job_queue_loop only processes status="pending" runs.
   Add guard if needed. Must verify before building MCP-08.

## Review Decisions

### CEO Review (2026-03-31)

| # | Issue | Decision | Rationale |
|---|-------|----------|-----------|
| 1 | Skill prompt auth model | ~~Direct DB via psycopg2~~ → REST endpoint with standard auth | Direct DB doesn't scale to design partners (they'd need DATABASE_URL). Standard auth is same security as context store reads. |
| 2 | ~~psycopg2 connection model~~ | N/A — removed with decision #1 | |
| 3 | File path traversal (upload) | No restriction — trust Claude Code | MCP is local stdio, Claude Code has safety rails |
| 4 | Output loss on save failure | Trust Claude Code retry/fallback | Output is in conversation context, natural recovery |
| 5 | Output format | Raw content (markdown/text), backend renders HTML | Cleaner separation, consistent brand, simpler skills |
| 6 | Tool descriptions | Added to spec as acceptance criteria per tool | Critical for discoverability — the core value |
| 7 | MCP tool logging | Structured logging decorator on every tool | Debuggability for production issues |
| 8 | File upload MCP tool | Removed from Wave 0 | Content-first: save text, backend renders. Export = UI feature. |

### Spec Review (2026-03-31)

| # | Issue | Decision | Rationale |
|---|-------|----------|-----------|
| 9 | Task filter missing `in_progress` | Added to filter | In-progress tasks are actionable, must be surfaced |
| 10 | CAT-03 prompt adaptation is massive | Split: seed metadata (Wave 0) + adapt prompts (Wave 1) | Prompt adaptation is content rewrite, not mechanical seeding |
| 11 | Category column redundant with tags | Use `tags[0]` as category, skip migration | No new column needed, tags already exist |
| 12 | Install script highest effort / lowest ROI | Deferred to post-Wave 0 | Manual setup for first 2-3 design partners is fine |
| 13 | Skill run job queue re-execution risk | Verify job_queue_loop skips status="completed" runs | Must confirm before building flywheel_save_document |

## Artifacts Referenced

- CONCEPT-BRIEF-flywheel-platform-architecture.md — all decisions, tensions, resolved questions
- cli/flywheel_mcp/server.py — current MCP server (3 tools, FastMCP, stdio)
- cli/flywheel_mcp/api_client.py — FlywheelClient wrapping REST calls
- backend/src/flywheel/api/ — 30+ API endpoints across 20 routers
- backend/src/flywheel/db/models.py — SkillDefinition, SkillRun, Meeting, Task, Document schemas
- frontend/src/app/routes.tsx — 30+ React Router routes
- scripts/seed_skills.py — skill seeding pipeline
- 22 SKILL.md files — skill definitions with prompts and metadata
