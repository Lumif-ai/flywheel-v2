# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-11)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v15.0 Broker Module MVP — Phase 119 Broker API-Frontend Wiring Fixes

## Current Position

Milestone: v15.0 Broker Module MVP
Phase: 119 — Broker API-Frontend Wiring Fixes (Gap Closure)
Plan: 02 of 02 complete
Status: Complete
Last activity: 2026-04-13 — Completed 119-02 frontend wiring fixes

Progress: [##########] 100%

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

## Accumulated Context

### Decisions

All v1.0-v12.0 decisions archived in PROJECT.md Key Decisions table.

v13.0 Phase 105 Plan 01:
- WeasyPrint system deps in Dockerfile only -- no local uv sync required
- HTML sanitization at two points in export path (fragment wrapper + full-document body)
- asyncio.to_thread wraps both PDF and DOCX export

v13.0 Phase 105 Plan 02:
- output_config only applied when skill has explicit output_schema in parameters -- free-text skills unaffected
- output_schema extraction placed outside tool loop (invariant per execution)
- output_renderer structured_data pipeline confirmed already complete (no changes needed)

v13.0 Phase 110 Plan 01:
- read_context_file() default limit raised from 20 to 100 (backend max, fewer round-trips)
- Metadata filtering documented as client-side only; pre-Phase-110 entries have empty metadata dict

v13.0 Phase 111 Plan 01:
- meeting-intelligence skill load limit: 1000 entries per file (single call, warns if has_more=true)
- LLM model for synthesis: claude-opus-4-5 (not claude-3 — quality over cost for synthesis)
- Hair-on-fire threshold: >70% urgency language ratio
- Confidence thresholds: <10 EARLY SIGNAL, 10-25 EMERGING PATTERN, 25+ STRONG PATTERN
- Meeting count in entry content not evidence_count (prevents inflation on re-runs)

v13.0 Phase 111 Plan 02:
- Co-occurrence threshold: 2+ meetings (single-meeting pairs are noise)
- Alphabetical pair ordering (pain_a < pain_b) enforced for deterministic cluster upsert key
- Step 4 co-occurrence wrapped in try/except — cluster failure never loses Step 3 pain entries
- flywheel_save_document as MCP tool comment block (not Python code) — Claude Code executes at runtime
- V1 cluster naming: constituent slugs only, no descriptive names (deferred to V2)

v13.0 Phase 110 Plan 02:
- source and confidence promoted to explicit params in write_context() (backward compatible)
- metadata only added to POST body when non-None and non-empty (conditional inclusion)
- CLI path (context_utils.py) explicitly flagged as unable to carry metadata — FlywheelClient required for Phase 110+ writes

v13.0 pre-GSD context:
- Pre-GSD code exists for one-pager skill, export service, OnePagerRenderer — needs validation against research findings
- WeasyPrint NOT in pyproject.toml or Dockerfile — must fix before PDF export works
- export_as_pdf is sync — must wrap in asyncio.to_thread
- HTML sanitization gap in _wrap_fragment_as_document — XSS risk
- Anthropic SDK upgrade to >=0.93.0 needed for output_config structured outputs
- File upload backend ALREADY EXISTS (api/files.py, file_extraction.py, UploadedFile model)
- PII redaction belongs at export/share boundary, not pre-storage
- Archived pii-redactor script (560 lines) — port, don't rebuild
- No more hardcoded is_xyz branches in skill executor
- Legal doc advisor (Phase 107) ships MCP/CLI-first — user provides file path. Web file upload UI comes in Phase 108. No brainstorm needed — archived skill is v3.0 and mature. Phase 107 research defines the structured JSON schema.
- No phase reordering — 107 before 108 is correct

v15.0 Phase 112 Plan 01:
- ORM models follow exact PipelineEntry pattern (server_default, TIMESTAMP(timezone=True), Mapped annotations)
- BrokerActivity indexes use text() for DESC ordering in composite index
- All 6 tables include import_source per SPEC REQ-06; external_id/external_ref on carrier_configs and broker_projects only

v15.0 Phase 112 Plan 02:
- require_module uses get_db_unscoped (tenants table not RLS-scoped)
- broker feature flag derived at response time from modules array, not stored separately

v15.0 Phase 112 Plan 03:
- Broker nav item in own SidebarGroup after Pipeline (visually separated as module)
- broker=false added to COMPILE_TIME defaults (prevents accidental exposure to non-broker tenants)
- Shield icon chosen for broker identity in sidebar

v15.0 Phase 113 Plan 01:
- Adapted plan field names to actual model: name (not client_name/project_name), project_type (not contract_type)
- Single BrokerActivity per coverage update with updated_fields list in metadata (not one per field)
- Document refs stored in project metadata_ JSONB (documents array) for flexible schema

v15.0 Broker Module MVP:
- Broker module is a Flywheel feature, not a separate product — same codebase, same deployment, feature-flagged per tenant
- 6 new tables, 2 AI engines (contract_analyzer, quote_extractor), 2 business logic modules (gap_detector, quote_comparator)
- Playwright portal automation runs locally in broker's Claude Code instance (not server-side) — no credential storage
- Mandatory screenshot gate before portal form submission — no auto-submit
- AI extractions are starting points, broker always reviews — confidence scoring + mandatory review
- Single carrier portal for MVP (Mapfre Mexico), all others via email solicitation
- broker_migration.py handles Supabase PgBouncer DDL workaround (individual transactions per statement)
- Phase 112 recommended for Codex (pure mechanical), Phases 113-116 split Codex/Claude Code, Phase 117 Codex

v15.0 Phase 113 Plan 04:
- Native select element for contract type (no shadcn Select component in UI library)
- Simple HTML table for project list (not ag-grid) — faster initial build, sufficient for MVP
- KPI loading skeleton added (not in plan) for polish

v15.0 Phase 113 Plan 02:
- AI extraction fields mapped to ORM columns: limit_amount string -> required_limit Numeric, confidence_score float -> confidence text (high/medium/low)
- Raw extraction values preserved in metadata_ JSONB for audit trail
- Contract summary stored in project metadata_ JSONB (not a dedicated column)
- Detected language auto-updates project.language field

v15.0 Phase 113 Plan 03:
- Used tenant.settings.modules (not TenantModule table) for broker module check in Gmail sync
- Broker PDF detection creates draft BrokerProject (broker_project_id NOT NULL on BrokerActivity)
- PDF detection runs as post-sync pass fetching full messages only for broker tenants
- import_source/external_ref used (not source/source_ref) matching actual ORM columns

v15.0 Phase 113 Plan 05:
- Confidence displayed as text badge (high/medium/low) matching ORM string column, not numeric percentage
- Inline edit uses query invalidation on success (not optimistic update) for simplicity
- Used actual model field names (name, project_type) per Plan 04 decisions

v15.0 Phase 114 Plan 01:
- Reused existing _coverage_to_dict for ORM-to-dict conversion before gap detection (pure Python engine takes/returns dicts)
- Gap results persisted via ORM attribute assignment, not raw SQL, for consistency with existing broker.py patterns
- BrokerActivity metadata stores full summary dict for audit trail

v15.0 Phase 114 Plan 02:
- IntegrityError caught with explicit rollback before raising 409 (prevents session corruption)
- Carrier matching done in Python rather than complex SQL (simpler, testable, small carrier count per tenant)
- Match sort: (-match_score, avg_response_days or 999) for deterministic ordering

v15.0 Phase 114 Plan 03:
- Other-category coverages merged into Insurance Coverages section (not silently dropped)
- CarrierSelection visibility gated on project status (gaps_identified and later only)
- Carrier form uses comma-separated text for coverage_types/regions (MVP simplicity)
- Sonner toast for mutation feedback (consistent with rest of app)

v15.0 Phase 115 Plan 01:
- Draft columns on CarrierQuote (not EmailDraft) due to NOT NULL email_id FK constraint
- Sonnet model for solicitation drafting (cost-effective for email generation)
- Filename regex heuristics for document classification (simple, extensible)

v15.0 Phase 115 Plan 02:
- PII cleanup (null draft_body) after send matches email copilot approve pattern
- Status auto-update to "soliciting" only when ALL quotes solicited (REQ-38)
- Email validation via simple regex before draft generation (skip with reason if invalid)
- Portal track creates CarrierQuote with draft_status=null (no email draft needed)

v15.0 Phase 115 Plan 03:
- Optional Playwright import via try/except -- server never fails on missing dependency
- Dynamic carrier script loading via importlib -- extensible without code changes to engine
- Screenshot saved to /tmp with timestamp -- local artifact for review gate
- httpx for screenshot upload (also optional) -- no hard dependency on upload capability
- [Phase 115]: Portal quotes identified by null draft_subject + non-null carrier_config_id

v15.0 Phase 116 Plan 01:
- claude-opus-4-6 default for quote_extraction engine (quality over cost for financial data)
- Multi-coverage quotes create separate CarrierQuote rows per line item (shared hash prefix)
- Critical exclusion detection in both AI prompt AND comparator ranking logic

v15.0 Phase 116 Plan 03:
- refetchInterval on useBrokerQuotes polls every 10s only when any quote has status "extracting"
- ComparisonMatrix derives carrier columns dynamically from data (no hardcoded list)
- Needs follow-up status computed client-side (>7 days since solicited_at)

v15.0 Phase 118 Plan 01:
- Dashboard nav uses exact match (p === '/broker') to prevent false active on sub-routes
- Old single-item broker SidebarGroup removed — superseded by full content replacement ternary
- StreamSidebar placed inside GTM branch (broker tenants see zero GTM content)
- [Phase 119]: description field mapped from display_name (backward-compat: both keys present)
- [Phase 119]: Flat array returns for small collections (carriers, quotes) — no pagination wrapper

v15.0 Phase 119 Plan 02:
- editRecommendation returns RecommendationDraftResponse (same shape as draftRecommendation, not BrokerProject)
- sendRecommendation returns { status, sent_at, document_id } (unique shape from backend)
- CarrierSettings already handles flat array correctly -- no changes needed

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

v15.0 Phase 117 Plan 01:
- validate_transition uses late import in contract_analyzer.py (circular dependency avoidance)
- ALLOWED_TRANSITIONS: 11 states, recommended/delivered between quotes_complete and bound
- Terminal states (bound, cancelled) cannot transition further

v15.0 Phase 117 Plan 02:
- Sonnet model for recommendation drafting (cost-effective, same as solicitation drafter)
- 3000 max_tokens for recommendation (longer than solicitation due to comparison detail)
- Document saved to library with module="broker" and type="broker-recommendation"

v15.0 Phase 117 Plan 03:
- 3-state pattern (no-draft/pending/sent) mirrors EmailApproval but for recommendation
- Inline confirmation dialog instead of modal (lighter UX for single action)
- Warning banner when no recommended quotes exist (advisory, not blocking)

## Session Continuity

Last session: 2026-04-13
Stopped at: Completed 119-02-PLAN.md — Phase 119 complete, all broker wiring fixes done
Resume file: None
