---
phase: 157-desktop-integration
plan: 01
subsystem: cli
tags: [click, claude-desktop, mcp, json-config, rich]

requires:
  - phase: 152-retirement
    provides: setup-claude-code pattern and flywheel-mcp binary
provides:
  - "`flywheel desktop-setup` CLI command for Claude Desktop MCP registration"
  - "Desktop project instructions template at ~/.flywheel/desktop-project-instructions.md"
affects: [157-02, desktop-onboarding]

tech-stack:
  added: []
  patterns: ["Claude Desktop JSON config merge (read/preserve/write)"]

key-files:
  created: []
  modified:
    - cli/flywheel_cli/main.py

key-decisions:
  - "Used setdefault for mcpServers merge to preserve existing entries without overwriting"
  - "Granola uses npx mcp-remote for Desktop (Desktop cannot do HTTP MCP natively)"
  - "Non-blocking auth warning -- setup continues even if not logged in so config is ready"
  - "pbcopy clipboard attempt with silent fallback on non-macOS"

patterns-established:
  - "Desktop config merge: read JSON, setdefault mcpServers, write back with indent=2"
  - "DESKTOP_PROJECT_INSTRUCTIONS constant for template content (easy to update)"

duration: 2min
completed: 2026-04-21
---

# Phase 157 Plan 01: Desktop Setup Command Summary

**`flywheel desktop-setup` command that registers Flywheel + Granola MCP servers in Claude Desktop config and generates behavioral project instructions template**

## Performance

- **Duration:** 112s
- **Started:** 2026-04-21T16:44:21Z
- **Completed:** 2026-04-21T16:46:13Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `desktop-setup` Click command with 9-step flow: binary discovery, auth check, config read/merge/write, Granola entry, project instructions, clipboard copy, Rich summary panel
- Config merge preserves all existing mcpServers and non-MCP config (e.g. preferences)
- Project instructions template covers all required behavioral rules: flywheel_warm_context, flywheel_route_skill, flywheel_write_context, flywheel_read_context, flywheel_save_document, flywheel_save_meeting_summary

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Add desktop-setup Click command** + **Task 2: End-to-end verification** - `d252010` (feat)

## Files Created/Modified
- `cli/flywheel_cli/main.py` - Added desktop-setup command (+162 lines) with DESKTOP_PROJECT_INSTRUCTIONS constant and desktop_setup() function

## Decisions Made
- Used `setdefault("mcpServers", {})["flywheel"]` for safe merge preserving existing entries
- Granola uses `npx -y @anthropic/mcp-remote@latest` because Claude Desktop cannot do HTTP MCP natively (unlike Claude Code)
- Auth warning is non-blocking (yellow warning, not exit 1) so config is ready when user logs in later
- Added JSON decode error handling for corrupted existing config files
- Platform detection uses `platform.system()` with Linux rejection via ClickException

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added JSON decode error handling**
- **Found during:** Task 1 (config read/create)
- **Issue:** Plan did not specify handling for corrupted/invalid JSON in existing config file
- **Fix:** Added try/except JSONDecodeError with yellow warning, falls back to empty dict
- **Files modified:** cli/flywheel_cli/main.py
- **Verification:** Import and --help both succeed
- **Committed in:** d252010

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for robustness when config file exists but is invalid. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Desktop-setup command ready; Plan 02 (test suite) can proceed
- Command tested end-to-end on macOS with real config file

---
*Phase: 157-desktop-integration*
*Completed: 2026-04-21*
