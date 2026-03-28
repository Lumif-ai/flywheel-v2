# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v3.0 — Intelligence Flywheel (Phases 59–63)

## Current Position

Phase: 60 of 63 (Meeting Data Model and Granola Adapter)
Plan: 1 of 3 in current phase
Status: In progress
Last activity: 2026-03-28 — Phase 60 Plan 01 complete: meetings table with split-visibility RLS and Meeting ORM model

Progress: [█████████████████░░░] 86% (32/42 total plans complete across all milestones)

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
- [57-01 execution]: ContactItem uses created_at (not last_contacted_at) — backend does not expose last_contacted_at; use for "Added X ago" display in PeopleTab
- [57-01 execution]: signalByType helper reads from useSignals() data — avoids prop drilling signal counts through sidebar tree
- [57-01 execution]: Placeholder RelationshipListPage/RelationshipDetail components registered in Plan 01 so routes work immediately — Plans 02/03 replace them
- [57-02 execution]: RelationshipCard uses BrandedCard variant='action' (coral left border) when signal_count > 0, 'info' otherwise — consistent with pipeline urgency styling
- [57-02 execution]: TYPE_CONFIG object maps RelationshipType to label/icon/emptyDescription — single source of truth, avoids scattered switch statements
- [57-02 execution]: sortByUrgency() sorts client-side by signal_count desc then last_interaction_at desc (nulls last) — no extra server round trip
- [57-03 execution]: TAB_CONFIG defined at module level outside component — single authoritative constant for tab sets per type; prevents recreation on every render
- [57-03 execution]: fromType URL param is CRITICAL source of truth — never derive tab config or back-link from account.relationship_type (account may belong to multiple types)
- [57-03 execution]: AI panel placeholder is dashed border div with comment "AskPanel slot — replaced in Plan 05"; tab content placeholders have "Coming soon..." and comment for Plan 04
- [57-04 execution]: lookupValue does two passes (direct key match then case-insensitive scan) — JSONB intel keys may use any casing depending on how notes were processed
- [57-04 execution]: CommitmentsTab always renders two-column structure even when empty — column headers provide UI affordance before data exists
- [57-04 execution]: RelationshipDetail uses explicit TabsContent per tab key (not map) — ensures Intelligence content never renders for advisor/investor types
- [57-04 execution]: ACTION_CONFIG Record<RelationshipType, ActionConfig[]> drives type-specific action bar — single source of truth for quick actions per relationship type
- [57-05 execution]: lastAnswer is ephemeral (most recent Q&A only, lost on unmount) — stateless per locked design decision from research
- [57-05 execution]: onSuccess/onError callbacks passed directly into mutate() call (not on hook definition) so mode resets correctly per submission
- [57-05 execution]: Auto-resize textarea capped at 6 rows via scrollHeight comparison in useEffect
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
- [58-01 execution]: DOCUMENT_FILE_PREFIX constant defined inside _execute_company_intel (not module-level) — only used there, avoids namespace pollution
- [58-01 execution]: is_document flag drives source_label ("document-upload" vs "website-crawl") and gates companies cache upsert (skipped for document-only inputs — no domain)
- [58-01 execution]: Supplementary doc fetch failures logged as warnings (not errors) — partial supplementary data preferable to aborting run
- [58-01 execution]: enrich_with_web_research max_uses reduced from 5 to 3 when existing_profile_keys count > half of total profile files (saves API credits on refresh)
- [58-02 execution]: enrichment_status field retained on CompanyProfileResponse but hardcoded to None — avoids frontend breakage while removing all enrichment logic
- [58-02 execution]: refresh_profile called directly (not via HTTP) from reset_profile — keeps db session shared, avoids double commit overhead
- [58-02 execution]: profile_linked flag auto-set in analyze-document before SkillRun creation — ensures file appears in subsequent refresh aggregation without a separate upload call
- [58-03 execution]: useProfileRefresh is a separate hook from useProfileCrawl — decoupled per research recommendation, avoids God hook
- [58-03 execution]: startFromRunId() accepts caller-provided run_id and only sets SSE URL — DocumentAnalyzePanel owns the POST, hook owns only SSE
- [58-03 execution]: useSSE already appends token internally — SSE URL in useProfileRefresh is plain path without ?token= suffix to avoid double-appending
- [58-03 execution]: 'discovery' event type added to sse.ts SSEEventType union — skills/runs stream sends discovery events; original type list only had text/stage/done/error/crawl_error
- [59-01 execution]: integrations table RLS policy name is 'integrations_tenant_isolation' (not 'tenant_isolation') — must use exact name in any future policy DROP/replace operations on this table
- [59-01 execution]: user_isolation policy uses nullable pattern (user_id IS NULL OR user_id = current_setting(...)) for work_items and skill_runs — NULL user_id rows are tenant-shared system items
- [59-01 execution]: email_scores and email_drafts own no user_id column — user isolation enforced via subquery: email_id IN (SELECT id FROM emails WHERE user_id = current_setting('app.user_id', true)::uuid)
- [Phase 59]: Return 404 (not 403) on ownership mismatches — avoids leaking resource existence to potential attackers
- [Phase 59]: user.sub (not user.id) used for all user_id comparisons — TokenPayload exposes .sub as the UUID field
- [Phase 59]: Both base and count_q in list_runs() get user_id filter — ensures pagination totals stay accurate
- [60-01 execution]: Split-visibility RLS uses 2 policies (tenant_read FOR SELECT + owner_write FOR ALL) — cleaner than 4 per-operation policies; tenant members can read meeting metadata, only owner can write
- [60-01 execution]: current_setting('app.tenant_id', true) with missing_ok=true on meetings table — consistent with 031_user_level_rls pattern
- [60-01 execution]: idx_meetings_dedup partial unique index WHERE external_id IS NOT NULL — allows multiple manual-upload rows (NULL external_id) while preventing duplicate synced records

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 56]: RESOLVED — AG Grid themeQuartz.withParams() with CSS custom properties works cleanly with Tailwind v4 (no CSS imports needed)
- [Phase 57]: RESOLVED — AskPanel implemented with 4-mode state machine, dual-mode input, source citations — no spike needed

## Session Continuity

Last session: 2026-03-28
Stopped at: Completed 60-01-PLAN.md — meetings table + ORM model; ready for Phase 60 Plan 02 (Granola adapter)
Resume file: None
