# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Conversations automatically become tracked commitments and executed deliverables -- the founder's daily operating system
**Current focus:** v19.0 Broker Redesign -- Phase 134 Skills Infrastructure

## Current Position

Milestone: v19.0 Broker Redesign
Phase: 138 of 139 (Workflow Frontend B)
Plan: 3 of 4 in current phase
Status: Plan 138-03 complete — QuoteTracking redesigned with QUOT-01 through QUOT-05 (received/pending badges, carrier_type badge+premium, expandable rows, single RunInClaudeCodeButton, completion card)
Last activity: 2026-04-15 -- Completed 138-03: QuoteTracking redesigned, QUOT-01 through QUOT-05 satisfied (3380eda)

Progress: [███████░░░] 61% (14/23 plans)

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
- [Phase 133]: Used transitional type cast pattern (QuoteWithLegacyDraft) for safe field removal during migration
- [Phase 134-01]: FLYWHEEL_API_TOKEN is broker's session JWT (not service key); documented token acquisition steps in SKILL.md
- [Phase 134-01]: /broker:analyze-gaps and /broker:compare-quotes are STUB entries (Phase 135); marked NOT YET IMPLEMENTED in dispatch table
- [Phase 134-01]: api_client.py validates FLYWHEEL_API_TOKEN at _headers() call time (module-level read, RuntimeError on empty)
- [Phase 134-02]: safe_fill/safe_select use per-field try/except — one broken selector cannot abort the entire fill run
- [Phase 134-02]: mapfre.yaml selectors are PLACEHOLDER_* until live portal DevTools calibration
- [Phase 134-02]: fill_portal() never calls page.click() on submit/confirm — broker always submits manually
- [Phase 134-02]: New carrier pattern = {carrier}.py + {carrier}.yaml in portals/ directory
- [Phase 134-03]: broker_auth_helper.py uses underscore filename for Python importability; hooks use hyphens per Claude hook convention
- [Phase 134-03]: Stop hook outputs additionalContext only when BROKER_PIPELINE_MODE=1 still active; does not block stopping
- [Phase 134-03]: PostToolUse hooks detect writes by regex on tool_input command string (lightweight, no extra API calls)
- [Phase 134-03]: settings.json hook registration uses Python atomic read-modify-write preserving all 9 existing hooks
- [Phase 135-01]: upload_file() re-reads FLYWHEEL_API_TOKEN at call time (not module-level) so tests can set env var after import
- [Phase 135-01]: upload_file() skips _headers() to avoid Content-Type override — httpx sets multipart boundary automatically
- [Phase 135-01]: parse-policies uses inline Claude reading of pdfplumber output rather than API call
- [Phase 135-02]: fill-portal.md is a thin wrapper delegating all Playwright automation to portals/mapfre.py; no Playwright code duplicated
- [Phase 135-02]: draft-emails.md validates each carrier_config_id as UUID before calling the endpoint; rejects names with actionable error
- [Phase 135-02]: select-carriers.md prints email_carrier_config_ids in copy-paste format for handoff to /broker:draft-emails
- [Phase 135-03]: extract-quote does NOT create CarrierQuote rows — maps PDF to existing row only
- [Phase 135-03]: critical_exclusions explicitly surfaced in extract-quote output (cross-references MSA contract via quote_extractor.py)
- [Phase 135-03]: draft-recommendation pre-checks /comparison before confirming and posting — warns broker if data incomplete
- [Phase 135-03]: recipient_email normalized — blank input becomes None (backend accepts null)
- [Phase 135-04]: Pipeline files reference step skills via prompt references (not copy-paste) — single source of truth
- [Phase 135-04]: process-project deactivates BROKER_PIPELINE_MODE before draft-emails so audit hooks fire on email writes
- [Phase 135-04]: compare-quotes runs inline GET /comparison (not a separate step skill) — read-only synthesis
- [Phase 135-04]: /broker:analyze-gaps alias kept in router for backward compat with Phase 134 stub
- [Phase 136-01]: filterAttention state managed in BrokerDashboard (not grid) — passes computed status string to useBrokerProjects, keeps ProjectPipelineGrid a dumb display component
- [Phase 136-01]: Days Since Update uses valueGetter computing from updated_at — no new DB column needed
- [Phase 136-01]: MetricCard accent=true adds 3px coral left border; Needs Attention badge resets offset to 0 on toggle
- [Phase 136-02]: GridRow union type with isSectionHeader() guard for mixed ProjectCoverage + SectionHeaderRow data in ag-grid
- [Phase 136-02]: GapAmountCell uses gap_amount ?? required_limit for missing; gap_amount ?? (required_limit - current_limit) for insufficient
- [Phase 136-02]: ClauseLink color changed from blue to coral (#E94D35) to match brand accent
- [Phase 136-02]: domLayout=normal (not autoHeight) — autoHeight causes re-render storms with getRowStyle
- [Phase 136-03]: Spike decision — approved: ag-grid; fullWidthRow section headers confirmed Community-compatible
- [Phase 136-03]: ComparisonGrid interface narrowed — removed onToggleCarrier/showDifferencesOnly (HTML-table-specific props); ag-grid renders its own rows
- [Phase 136-03]: context={{ currency }} on AgGridReact propagates currency to inline cell renderers without colDef prop drilling
- [Phase 136-03]: CellWithLegacyFlags workaround removed — ComparisonQuoteCell flags are now proper typed optional fields
- [Phase 136-04]: CarrierCellRenderer unified renderer — checks props.node.rowPinned==='bottom'; pinnedBottomRowCellRenderer prop not in ag-grid-react API
- [Phase 136-04]: PDF mode uses static PdfPrintView (plain HTML table) — simpler than ag-grid print CSS, consistent recommended-carrier styling
- [Phase 136-04]: AI Insight card hidden when no is_recommended data available — avoids "Insufficient data" noise for older quotes
- [Phase 137-01]: useDocumentUpload is thin useMutation wrapper; cache invalidation uses broker-project queryKey
- [Phase 137-01]: DocumentEntry interface defined locally (both OverviewTab + DocumentUploadZone) — small, no need to centralize yet
- [Phase 137-01]: Drop zone uses native drag events (no react-dropzone) — sufficient for requirements
- [Phase 137-01]: broker_legacy.py kept in sync with projects.py MIME set (same 9 types)
- [Phase 137-02]: useAnalysisPolling shares queryKey ['broker-project', id] with useBrokerProject — TanStack deduplicates; no double network calls
- [Phase 137-02]: Full-width bypass uses activeTab conditional rendering (not CSS col-span-3) — sidebar simply not rendered for Analysis tab
- [Phase 137-02]: AnalysisTab is presentation-only; polling logic fully encapsulated in useAnalysisPolling hook
- [Phase 137-03]: RequirementsPanel owns all state rendering (running/failed/empty/populated); AnalysisTab right pane is a thin wrapper
- [Phase 137-03]: 60ms stagger applied via inline animationDelay (not staggerDelay() util which uses 50ms) — spec-mandated value
- [Phase 137-03]: WORKFLOW_STEPS edited as array literal directly (not .push()) to preserve as const typing
- [Phase 138-workflow-frontend-b]: domLayout=autoHeight for CarrierSelection (short table, not full-page)
- [Phase 138-workflow-frontend-b]: Routing Rule indicator is presence check on matched_coverages.length (not match_score which is removed per CARR-02)
- [Phase 138-03]: expandedQuoteId state lifted to QuoteTracking parent — allows single expansion at a time; per-row state would allow multi-expand
- [Phase 138-03]: allExtracted uses received+extracted statuses (not extracted-only) per QUOT-05 spec semantics

### Pending Todos

- v18.0 Phase 132-03 awaiting final verify (committed at 387291a)
- Title matching false positives in _filter_unprepped (deferred from 66.1)
- Private import coupling in flywheel_ritual.py (tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-15
Stopped at: Completed 138-03-PLAN.md (QuoteTracking redesigned — QUOT-01 through QUOT-05 satisfied)
Resume file: None
