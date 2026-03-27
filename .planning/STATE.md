# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v2.1 — Phase 54: Data Model Foundation

## Current Position

Phase: 54 of 57 (Data Model Foundation)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-03-27 — Phase 54 Plan 02 complete (migration 029 + status rename Phase A)

Progress: [███████████░░░░░░░░░] 58% (15/26 total plans complete across all milestones)

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

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.1 research]: Two-phase migration mandatory for status→pipeline_stage rename — Phase A (add + copy) in Phase 54, Phase B (drop old column) deferred to post-stable-deploy
- [v2.1 research]: AI synthesis never auto-triggered on page load — NULL ai_summary returns NULL, not an LLM call; rate-limit at DB level (5-min window)
- [v2.1 research]: GIN index ships in same migration as relationship_type column — never as follow-up optimization
- [v2.1 research]: Partition predicate (graduated_at IS NOT NULL) defined once and enforced in both Pipeline and Relationships endpoints
- [v2.1 research]: fromType URL param drives tab config and back-link on shared RelationshipDetail page
- [v2.1 research]: Query key factory (queryKeys.ts) established in Phase 56 — graduation invalidates pipeline + relationships + signals simultaneously
- [v2.1 roadmap]: DS-01 through DS-04 placed in Phase 56 (first frontend phase) so Phase 57 inherits tokens without rework
- [54-01 execution]: Alembic revision IDs must be <=32 chars — alembic_version.version_num is varchar(32); use short IDs like 028_acct_ext not full descriptive names
- [54-01 execution]: ARRAY(Text) GIN indexes: always co-locate in same migration as column and replicate in ORM __table_args__
- [54-02 execution]: Two-phase zero-downtime rename pattern: add nullable → bulk UPDATE → set NOT NULL → Phase B (drop) deferred until post-stable-deploy
- [54-02 execution]: down_revision must reference the actual revision variable (e.g. 028_acct_ext), not the migration filename stem

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 56]: AG Grid CSS variable theming against Tailwind v4 Vite plugin architecture untested in this codebase — plan a 1-hour spike before committing to theming approach
- [Phase 57]: AskPanel conversational UI is highest-complexity component in milestone — consider focused implementation spike before building

## Session Continuity

Last session: 2026-03-27
Stopped at: Phase 54 Plan 02 complete — Phase 54 (Data Model Foundation) complete, ready for Phase 55 (Pipeline API)
Resume file: None
