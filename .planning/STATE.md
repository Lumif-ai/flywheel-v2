# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v2.1 — Phase 56: Pipeline Grid

## Current Position

Phase: 56 of 57 (Pipeline Grid)
Plan: 3 of 3 in current phase
Status: Phase complete
Last activity: 2026-03-27 — Phase 56 Plan 03 complete (filter bar, view tabs, graduation modal, stale/reply row styling, pagination)

Progress: [███████████████░░░░░] 80% (21/26 total plans complete across all milestones)

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
- [56-01 execution]: badge-translucent provides shared pill shape only; individual badge rgba colors applied via inline styles to avoid combinatorial CSS class explosion
- [56-01 execution]: Register pattern: pipeline=--page-bg (cool white), relationship=--brand-tint-warm, personal=--brand-tint-warmest — drives page background switching
- [56-02 execution]: AG Grid theming uses themeQuartz.withParams() only — no CSS imports from ag-grid-community/styles/ (prevents Tailwind v4 conflict)
- [56-02 execution]: Cell renderers always wrap content in flex items-center h-full div for proper vertical centering in 56px rows
- [56-02 execution]: GraduateButton reads onGraduate from AG Grid context prop (props.context.onGraduate) — decoupled from modal logic; Plan 03 replaces console.log stub
- [56-02 execution]: localStorage key format established: flywheel:{page}:{stateType} (e.g., flywheel:pipeline:columnState)
- [56-02 execution]: Pipeline endpoint now accepts fit_tier and outreach_status query params — filters applied at SQL level for accurate total count
- [56-03 execution]: Comma-separated array param serialization — frontend sends fit_tier=Excellent,Strong; backend _expand() splits on commas; supports both repeated params and comma-separated
- [56-03 execution]: Stale tab (>14 days) uses client-side filter on already-loaded data — days_since_last_outreach already in each row, no extra server round trip
- [56-03 execution]: Entity level auto-detection in GraduationModal — only advisor/investor selected => person, otherwise company
- [56-03 execution]: Count query LEFT JOINs last_status_sq subquery so outreach_status filter applies correctly and pagination totals stay accurate
- [56-03 execution]: AG Grid getRowStyle used for stale/replied/graduating row styles — avoids Tailwind v4 CSS class conflicts
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
Stopped at: Phase 56 Plan 03 complete — Phase 56 fully done, ready for Phase 57 (RelationshipDetail)
Resume file: None
