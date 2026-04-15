# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Conversations automatically become tracked commitments and executed deliverables -- the founder's daily operating system
**Current focus:** v19.0 Broker Redesign -- Phase 133 Foundation

## Current Position

Milestone: v19.0 Broker Redesign
Phase: 133 of 139 (Foundation)
Plan: 3 of 3 in current phase
Status: Phase 133 complete
Last activity: 2026-04-15 -- Completed 133-03 shared grid components

Progress: [█░░░░░░░░░] 17% (4/23 plans)

## Performance Metrics

**Previous milestones:**
- v15.0 Broker Module MVP: 8 phases, 25 plans
- v16.0 Briefing Intelligence Surface: 2 phases, 4 plans
- v17.0 Broker Frontend: 7 phases, 16 plans
- v18.0 Broker Data Model v2: 4 phases, 11 plans

## Accumulated Context

### Decisions

All v1.0-v18.0 decisions archived in PROJECT.md Key Decisions table.

**v19.0 Execution Decisions:**
- Cell renderers follow StatusBadge pattern: ICellRendererParams, flex h-full wrapper, em-dash for null
- CarrierCell uses deterministic hash-to-palette color mapping (no per-carrier config needed)
- ai_critical_finding computed at serialization time via optional param, not stored column

**v19.0 Architecture Decisions (from brainstorm 2026-04-15):**
- Claude Code is intelligence layer, backend is data layer, frontend is presentation layer
- Skills call backend API endpoints (no local script copies of gap detection/comparison)
- Portal auto-fill uses deterministic Playwright scripts per carrier (not AI)
- Hooks auto-trigger gap_detector after coverage writes, quote_comparator after quote writes
- ag-grid stays -- theme with Linear x Airbnb x Lumif.ai blend
- Comparison matrix uses ag-grid with fullWidthRow (Community-compatible, no Enterprise)
- Two pipeline commands + 9 individual step commands
- Hooks need pipeline-mode sentinel to prevent redundant API calls
- Comparison matrix needs 1-day prototype gate before full build
- Type removal must be ordered: add new types BEFORE removing old
- Every component must match visual spec from day one

### Pending Todos

- v18.0 Phase 132-03 awaiting final verify (committed at 387291a)
- Title matching false positives in _filter_unprepped (deferred from 66.1)
- Private import coupling in flywheel_ritual.py (tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-15
Stopped at: Completed 133-01-PLAN.md (backend coverage serializer + new endpoints)
Resume file: None
