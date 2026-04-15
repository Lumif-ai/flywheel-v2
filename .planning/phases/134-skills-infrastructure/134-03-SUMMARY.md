---
phase: 134-skills-infrastructure
plan: "03"
subsystem: infra
tags: [hooks, claude-hooks, playwright, broker, pipeline, automation]

# Dependency graph
requires:
  - phase: 134-01
    provides: broker skill directory, api_client.py, FLYWHEEL_API_TOKEN auth pattern

provides:
  - broker-auth-helper.py shared utility (get_broker_context, is_broker_context, is_pipeline_mode)
  - broker-post-coverage-write.py PostToolUse hook (auto-triggers analyze-gaps)
  - broker-post-quote-write.py PostToolUse hook (auto-triggers comparison ranking)
  - broker-pipeline-check.py Stop hook (guards against infinite loop via stop_hook_active)
  - broker-pre-portal-validate.py PreToolUse hook (Playwright prereq check)
  - settings.json updated with all 4 hook registrations appended

affects: [134-broker-skills, 135-broker-endpoints, broker-pipeline, portal-scripts]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auth sentinel pattern: all hooks exit 0 silently when FLYWHEEL_API_URL or FLYWHEEL_API_TOKEN missing"
    - "Pipeline sentinel pattern: hooks check BROKER_PIPELINE_MODE=1 before firing to suppress redundant API calls"
    - "Stop hook infinite-loop guard: check stop_hook_active field before any additionalContext output"
    - "Absolute sys.path.insert for shared hook utility import (avoids relative import failures)"
    - "JSON stdout for PreToolUse deny decisions (exit 0 + JSON, not exit 2 + stderr)"

key-files:
  created:
    - ~/.claude/hooks/broker_auth_helper.py
    - ~/.claude/hooks/broker-post-coverage-write.py
    - ~/.claude/hooks/broker-post-quote-write.py
    - ~/.claude/hooks/broker-pipeline-check.py
    - ~/.claude/hooks/broker-pre-portal-validate.py
  modified:
    - ~/.claude/settings.json

key-decisions:
  - "broker_auth_helper.py uses underscore filename (broker_auth_helper) for Python importability, while the 4 hooks use hyphen filenames per Claude hook convention"
  - "Stop hook outputs additionalContext JSON only when BROKER_PIPELINE_MODE=1 is still active — it does not block stopping, only provides a reminder"
  - "PostToolUse hooks detect coverage/quote writes by regex-matching the Bash command string or serialized MCP tool_input — no DB query needed"
  - "settings.json hook registration uses Python atomic read-modify-write to preserve all 9 existing hooks (block-no-verify, security-deny, cost-verify, etc.)"

patterns-established:
  - "Broker hook sentinel chain: stop_hook_active check -> auth check -> pipeline mode check -> tool-specific logic"
  - "All broker hooks: import broker_auth_helper via sys.path.insert(0, expanduser('~/.claude/hooks'))"

# Metrics
duration: 12min
completed: 2026-04-15
---

# Phase 134 Plan 03: Broker Hooks Summary

**5 Claude hook files wiring automation layer: coverage writes auto-trigger gap analysis, quote writes auto-trigger comparison ranking, pipeline-check Stop hook guards infinite loop, and portal Playwright prereq validation**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-15T12:15:00Z
- **Completed:** 2026-04-15T12:27:39Z
- **Tasks:** 2
- **Files modified:** 6 (5 created in ~/.claude/hooks/, 1 updated ~/.claude/settings.json)

## Accomplishments
- Created shared `broker_auth_helper.py` utility with auth + pipeline mode sentinels used by all 4 hooks
- Implemented PostToolUse hooks for coverage writes (analyze-gaps trigger) and quote writes (comparison trigger) with Bash + MCP tool_input detection
- Implemented Stop hook with `stop_hook_active` infinite-loop guard and pipeline-mode reminder
- Implemented PreToolUse hook for Playwright prereq validation on portal scripts with JSON deny response
- Appended all 4 hook registrations to settings.json while preserving all 9 existing hooks

## Task Commits

Per-plan commit strategy — one commit covers all task work:
- All hook files in `~/.claude/hooks/` (outside flywheel-v2 git repo, not tracked)
- `~/.claude/settings.json` (outside flywheel-v2 git repo, not tracked)

Plan metadata committed to flywheel-v2 repo.

## Files Created/Modified
- `~/.claude/hooks/broker_auth_helper.py` - Shared utility: get_broker_context, is_broker_context, is_pipeline_mode
- `~/.claude/hooks/broker-post-coverage-write.py` - PostToolUse: detects /broker/projects/{id}/coverages POST, triggers analyze-gaps
- `~/.claude/hooks/broker-post-quote-write.py` - PostToolUse: detects /broker/projects/{id}/quotes POST, triggers comparison
- `~/.claude/hooks/broker-pipeline-check.py` - Stop hook: stop_hook_active guard + pipeline mode reminder
- `~/.claude/hooks/broker-pre-portal-validate.py` - PreToolUse: denies portal script execution if playwright not importable
- `~/.claude/settings.json` - Appended 2 PostToolUse + 1 PreToolUse + 1 Stop broker hook registrations

## Decisions Made
- `broker_auth_helper.py` uses underscore in filename for Python importability (`from broker_auth_helper import ...`), while the 4 hooks use hyphens per Claude convention
- Stop hook only adds `additionalContext` when pipeline mode is still active; does not block Claude from stopping
- PostToolUse hooks detect writes by regex on tool_input command string — lightweight, no extra API calls
- All hooks use `sys.path.insert(0, expanduser("~/.claude/hooks"))` for absolute path imports to avoid relative import failures in hook execution context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all hooks passed verification on first attempt.

## User Setup Required
None - hooks are wired via settings.json automatically. To activate broker hooks, set `FLYWHEEL_API_URL` and `FLYWHEEL_API_TOKEN` environment variables in the shell where Claude Code runs.

## Next Phase Readiness
- All 5 hook files functional and registered in settings.json
- Broker automation loop is complete: write coverage -> hook fires -> analyze-gaps called; write quote -> hook fires -> comparison called
- Phase 135 (broker API endpoints for analyze-gaps and compare-quotes) can proceed
- Portal scripts (Phase 136+) will have Playwright prereq validation automatically

---
*Phase: 134-skills-infrastructure*
*Completed: 2026-04-15*
