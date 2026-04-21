---
phase: 153-prompt-normalization-schema
plan: 01
subsystem: api
tags: [regex, mcp, prompt-normalization, fastapi, skill-serving]

# Dependency graph
requires: []
provides:
  - "normalize_for_mcp() function with 4-pass serve-time prompt normalization"
  - "?mode=mcp query param on GET /skills/{name}/prompt endpoint"
  - "MCP client always requests normalized prompts via mode=mcp"
affects: [153-02, 153-03, skill-serving, mcp-client]

# Tech tracking
tech-stack:
  added: []
  patterns: ["serve-time normalization via query param gating", "longest-match-first regex replacement with word-boundary anchors"]

key-files:
  created:
    - backend/src/flywheel/services/prompt_normalizer.py
  modified:
    - backend/src/flywheel/api/skills.py
    - cli/flywheel_mcp/api_client.py
    - cli/flywheel_mcp/server.py

key-decisions:
  - "4-pass ordering: prefix strip -> MCP tool map -> native capability map -> doc-block replacement"
  - "Word-boundary anchored regex prevents partial matches (e.g. context_read inside flywheel_read_context)"
  - "Longest-key-first sorting prevents substring collisions in replacement maps"

patterns-established:
  - "Serve-time normalization: raw prompts stored unchanged, normalized on read via query param"
  - "Mode gating: ?mode=mcp triggers normalization, absent mode returns raw (backward compat)"

# Metrics
duration: 8min
completed: 2026-04-21
---

# Phase 153 Plan 01: Prompt Normalization + MCP Endpoint Summary

**4-pass serve-time prompt normalizer with ?mode=mcp gating on skill prompt endpoint, 12 MCP tool renames + 7 native capability mappings + prefix strip + doc-block replacement**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-21T15:04:10Z
- **Completed:** 2026-04-21T15:12:20Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments
- Created prompt_normalizer.py with normalize_for_mcp() implementing 4 ordered passes: mcp__flywheel__ prefix strip, 12 MCP tool name mappings, 7 native capability mappings, and Available Tools doc-block replacement
- Wired normalizer into GET /skills/{name}/prompt with ?mode=mcp query param -- raw prompts unchanged without mode param (backward compatible)
- Updated MCP client (api_client.py) to accept mode param, and MCP server (server.py) to always pass mode="mcp"

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `9129a2d` (feat)

## Files Created/Modified
- `backend/src/flywheel/services/prompt_normalizer.py` - 4-pass normalize_for_mcp() with static mapping dicts and pre-compiled regexes
- `backend/src/flywheel/api/skills.py` - Added mode Query param, normalize_for_mcp import, conditional normalization before return
- `cli/flywheel_mcp/api_client.py` - Added mode param to fetch_skill_prompt(), appends ?mode={mode} to URL
- `cli/flywheel_mcp/server.py` - flywheel_fetch_skill_prompt always passes mode="mcp" to client

## Decisions Made
- Used pre-compiled regex patterns at module level for performance (compiled once, reused per request)
- Sorted replacement keys longest-first to prevent substring collisions
- Protected skills still return orchestrator stub regardless of mode (normalization only applies to non-protected prompts)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- prompt_normalizer.py ready for Plan 02 (unit tests) to validate all edge cases
- Plan 03 (schema registry) can reference the normalization patterns established here

---
*Phase: 153-prompt-normalization-schema*
*Completed: 2026-04-21*
