# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v17.0 Broker Frontend MVP — Phase 128 (Carriers Page Route Cleanup)

## Current Position

Milestone: v17.0 Broker Frontend MVP
Phase: 128.1 of 128.1 (Tenant Name Fix)
Plan: 1 of 1 (complete)
Status: Complete
Last activity: 2026-04-14 — Phase 128.1 Plan 01 complete (generic domain guard, tenant name resolution, sidebar branding)

Progress: [██████████] 100%

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
- Checkpoint auto-approved in autonomous mode when tsc + build pass — no human verification needed for compile-clean UI changes
- URL tab sync via useSearchParams with replace:true to avoid history pollution
- Thin tab wrapper pattern — tabs are pure import-and-render with projectId, no local state or data fetching
- Step indicator colors derived from project status progression order
- Back link navigates to /broker/projects not /broker dashboard
- ClientProfile uses getStr helper with fallback key arrays for flexible metadata schema
- Documents section casts metadata.documents as array with filter(Boolean) safety
- ConfidenceDot as local component in CoverageTab rather than shared -- small and coverage-specific
- Insurance/surety category split mirrors GapAnalysis.tsx logic for consistency
- Z-index layering for sticky table: z-30 corners, z-20 header/footer, z-10 first column
- Difference filter fallback: show all rows when filter would empty table
- Totals computed over full coverages list, not filtered subset
- Carrier filtering strips quotes from rows, not rows from table — empty cells visible
- At-least-one-carrier guard prevents deselecting all carriers
- Shared form extraction pattern: types + constants + conversion helpers + component in one file for cross-page reuse
- ag-grid action column callbacks via context prop with separate renderer component
- Clients redirect targets /broker/projects -- client profile lives on project Overview tab
- Email sidebar links to shared /email route, not broker-specific page
- Sidebar always shows "Flywheel" brand, not tenant name -- dropdown retains tenant names
- Generic domain guard applied to both promote and promote-oauth flows
- Company.name set to None for generic domains -- intel skill populates real name later
- Shared GENERIC_DOMAINS constant in flywheel.utils.domains replaces all inline domain lists

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Roadmap Evolution

- Phase 128.1 inserted after Phase 128: Tenant Name Fix — sidebar always "Flywheel", generic domain guard, company name resolution priority (URGENT)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-14
Stopped at: Completed 128.1-01-PLAN.md — generic domain guard, tenant name resolution, sidebar branding (Phase 128.1 complete)
Resume file: None
