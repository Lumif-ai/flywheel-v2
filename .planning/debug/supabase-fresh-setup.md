---
status: verifying
trigger: "First-time Supabase setup with fresh database fails to run the app end-to-end"
created: 2026-03-23T00:00:00Z
updated: 2026-03-23T03:00:00Z
---

## Current Focus

hypothesis: Issue 9 — convert_skill reads SKILL.md from local filesystem, but company-intel has no SKILL.md (uses a Python engine instead)
test: Added engine dispatch in execute_run that bypasses convert_skill/LLM tool-use loop for company-intel
expecting: Crawl runs through dedicated engine (crawl -> structure -> enrich -> write) without needing SKILL.md
next_action: User tests E2E — restart backend, trigger onboarding crawl

## Symptoms

expected: New user visits /onboarding, enters company URL, sees crawl results streaming in real-time
actual: Crawl completes with 0 items. Job queue worker fails silently. Multiple subsystem errors.
errors:
  1. PostgresSyntaxError in _append_event_atomic — SET LOCAL app.tenant_id syntax
  2. AttributeError: User has no attribute 'supabase_uid'
  3. Job queue worker crashes, no events_log entries written
  4. GET /tenants → 404
  5. GET /auth/api-key → 405
reproduction: Fresh Supabase, Base.metadata.create_all, start backend+frontend, visit /onboarding
started: First time running against live Supabase

## Eliminated

## Evidence

- timestamp: 2026-03-23T00:01
  checked: _append_event_atomic SQL in skill_executor.py line 922
  found: Uses `:event::jsonb` — SQLAlchemy interprets `::` as param binding (`:event` then `:jsonb`), causing PostgresSyntaxError
  implication: Every call to _append_event_atomic fails, which is the FIRST thing execute_run does — this breaks the entire job execution pipeline

- timestamp: 2026-03-23T00:02
  checked: User model in models.py
  found: User model has no `supabase_uid` column. anonymous_cleanup.py line 66 references `User.supabase_uid`
  implication: Cleanup will crash with AttributeError at runtime

- timestamp: 2026-03-23T00:03
  checked: TenantSwitcher.tsx line 25
  found: Calls `api.get('/tenants')` -> `GET /api/v1/tenants`. But tenant router prefix is `/tenants` with no root GET. User tenants list is at `/user/tenants`.
  implication: 404 on every page load for tenant switcher

- timestamp: 2026-03-23T00:04
  checked: AppSidebar.tsx line 25, ApiKeyManager.tsx line 20
  found: Frontend calls `GET /auth/api-key` but only POST and DELETE exist. No GET endpoint for checking key status.
  implication: 405 on every page load

- timestamp: 2026-03-23T00:05
  checked: job_queue.py error handling (line 90-92)
  found: Generic `except Exception` catches _append_event_atomic failures, logs "Job queue error", sleeps, retries
  implication: Job queue worker appears to crash but actually keeps retrying. The real failure is in execute_run which calls _append_event_atomic first.

- timestamp: 2026-03-23T02:00
  checked: skill_converter.py line 22 and pyproject.toml dependencies
  found: skill_converter.py does `import frontmatter` (python-frontmatter package). Not in pyproject.toml dependencies. Package missing from venv.
  implication: Any skill execution via execute_run -> convert_skill fails with ModuleNotFoundError before the LLM call even happens

- timestamp: 2026-03-23T02:01
  checked: All 12 migration files with RLS statements
  found: Base.metadata.create_all creates tables but skips ALL op.execute() calls in migrations. This means: no app_user role, no GRANT statements, no ALTER TABLE ENABLE RLS, no CREATE POLICY statements. 12 migration files contain RLS setup for ~20 tables.
  implication: RLS is enabled on tables (SQLAlchemy model has it?) but no policies exist, so all INSERT/UPDATE/DELETE operations fail with InsufficientPrivilegeError

- timestamp: 2026-03-23T02:02
  checked: LiveCrawl.tsx line 65-67
  found: Counter shows "{crawlTotal} items found" immediately on mount, even when crawlTotal=0. No conditional to hide counter before first item arrives.
  implication: User sees "0 items found" with bouncing dots, which looks broken

