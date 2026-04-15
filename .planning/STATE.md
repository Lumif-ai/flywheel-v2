# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Conversations automatically become tracked commitments and executed deliverables -- the founder's daily operating system
**Current focus:** v19.0 Broker Redesign -- Phase 134 Skills Infrastructure

## Current Position

Milestone: v19.0 Broker Redesign
Phase: 135 of 139 (AI Skills)
Plan: 1 of 4 in current phase
Status: Plan 135-01 complete
Last activity: 2026-04-15 -- Completed 135-01 api_client extensions + parse-contract, parse-policies, gap-analysis step skills

Progress: [██░░░░░░░░] 26% (6/23 plans)

## Performance Metrics

**Previous milestones:**
- v15.0 Broker Module MVP: 8 phases, 25 plans
- v16.0 Briefing Intelligence Surface: 2 phases, 4 plans
- v17.0 Broker Frontend: 7 phases, 16 plans
- v18.0 Broker Data Model v2: 4 phases, 11 plans

## Accumulated Context

### Decisions

All v1.0-v18.0 decisions archived in PROJECT.md Key Decisions table.

**v19.0 Execution Decisions:**
- Cell renderers follow StatusBadge pattern: ICellRendererParams, flex h-full wrapper, em-dash for null
- CarrierCell uses deterministic hash-to-palette color mapping (no per-carrier config needed)
- ai_critical_finding computed at serialization time via optional param, not stored column

**v19.0 Architecture Decisions (from brainstorm 2026-04-15):**
- Claude Code is intelligence layer, backend is data layer, frontend is presentation layer
- Skills call backend API endpoints (no local script copies of gap detection/comparison)
- Portal auto-fill uses deterministic Playwright scripts per carrier (not AI)
- Hooks auto-trigger gap_detector after coverage writes, quote_comparator after quote writes
- ag-grid stays -- theme with Linear x Airbnb x Lumif.ai blend
- Comparison matrix uses ag-grid with fullWidthRow (Community-compatible, no Enterprise)
- Two pipeline commands + 9 individual step commands
- Hooks need pipeline-mode sentinel to prevent redundant API calls
- Comparison matrix needs 1-day prototype gate before full build
- Type removal must be ordered: add new types BEFORE removing old
- Every component must match visual spec from day one
- [Phase 133]: Used transitional type cast pattern (QuoteWithLegacyDraft) for safe field removal during migration
- [Phase 134-01]: FLYWHEEL_API_TOKEN is broker's session JWT (not service key); documented token acquisition steps in SKILL.md
- [Phase 134-01]: /broker:analyze-gaps and /broker:compare-quotes are STUB entries (Phase 135); marked NOT YET IMPLEMENTED in dispatch table
- [Phase 134-01]: api_client.py validates FLYWHEEL_API_TOKEN at _headers() call time (module-level read, RuntimeError on empty)
- [Phase 134-02]: safe_fill/safe_select use per-field try/except — one broken selector cannot abort the entire fill run
- [Phase 134-02]: mapfre.yaml selectors are PLACEHOLDER_* until live portal DevTools calibration
- [Phase 134-02]: fill_portal() never calls page.click() on submit/confirm — broker always submits manually
- [Phase 134-02]: New carrier pattern = {carrier}.py + {carrier}.yaml in portals/ directory
- [Phase 134-03]: broker_auth_helper.py uses underscore filename for Python importability; hooks use hyphens per Claude hook convention
- [Phase 134-03]: Stop hook outputs additionalContext only when BROKER_PIPELINE_MODE=1 still active; does not block stopping
- [Phase 134-03]: PostToolUse hooks detect writes by regex on tool_input command string (lightweight, no extra API calls)
- [Phase 134-03]: settings.json hook registration uses Python atomic read-modify-write preserving all 9 existing hooks
- [Phase 135-01]: upload_file() re-reads FLYWHEEL_API_TOKEN at call time (not module-level) so tests can set env var after import
- [Phase 135-01]: upload_file() skips _headers() to avoid Content-Type override — httpx sets multipart boundary automatically
- [Phase 135-01]: parse-policies uses inline Claude reading of pdfplumber output rather than API call

### Pending Todos

- v18.0 Phase 132-03 awaiting final verify (committed at 387291a)
- Title matching false positives in _filter_unprepped (deferred from 66.1)
- Private import coupling in flywheel_ritual.py (tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-15
Stopped at: Completed 135-01-PLAN.md (api_client extensions + 3 step skills in ~/.claude/skills/broker/steps/)
Resume file: None
