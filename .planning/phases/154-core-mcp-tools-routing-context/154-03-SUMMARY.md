---
phase: 154-core-mcp-tools-routing-context
plan: 03
subsystem: api
tags: [mcp, skill-routing, context-store, fastmcp, httpx]

# Dependency graph
requires:
  - phase: 154-01
    provides: "GET /api/v1/skills/route backend endpoint"
  - phase: 154-02
    provides: "GET /api/v1/context/preamble backend endpoint"
provides:
  - "flywheel_route_skill MCP tool for intent-to-skill matching"
  - "flywheel_warm_context MCP tool for session context warming"
  - "FlywheelClient.route_skill() and FlywheelClient.get_context_preamble() methods"
affects: [mcp-server, skill-router, context-store, claude-code-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["MCP tool with fresh FlywheelClient per call, str return, dual error catch"]

key-files:
  created: []
  modified:
    - cli/flywheel_mcp/api_client.py
    - cli/flywheel_mcp/server.py

key-decisions:
  - "Placed tools between flywheel_fetch_skill_prompt and flywheel_fetch_skill_assets for logical grouping"
  - "Followed existing pattern exactly: output_schema=None, fresh FlywheelClient(), catch FlywheelAPIError + Exception"

patterns-established:
  - "Skill routing tool: format matched skill with name/description/confidence/prompt, or top-3 candidates"
  - "Context warming tool: catalog listing with +/- status icons, recent entries grouped by file"

# Metrics
duration: 1min
completed: 2026-04-21
---

# Phase 154 Plan 03: MCP Tool Wiring Summary

**flywheel_route_skill and flywheel_warm_context MCP tools wired to backend skill-route and context-preamble endpoints**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-21T15:36:15Z
- **Completed:** 2026-04-21T15:37:28Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `route_skill()` and `get_context_preamble()` thin client methods to FlywheelClient
- Added `flywheel_route_skill(intent)` MCP tool with matched-skill formatting and top-3 fallback
- Added `flywheel_warm_context()` MCP tool with catalog listing and recent entries grouped by file

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `78566d5` (feat: route_skill + get_context_preamble client methods, flywheel_route_skill + flywheel_warm_context MCP tools)

## Files Created/Modified
- `cli/flywheel_mcp/api_client.py` - Added route_skill() and get_context_preamble() methods after fetch_skill_prompt
- `cli/flywheel_mcp/server.py` - Added flywheel_route_skill and flywheel_warm_context @mcp.tool functions before flywheel_fetch_skill_assets

## Decisions Made
- Placed new client methods after fetch_skill_prompt and before the heavy fetch_skill_assets_bundle for logical grouping
- Placed new MCP tools in the Skill Discovery section, between flywheel_fetch_skill_prompt and flywheel_fetch_skill_assets
- Followed existing patterns exactly with no deviations from the established codebase conventions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both MCP tools are wired and ready for end-to-end testing once backend endpoints from 154-01 and 154-02 are deployed
- Phase 154 is now complete: all 3 plans (backend route, backend preamble, MCP wiring) delivered

---
*Phase: 154-core-mcp-tools-routing-context*
*Completed: 2026-04-21*

## Self-Check: PASSED
