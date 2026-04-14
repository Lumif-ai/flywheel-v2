# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v17.0 Broker Frontend MVP — Phase 122 (Shared Module Toolkit)

## Current Position

Milestone: v17.0 Broker Frontend MVP
Phase: 123 of 128 (Backend New Endpoints)
Plan: 2 of 2 (complete)
Status: Phase 123 Complete
Last activity: 2026-04-14 — dashboard-tasks + export-comparison endpoints added

Progress: [██░░░░░░░░] 14%

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
- v12.0: 6 phases (4 + 2 inserted)
- v14.0: 2 phases, 4 plans
- v15.0: 8 phases, 25 plans
- v16.0: 2 phases, 4 plans

## Accumulated Context

### Decisions

All v1.0-v16.0 decisions archived in PROJECT.md Key Decisions table.

v17.0:
- Shared module toolkit over module-specific code — extract ag-grid theme, cell renderers, column persistence to shared locations
- Custom HTML table for comparison matrix — two-row cells + multi-sticky don't fit ag-grid model; use CSS Grid or native table
- Gate strip goes in layout.tsx not per-page — prevents mount/unmount flicker and duplicate polling
- Excel export must use run_in_executor — openpyxl is synchronous, would block FastAPI event loop
- Dashboard tasks concatenated by priority (review > approve > export > followup), not re-sorted
- Followup tasks are per-carrier-quote for carrier-level overdue visibility
- CoverageTable migration must preserve is_manual_override business logic
- No separate Clients page — client profile lives on project Overview tab
- Consolidate /broker/settings/carriers into /broker/carriers
- Zero new dependencies — entire stack already installed
- Three separate queries for gate-counts over UNION — clarity and independent filterability
- exists() subquery for approve gate — check pending carrier drafts without loading rows

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-14
Stopped at: Completed 123-02-PLAN.md — Phase 123 complete, all backend endpoints done
Resume file: None
