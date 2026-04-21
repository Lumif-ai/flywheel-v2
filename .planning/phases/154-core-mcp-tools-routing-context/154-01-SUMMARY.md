---
phase: 154-core-mcp-tools-routing-context
plan: 01
subsystem: api
tags: [fastapi, mcp, skill-routing, token-overlap]

requires:
  - phase: 153-prompt-normalizer
    provides: normalize_for_mcp function for MCP tool-name rewriting
provides:
  - GET /api/v1/skills/route endpoint for intent-to-skill matching
  - _score_skill_match token-overlap scoring algorithm
  - _route_skills orchestrator with 0.6 confidence threshold
affects: [154-02, 154-03, mcp-tools, cc-skill-router]

tech-stack:
  added: []
  patterns: [token-overlap matching, confidence-threshold routing]

key-files:
  created: []
  modified: [backend/src/flywheel/api/skills.py]

key-decisions:
  - "0.6 confidence threshold separates match from candidates"
  - "Exact trigger substring match returns 1.0 (slash commands and natural language)"
  - "Multi-word trigger bonus +0.1 capped at 0.95 to prevent single-word domination"
  - "Route endpoint placed before /{skill_name}/prompt to avoid FastAPI greedy path matching"

patterns-established:
  - "Token-overlap scoring: exact substring -> 1.0, token overlap -> 0.8 max, description -> 0.3 max"
  - "Route endpoint returns MCP-normalized prompt for matched skills"

duration: 1min
completed: 2026-04-21
---

# Phase 154 Plan 01: Skill Routing Endpoint Summary

**Token-overlap intent-to-skill routing endpoint returning MCP-normalized prompts with 0.6 confidence threshold**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-21T15:32:51Z
- **Completed:** 2026-04-21T15:34:09Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Token-overlap scoring algorithm with exact substring, token overlap, and multi-word bonus
- GET /api/v1/skills/route endpoint that routes intents to cc_executable skills
- Confident matches return full MCP-normalized prompt; low-confidence returns top-3 candidates

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `be14f62` (feat: routing algorithm + endpoint)

## Files Created/Modified
- `backend/src/flywheel/api/skills.py` - Added _score_skill_match, _route_skills helpers and GET /route endpoint

## Decisions Made
- Used 0.6 as confidence threshold (plan-specified) -- balances precision vs recall
- Placed /route endpoint before /{skill_name}/prompt to avoid FastAPI greedy path parameter capture
- Only cc_executable=True skills considered for routing (non-CC skills filtered out)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Route endpoint ready for 154-02 (context warming) and 154-03 (MCP tool integration)
- Endpoint is tenant-scoped and auth-protected via require_tenant

---
*Phase: 154-core-mcp-tools-routing-context*
*Completed: 2026-04-21*
