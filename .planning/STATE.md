# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v2.1 — Phase 55: Relationships and Signals APIs

## Current Position

Phase: 55 of 57 (Relationships and Signals APIs)
Plan: 3 of 3 in current phase — PHASE COMPLETE
Status: In progress
Last activity: 2026-03-27 — Phase 55 Plan 03 complete (RAPI-05/06 notes+files endpoints, SIG-01/02 signals badge count API)

Progress: [█████████████░░░░░░░] 69% (18/26 total plans complete across all milestones)

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
- [55-01 execution]: graduated_at partition predicate (Account.graduated_at.isnot(None)) must appear on every relationships read/write endpoint — POST /graduate is the only intentional exception (targets un-graduated accounts)
- [55-01 execution]: _graduate_account() sets graduated_at = now so both auto-graduation (reply trigger) and manual graduation always timestamp the event
- [55-03 execution]: httpx used for Supabase Storage upload (not supabase-py) — matches existing document_storage.py pattern; file content read before upload for size validation
- [55-03 execution]: Signal queries are 4 separate queries per type (not window functions) — simpler to extend, graduated_at.isnot(None) in base_filters on every query
- [55-02 execution]: enforce_rate_limit() MUST be called before generate() in POST /synthesize — rate limit fires before any LLM call even when ai_summary is NULL
- [55-02 execution]: Sparse data in generate() still updates ai_summary_updated_at = now — prevents rapid re-attempts on thin accounts; ask() has no rate limit (stateless)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 56]: AG Grid CSS variable theming against Tailwind v4 Vite plugin architecture untested in this codebase — plan a 1-hour spike before committing to theming approach
- [Phase 57]: AskPanel conversational UI is highest-complexity component in milestone — consider focused implementation spike before building

## Session Continuity

Last session: 2026-03-27
Stopped at: Phase 55 fully complete (Plans 01-03) — ready for Phase 56 (Frontend Pipeline + Relationships)
Resume file: None
