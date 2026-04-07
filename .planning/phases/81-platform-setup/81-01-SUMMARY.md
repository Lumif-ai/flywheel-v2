---
phase: 81-platform-setup
plan: 01
subsystem: infra
tags: [claude-md, mcp, integration-rules, template]

# Dependency graph
requires:
  - phase: 79-mcp-tools
    provides: "13 MCP tools (read/write context, skill discovery, save document/meeting)"
provides:
  - "CLAUDE.md template with context routing, skill discovery, and output saving rules"
affects: [82-install-script, onboarding]

# Tech tracking
tech-stack:
  added: []
  patterns: ["CLAUDE.md integration template for MCP tool routing"]

key-files:
  created: [cli/flywheel_mcp/templates/CLAUDE.md]
  modified: []

key-decisions:
  - "30-line template (well under 60 max) -- concise enough for high compliance"
  - "Static markdown, no variables or interpolation -- every founder gets same rules"
  - "flywheel_run_skill excluded from template (cron/scheduled path only)"

patterns-established:
  - "CLAUDE.md template pattern: imperative tone, bullet points, exact tool names in backticks"
  - "Three-section structure: Context Store, Skill Discovery, Output"

# Metrics
duration: 1min
completed: 2026-03-30
---

# Phase 81 Plan 01: CLAUDE.md Template Summary

**30-line CLAUDE.md template with context routing, skill-first lookup, and output saving rules referencing 6 MCP tools**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-30T18:09:37Z
- **Completed:** 2026-03-30T18:10:30Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created CLAUDE.md template at cli/flywheel_mcp/templates/CLAUDE.md
- Three rule sections: context routing (business intel -> flywheel_write_context with read-before-write), skill discovery (flywheel_fetch_skills -> flywheel_fetch_skill_prompt -> execute), output saving (flywheel_save_document + flywheel_save_meeting_summary)
- All 6 required MCP tool names referenced; flywheel_run_skill correctly excluded
- 30 lines with imperative tone and concrete business intel examples

## Task Commits

1. **Task 1: Create templates directory and CLAUDE.md template** - `c3b6332` (feat)

## Files Created/Modified
- `cli/flywheel_mcp/templates/CLAUDE.md` - Integration rules template for founders' CLAUDE.md

## Decisions Made
- Kept template to 30 lines (well under 60 max) for high CLAUDE.md compliance
- Used research-recommended content structure verbatim -- no deviations needed
- flywheel_run_skill excluded per plan (interactive path uses fetch_skill_prompt)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CLAUDE.md template ready for manual copy into founder projects
- Future install script (Phase 82+) can read from cli/flywheel_mcp/templates/CLAUDE.md

---
*Phase: 81-platform-setup*
*Completed: 2026-03-30*
