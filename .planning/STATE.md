# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v12.0 Library Redesign

## Current Position

Milestone: v12.0 Library Redesign
Phase: 104.1 of 104.1 (Legacy Model Cleanup)
Plan: 3 of 5 complete
Status: Executing Phase 104.1 plans
Last activity: 2026-04-09 — Plan 03 complete (signals.py + synthesis_engine.py rewired to pipeline models)

Progress: [██████____] 60% (3/5 plans in Phase 104.1)

## Performance Metrics

**Previous milestones:**
- v1.0: 6 core phases + 3 patches
- v2.0: 4 phases, 9 plans
- v2.1: 5 phases, 16 plans
- v3.0: 5 phases, 13 plans
- v4.0: 4 phases, 13 plans
- v5.0: 1 phase, 7 plans
- v6.0: 1 phase, 3 plans
- v7.0: 7 phases, 13 plans
- v8.0: 7 phases, 14 plans
- v9.0: 8 phases, 25 plans
- v10.0: 5 phases, 7 plans
- v11.0: 5 phases, 10 plans

## Accumulated Context

### Decisions

All v1.0-v11.0 decisions archived in PROJECT.md Key Decisions table and previous STATE.md snapshots.

v12.0 design decisions (from design brief):
- Three filtering axes: type tabs (automatic), company dropdown (automatic), tag pills (user-defined escape hatch)
- Flat time-grouped list, not company-grouped sections (Norman: three-level nesting causes cognitive overload)
- Fix titles at write time (skills generate readable titles) + migration for existing bad titles
- Fix dedup at write time (same title + type + account within 1 hour = update) + migration for existing dupes
- Account resolution Option C: skills create Account first, pass both account_id + company_name
- Tag validation: max 20/doc, 200 unique/tenant, 50 chars, lowercase alphanumeric+hyphens
- PgBouncer DDL constraint: each migration statement via SQL Editor, not Alembic transactions
- Backend must complete before frontend (API dependency)
- Skill ecosystem updates are last (backward-compatible params mean existing skills keep working)

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

### Roadmap Evolution

- v12.0 roadmap created: Phases 101-104
- Phase 104.1 inserted after Phase 104: Legacy Model Cleanup — rewire 9 backend files from Account/AccountContact/OutreachActivity to PipelineEntry/Contact/Activity (URGENT)
- 104.1-02: outreach.py and timeline.py confirmed dead (no frontend callers), deleted entirely (735 lines removed)
- 104.1-02: Dead frontend accounts/ components noted for future cleanup (not in scope)
- 104.1-01: Used TIMESTAMP(timezone=True) for ai_summary_updated_at to match existing PipelineEntry column convention
- 104.1-03: Reply signal uses direction=inbound + status=completed (Activity has no 'replied' status); pipeline partition: retired_at IS NULL AND stage NOT IN ('identified')

## Session Continuity

Last session: 2026-04-09
Stopped at: Completed 104.1-03-PLAN.md (signals + synthesis engine rewire)
Resume file: None
