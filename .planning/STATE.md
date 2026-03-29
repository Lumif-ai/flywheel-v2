# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-28)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** Milestone v4.0 — Flywheel OS (Phases 64–66)

## Current Position

Phase: 66 of 66 (Flywheel Ritual — Rearchitect)
Plan: 3 of 4 in current phase (Plan 03 complete)
Status: Executing Phase 66 rearchitect plans
Last activity: 2026-03-29 — Phase 66 Plan 03: Stage 4 LLM-powered task execution

Progress: [████████████████████] 100% (42/42 plans complete across v1.0-v3.0) | v4.0: 11/12 plans

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
- [60-02 execution]: GRANOLA_API_BASE = https://public-api.granola.ai/v1 — real URL; spec assumed api.granola.ai (incorrect)
- [60-02 execution]: test_connection uses GET /v1/notes?page_size=1 — no /v1/me endpoint exists in Granola API
- [60-02 execution]: list_meetings reads 'notes' key from response (not 'meetings'); maps item["id"]->external_id, item["created_at"]->meeting_date, item.get("summary_text")->ai_summary
- [60-02 execution]: Upsert on reconnect clears last_synced_at = None — forces full re-sync from scratch on API key change
- [60-02 execution]: connect endpoint does NOT store last_sync_cursor in settings — Integration.last_synced_at column is the sync cursor
- [60-03 execution]: Processing rules sourced from integration.settings["processing_rules"] dict — avoids a separate config table; tenant-configurable via JSONB settings column
- [60-03 execution]: already_seen count is len(existing_ids) — built during dedup step, no extra DB query
- [60-03 execution]: _apply_processing_rules() returns "pending" or "skipped" only — exhaustive, no third state
- [61-01 execution]: Sync Anthropic SDK wrapped in run_in_executor — avoids blocking event loop while keeping simple SDK usage
- [61-01 execution]: Stage 5 (account linking) is a deliberate placeholder — Plan 02 replaces with auto_link_meeting_to_account
- [61-01 execution]: write_context_entries deduplicates on (file_name, source, detail, tenant_id) — safe to re-run without duplicate context entries
- [61-01 execution]: classify_meeting Layer 2 skipped entirely when tenant.domain IS NULL — logged at DEBUG level (not error)
- [61-02 execution]: FREE_EMAIL_DOMAINS frozenset at module level in meeting_processor_web.py — never auto-create accounts for gmail/yahoo/hotmail/outlook/icloud/protonmail/aol/live/msn/me
- [61-02 execution]: auto_link_meeting_to_account returns first created prospect when multiple external domains have no match — one canonical account_id per meeting run
- [61-02 execution]: Stage 5 preserves existing_account_id when already set on meeting row — manual account assignments are never overridden by auto-discovery
- [61-02 execution]: upsert_account_contacts deduplicates on (tenant_id, account_id, email) — safe to re-process same meeting without creating duplicate contact rows
- [61-02 execution]: Multi-match tie-breaking uses outerjoin + group_by + count(AccountContact.id) desc — most-contacts account wins when multiple domains match
- [61-03 execution]: apply_post_classification_rules lives in meeting_processor_web.py (not api/meetings.py) — avoids circular import; skill_executor imports from engine layer
- [61-03 execution]: skip_internal defaults to True when key absent — matches MPP-05 spec (internal-only meetings skip by default)
- [61-03 execution]: granola_list_meetings alias in meetings.py — avoids collision between granola_adapter.list_meetings import and new GET / endpoint function
- [61-03 execution]: Post-classification skip preserves meeting_type classification even when status becomes "skipped" — type analytics remain accurate
- [62-02 execution]: Client-side filter checks provider=granola AND status=connected — a disconnected row may remain in DB from prior connection
- [62-02 execution]: syncMutation calls POST /meetings/sync (not /integrations/{id}/sync) — meetings endpoint returns synced/skipped/already_seen stats for user feedback
- [62-03 execution]: Meeting rows serialized as inline dicts (not via _serialize_timeline_item) — direction set directly as "bidirectional" since Meeting doesn't share ContextEntry interface
- [62-03 execution]: INTEL_FILES excludes "contacts" — contact data surfaces via AccountContact/PeopleTab, not IntelligenceTab
- [62-03 execution]: Intel gap-fill uses file_name.replace("-", "_") key transformation — aligns with frontend lookupValue() two-pass scan (pain_points matches 'pain' case-insensitive)
- [62-03 execution]: attendees JSONB field on Meeting is list/dict — len(m.attendees or []) used safely for contact_name attendee count
- [63-01 execution]: Account-ID: prefix in SkillRun.input_text is the dispatch discriminator — is_account_meeting_prep checked BEFORE is_meeting_prep; onboarding path completely untouched
- [63-01 execution]: PREP_CONTEXT_FILES includes "contacts" (8 total: 7 intel files + contacts) — needed for Contacts & Stakeholders briefing section
- [63-01 execution]: Empty context guard returns friendly HTML via "done" event (not "error") — frontend can render without special-casing empty state
- [63-01 execution]: Meeting import in _execute_account_meeting_prep is local (not module-level) — matches _execute_meeting_processor pattern; avoids circular import risk
- [63-02 execution]: MeetingDetail type has no account_name field — "this account" fallback passed to PrepBriefingPanel; backend resolves name from DB
- [63-02 execution]: PrepBriefingPanel does NOT reuse MeetingPrepRenderer — different prop interface; renders dangerouslySetInnerHTML directly in styled container
- [63-02 execution]: done event handler checks rendered_html then output keys for compatibility with different SkillRun response shapes
- [64-01 execution]: calendar_event_id used for dedup (not external_id prefix pattern) -- cleaner partial unique index
- [64-01 execution]: Granola data wins over calendar data -- skip calendar update if existing row has granola_note_id (richer source preserved)
- [64-01 execution]: Fuzzy dedup uses OR of title-contains and attendee-overlap (not AND) -- maximizes match rate between calendar and Granola
- [64-01 execution]: get_meeting_prep_suggestions kept on WorkItem for now -- Plan 02 migrates it to query Meeting table
- [64-02 execution]: processing_status param renamed from 'status' to avoid shadowing fastapi.status import -- no frontend breakage (param was not yet consumed)
- [64-02 execution]: prep_meeting commits meeting.account_id to DB before SkillRun creation -- ensures account link persists regardless of downstream failure
- [64-02 execution]: Suggestions response uses meeting_id key (not work_item_id) and adds account_id field -- frontend prep triggering uses these directly
- [64-03 execution]: ScheduledPrepSection delegates to PrepBriefingPanel when account_id exists -- reuses existing component for steady state after prep
- [64-03 execution]: PrepTrigger uses useMutation + useState for stream_url handoff -- immediate transition from button to streaming (no blank intermediate)
- [64-03 execution]: ProcessingFeedback extended to recorded status -- recorded meetings are processable just like pending

