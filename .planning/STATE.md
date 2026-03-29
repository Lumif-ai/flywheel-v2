# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-29)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** Email-to-tasks extraction pipeline

## Current Position

Milestone: v1.0 CRM Redesign — Intelligence-First Relationships
Phase: 68-email-to-tasks (Email to Tasks)
Current Plan: 3 of 3
Status: Phase 68 complete — all plans done

Progress: [████████████████████] 100% — Phase 68: 3/3 plans complete

## Performance Metrics

**Velocity (v2.0):**
- Total plans completed: 9 (v2.0 milestone)
- Average duration: ~3 min/plan
- Phase 50: 2 plans, 8 min total
- Phase 51: 1 plan, 7 min
- Phase 52: 3 plans, 6 min total
- Phase 53: 3 plans, 9 min total

**Previous milestone (v1.0 Email Copilot):**
- Phases: 6 core + 3 patches (48, 49, 49.1)
- Average plan duration: ~4.5 min

## Accumulated Context

### Decisions

All v1.0-v4.0 decisions archived in milestone ROADMAP archives.
See: .planning/milestones/v4.0-ROADMAP.md for full history.

- 68-01: resolution_source_id has no FK (polymorphic reference to email or meeting)
- 68-01: All new task columns nullable for backwards-compatibility
- 68-02: Used 'completed' (not 'complete') for SkillRun status in last_ritual_at query -- matches actual DB values
- 68-02: No existing entity-to-account helper; implemented _resolve_entity_to_account from scratch
- 68-02: Extractor is pure data function; all SSE emission handled by ritual wrapper only
- 68-03: Detected Tasks section placed between Processing and Prep sections (Section 2.5)
- 68-03: Source badge color-coded pills (email=blue, slack=green, other=gray)
- 68-03: resolved_by validates against {user, system} enum set
- 67-01: UUIDs typed as string in TypeScript (JSON-serialized from backend)
- 67-01: 30s stale time for task queries (frequent changes during triage)
- 67-01: Optimistic removal from filtered list on status transition
- 67-02: TaskTriageCard uses plain div (not BrandedCard) for lightweight triage cards
- 67-02: Exit animations via CSS class toggle + 150ms setTimeout (more reliable than onTransitionEnd)
- 67-03: Account name from task.metadata.account_name (denormalized by backend)
- 67-03: Follow-up creation tracked in component-local Set state (session-level only)
- 67-04: Sheet component with showCloseButton=false for custom header layout in detail panel
- 67-04: Description auto-saves on blur with 500ms debounce (not keystroke)
- 67-04: Quick-add account field uses plain text input (no API search) for V1
- 67-05: Focus mode uses Zustand for ephemeral UI state, React Query for task data/mutations
- 67-05: Card exit animations use CSS class toggle + 250ms setTimeout with directional transforms
- 67-05: Focus trap via Tab key interception rather than external library
- 67-06: Widget uses shared React Query cache (no extra API calls for briefing)
- 67-06: Keyboard nav uses data-task-id DOM querying across section components
- 67-06: Widget shows confirm/dismiss only (no "later") for compact form
- 67-07: Reused existing useSSE hook for skill execution streaming (no polling fallback needed)
- 67-07: Search debounce via useEffect+setTimeout (no new dependencies)
- 67-07: Stagger animations reuse existing animationClasses.fadeSlideUp from animations.ts

### Pending Todos

- Tasks UI frontend (backend API exists at /tasks with 7 endpoints, no frontend — identified during v4.0 dogfooding)
- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)
- Granola created_after date format fixed (seconds + Z suffix) — verify sync works post-fix

### Blockers/Concerns

None active.

### Roadmap Evolution

All v1.0-v4.0 roadmap evolution archived. Clean slate for next milestone.

## Session Continuity

Last session: 2026-03-30
Stopped at: Completed 68-03-PLAN.md (Brief Integration + Task API) — Phase 68 complete
Resume file: None