- timestamp: 2026-03-23T03:00
  checked: skill_executor.py execute_run -> _execute_with_tools -> convert_skill code path
  found: execute_run calls _execute_with_tools for ALL skills. _execute_with_tools imports convert_skill which reads SKILL.md from ~/.claude/skills/{name}/SKILL.md. company-intel has NO SKILL.md file — it has a dedicated Python engine (engines/company_intel.py) that was never wired into the web execution path. The engine is not imported anywhere in the web app.
  implication: FileNotFoundError: "SKILL.md not found: /Users/sharan/.claude/skills/company-intel/SKILL.md" — the entire onboarding crawl fails

## Resolution

root_cause: |
  9 distinct issues across 3 rounds of testing:
  Round 1 (issues 1-5, already fixed):
  1. SQL cast syntax `::jsonb` conflicts with SQLAlchemy param binding in _append_event_atomic
  2. User model missing `supabase_uid` column referenced by anonymous_cleanup.py
  3. TenantSwitcher hits wrong endpoint (`/tenants` instead of `/user/tenants`)
  4. No GET /auth/api-key endpoint (only POST/DELETE exist)
  5. Job queue failures are a cascade from issue #1
  Round 2 (issues 6-8, already fixed):
  6. `python-frontmatter` package not in dependencies — skill_converter.py imports it
  7. Base.metadata.create_all skips ALL RLS policies from migrations — no policies, no role, no grants
  8. LiveCrawl shows "0 items found" before crawl starts
  Round 3 (issue 9, fixing now):
  9. execute_run routes ALL skills through _execute_with_tools -> convert_skill -> SKILL.md lookup.
     company-intel has no SKILL.md — it has a dedicated Python engine (engines/company_intel.py)
     that was never wired into the web execution path.

fix: |
  Issues 1-5: Already applied in previous session
  6. Added python-frontmatter to pyproject.toml dependencies (via `uv add`)
  7. Created scripts/apply_rls_policies.py — comprehensive script extracting all RLS from 12 migrations
  8. Added `crawlTotal > 0` conditional around counter in LiveCrawl.tsx
  9. Added ENGINE_SKILLS dispatch in execute_run and _execute_company_intel() async function that:
     - Calls crawl_company (async) directly
     - Calls structure_intelligence via asyncio.to_thread (sync LLM call)
     - Calls enrich_with_web_research via asyncio.to_thread (sync LLM + web search)
     - Writes to context store using async storage.append_entry with tenant-scoped sessions
     - Emits SSE stage events throughout for real-time progress
     - Returns (output, token_usage, tool_calls) matching _execute_with_tools interface

verification: |
  - python-frontmatter installs and imports successfully in venv
  - apply_rls_policies.py passes Python syntax check
  - LiveCrawl.tsx hides counter when crawlTotal=0, shows when >0
  - skill_executor.py passes Python syntax check
  - Manual E2E testing needed for full verification
files_changed:
  Round 1:
  - backend/src/flywheel/services/skill_executor.py (CAST instead of :: in _append_event_atomic)
  - backend/src/flywheel/services/anonymous_cleanup.py (removed User.supabase_uid reference)
  - backend/src/flywheel/api/tenant.py (added GET /tenants list endpoint)
  - backend/src/flywheel/api/auth.py (added GET /auth/api-key status endpoint)
  - backend/src/flywheel/api/chat.py (CAST instead of :: in events_log update)
  - backend/src/flywheel/api/graph.py (CAST instead of :: in settings update)
  Round 2:
  - backend/pyproject.toml (added python-frontmatter dependency)
  - backend/uv.lock (updated lockfile)
  - backend/scripts/apply_rls_policies.py (NEW: comprehensive RLS policy setup)
  - frontend/src/features/onboarding/components/LiveCrawl.tsx (hide counter when 0)
  Round 3:
  - backend/src/flywheel/services/skill_executor.py (ENGINE_SKILLS dispatch + _execute_company_intel)
