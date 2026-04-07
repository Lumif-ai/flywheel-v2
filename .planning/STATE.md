# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-07)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v10.0 Contact Outreach Pipeline — Phase 94 (MCP Contact Tools)

## Current Position

Milestone: v10.0 Contact Outreach Pipeline
Phase: 94 of 94 (MCP Contact Tools) -- COMPLETE
Plan: 1 of 1 (done)
Status: Phase 94 complete -- v10.0 Contact Outreach Pipeline milestone finished
Last activity: 2026-04-07 — Phase 94 executed (MCP contact listing + outreach step tools)

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

## Accumulated Context

### Decisions

All v1.0-v9.0 decisions archived in PROJECT.md Key Decisions table.

v10.0 design decisions:
- Person-first grid as default view (company toggle secondary) — JTBD is always person-level for outreach
- Grid is command center (scan+filter+select), detail panel is editing surface (messages, fields, actions)
- Sequences are emergent (activities sorted by step_number), not configured (no sequence builder UI)
- AI-computed next_step derived from activity status + elapsed time (not manually maintained)
- Claude Code sends emails via Playwright, not in-app send buttons — grid is visibility, not execution
- No auto-send without approval — founder reviews and approves every step
- Post-query filtering for status/channel on latest activity (avoids lateral join complexity)
- compute_next_step as pure function outside PipelineService for testability
- SingleSelectFilter for all contact filters (backend accepts single-value params)
- AgGridReact key={mode} forces remount on mode switch for clean column/sort state
- Contact row click navigates to parent company profile (detail panel deferred to Phase 93)
- Hooks invalidate both ['contacts'] and ['contact-activities'] query keys for grid/panel sync
- Activity mutation success toast only on status changes to avoid noise
- Contact panel 480px width (wider than company panel 420px) for textarea editing comfort
- EditableField: click-to-edit with blur-save, pencil icon on hover
- Action buttons contextual to status: Approve for drafted, Skip for drafted/approved, Mark Replied for sent
- MCP outreach tools are ID-based (not name-based) for batch workflows: list returns IDs, create accepts IDs

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 3 | Pipeline grid UX: merge Name+Domain, outreach status column, expandable detail rows | 2026-04-07 | 26428ae | [3-pipeline-grid-ux-fixes](./quick/3-pipeline-grid-ux-fixes-merge-name-domain/) |

## Session Continuity

Last session: 2026-04-07
Stopped at: Completed 094-01-PLAN.md (MCP contact tools) -- milestone v10.0 complete
Resume file: None