- [65-01 execution]: User-level RLS (tasks_user_isolation) for tasks — NOT split-visibility; tasks are personal per research anti-pattern
- [65-01 execution]: Separate _task_signals_cache keyed by tenant_id:user_id — avoids cold cache per-user on tenant-scoped _signals_cache
- [65-01 execution]: Removed early return in get_signals() — restructured into Step A (relationship cache)/Step B (task cache)/Step C (merge) so task counts always run
- [Phase 65]: Summary endpoint defined before /{task_id} to avoid FastAPI path parameter conflict
- [Phase 65]: Soft-delete via status=dismissed preserves audit trail; completed_at cleared on reopen (dismissed->detected)
- [Phase 65]: [65-02 execution]: Email tasks forced to trust_level='confirm' via post-processing enforcement -- defense-in-depth; not relying solely on LLM prompt instruction
- [Phase 65]: [65-02 execution]: Task extraction is best-effort in pipeline -- wrapped in try/except so meeting processing continues even if Haiku call or JSON parsing fails
- [66-03 execution]: LLM formulation uses Haiku (cheap/fast) -- actual skill execution uses whatever model the skill needs
- [66-03 execution]: Task status transitions confirmed -> in_review (matching spec ORCH-12); VALID_TRANSITIONS updated in tasks.py
- [66-03 execution]: trust_level='confirm' tasks produce deliverables but engine does NOT auto-send -- founder reviews everything
- [66-03 execution]: Local imports for create_registry/RunContext/RunBudget inside _stage_4_execute -- matches existing pattern in skill_executor.py
- [Phase 65]: [65-02 execution]: extract_tasks receives both transcript AND Stage 4 extracted intelligence -- full context to Haiku without additional LLM cost

- [66-01 execution]: python3 for all JSON parsing in skills (not jq) -- avoids dependency; python3 guaranteed in project env
- [66-01 execution]: 401 from any API call stops all sections immediately -- token is dead, no point continuing to other sections
- [66-01 execution]: Outreach section shows "Not configured" for v1 -- CSV tracker is stretch goal; "Not configured" is acceptable default
- [66-02 execution]: [id:uuid] tags appended to displayed list items for position-to-UUID tracking -- prevents stale-position bugs on re-fetch
- [66-02 execution]: SSE parsing uses python3 inline (not jq) -- consistent with 66-01 convention
- [66-02 execution]: Prep defaults to external meetings only -- "prep all" overrides to include internal
- [66-01 rearchitect]: sync_granola_meetings opens its own session via factory() with RLS context -- fully self-contained for both API and engine use
- [66-01 rearchitect]: _find_matching_scheduled kept module-level with explicit session param (not nested) -- cleaner for testing and reuse
- [66-01 rearchitect]: HTTPException raised from inside sync function for API compatibility -- caller is always endpoint or engine
- [Phase 66]: Refactored flywheel ritual stages into private async functions for readability and testability
- [Phase 66]: NULL title meetings treated as unprepped without querying skill_runs -- prevents contains('') matching all completed preps

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 56]: RESOLVED — AG Grid themeQuartz.withParams() with CSS custom properties works cleanly with Tailwind v4 (no CSS imports needed)
- [Phase 57]: RESOLVED — AskPanel implemented with 4-mode state machine, dual-mode input, source citations — no spike needed

## Session Continuity

Last session: 2026-03-29
Stopped at: Completed 66-03-PLAN.md — Stage 4 LLM-powered task execution
Resume file: None
