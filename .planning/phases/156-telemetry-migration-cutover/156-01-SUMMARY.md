---
phase: 156-telemetry-migration-cutover
plan: 01
subsystem: api, database, cli
tags: [telemetry, mcp, cc_executable, redirect, pgbouncer, alembic, sqlalchemy]

# Dependency graph
requires:
  - phase: 153-in-context-tool-normalization
    provides: "MCP tool normalization and cc_executable column on skill_definitions"
provides:
  - "skill_execution_telemetry table for tracking execution paths"
  - "POST /api/v1/skills/telemetry endpoint"
  - "MCP redirect for cc_executable skills in flywheel_run_skill"
  - "FlywheelClient.log_skill_telemetry fire-and-forget method"
affects: [156-02, migration-dashboards, skill-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns: ["fire-and-forget telemetry logging", "MCP redirect pattern for cc_executable skills"]

key-files:
  created:
    - backend/alembic/versions/067_skill_execution_telemetry.py
    - backend/scripts/apply_067_skill_execution_telemetry.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/api/skills.py
    - cli/flywheel_mcp/api_client.py
    - cli/flywheel_mcp/server.py

key-decisions:
  - "metadata_ column alias pattern (matching ContextAuditLog) for JSONB metadata column to avoid SQLAlchemy reserved name conflict"
  - "Telemetry wrapped in double try/except in MCP tool -- inner for log call, outer for entire cc_executable check -- ensures zero disruption"

patterns-established:
  - "Fire-and-forget telemetry: try/except pass around log calls, never blocking execution"
  - "MCP redirect pattern: check cc_executable flag, return REDIRECT message with instructions, fall through on any failure"

# Metrics
duration: 3min
completed: 2026-04-21
---

# Phase 156 Plan 01: Telemetry + MCP Redirect Summary

**skill_execution_telemetry table with PgBouncer-safe migration, POST /skills/telemetry endpoint, and MCP redirect for cc_executable skills in flywheel_run_skill**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-21T23:37:33Z
- **Completed:** 2026-04-21T23:40:40Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Telemetry table + ORM model + Alembic migration with PgBouncer-safe apply script
- POST /api/v1/skills/telemetry endpoint with execution_path validation
- MCP flywheel_run_skill now redirects cc_executable skills to in-context execution
- Both redirect and server-side paths log telemetry (fire-and-forget, never blocks)

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Telemetry table + ORM model + backend endpoint** - `69fa332` (feat)
2. **Task 2: MCP redirect logic + telemetry client method** - `69fa332` (feat)

## Files Created/Modified
- `backend/alembic/versions/067_skill_execution_telemetry.py` - Alembic migration with PgBouncer-safe DDL
- `backend/scripts/apply_067_skill_execution_telemetry.py` - Apply script with pre/post verification
- `backend/src/flywheel/db/models.py` - SkillExecutionTelemetry ORM model
- `backend/src/flywheel/api/skills.py` - SkillTelemetryRequest model + POST /skills/telemetry endpoint
- `cli/flywheel_mcp/api_client.py` - FlywheelClient.log_skill_telemetry method
- `cli/flywheel_mcp/server.py` - cc_executable redirect + server-side telemetry logging

## Decisions Made
- Used `metadata_` column alias (matching existing ContextAuditLog pattern) to avoid SQLAlchemy reserved name conflict with `metadata`
- Double try/except in MCP tool: inner for telemetry call, outer for entire cc_executable check -- ensures zero disruption on any failure path

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
Run the apply script against Supabase before using the telemetry endpoint:
```bash
cd backend && uv run python scripts/apply_067_skill_execution_telemetry.py
```

## Next Phase Readiness
- Telemetry infrastructure ready for 156-02 (feature flags + dashboards)
- cc_executable redirect active for any skill with the flag set to true
- Web UI path completely untouched

---
*Phase: 156-telemetry-migration-cutover*
*Completed: 2026-04-21*
