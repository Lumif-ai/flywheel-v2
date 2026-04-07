---
phase: 79-mcp-tools
plan: 03
subsystem: api
tags: [mcp, tasks, accounts, crm, fuzzy-search, uuid]

requires:
  - phase: 79-01
    provides: "MCP server skeleton with FastMCP, InvocationLogger middleware, skill discovery tools"
provides:
  - "flywheel_fetch_tasks tool for actionable task retrieval with sort and filter"
  - "flywheel_fetch_account tool with UUID and fuzzy name search"
  - "_format_account_detail helper for structured account output"
affects: [79-04, morning-brief-skill, meeting-prep-skill, outreach-skill]

tech-stack:
  added: []
  patterns: ["UUID-first then name search for entity lookup", "client-side exclusion filter for multi-status"]

key-files:
  created: []
  modified: ["cli/flywheel_mcp/server.py"]

key-decisions:
  - "Client-side exclusion of done/dismissed tasks (backend only supports single-status filter)"
  - "UUID detection via stdlib uuid.UUID in local import inside function"
  - "Single match auto-fetches full detail; multiple matches return disambiguation list"

patterns-established:
  - "Entity lookup pattern: UUID-first, then fuzzy name search, then disambiguation"
  - "Task sorting: due_date ascending (nulls last), then priority (high > medium > low)"

duration: 1min
completed: 2026-03-30
---

# Phase 79 Plan 03: Task & Account Read Tools Summary

**flywheel_fetch_tasks and flywheel_fetch_account MCP tools with due-date/priority sorting, UUID/name lookup, and disambiguation**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-30T17:56:26Z
- **Completed:** 2026-03-30T17:57:45Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- flywheel_fetch_tasks returns actionable tasks (excludes done/dismissed), sorted by due date then priority, with all metadata for chaining
- flywheel_fetch_account resolves UUID identifiers directly and names via fuzzy search with auto-disambiguation
- _format_account_detail helper produces structured output with contacts and recent timeline

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Implement flywheel_fetch_tasks (MCP-05)** + **Task 2: Implement flywheel_fetch_account (MCP-06)** - `86b2f91` (feat)

## Files Created/Modified
- `cli/flywheel_mcp/server.py` - Added flywheel_fetch_tasks, _format_account_detail, flywheel_fetch_account (135 lines)

## Decisions Made
- Client-side exclusion of done/dismissed tasks since backend only supports single-status filter
- UUID detection via local import of uuid.UUID inside function body (matches codebase pattern)
- Single name match auto-fetches full detail; multiple matches return disambiguation list with IDs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 10 MCP tools now registered (3 original + 2 skill discovery + 3 meeting + 2 task/account)
- Plan 04 (action/write tools) can proceed with full read layer in place
- Task IDs and account IDs in output enable chaining to update/write tools

---
*Phase: 79-mcp-tools*
*Completed: 2026-03-30*
