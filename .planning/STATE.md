# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** v2.0 AI-Native CRM complete — next milestone TBD

## Current Position

Phase: 53 of 53 (Frontend) — MILESTONE v2.0 COMPLETE
Plan: All plans complete across all phases
Status: Milestone shipped
Last activity: 2026-03-27 — v2.0 AI-Native CRM milestone archived

Progress: [██████████] 100% (v2.0 milestone — shipped)

## Performance Metrics

**Velocity (v2.0):**
- Total plans completed: 8 (this milestone)
- Phase 50, Plan 01: 2 min (1 task, 1 file)
- Phase 50, Plan 02: 6 min (2 tasks, 4 files)
- Phase 51, Plan 01: 7 min (2 tasks, 4 files)
- Phase 52, Plan 01: 2 min (2 tasks, 2 files)
- Phase 52, Plan 02: 2 min (2 tasks, 2 files)
- Phase 52, Plan 03: 2 min (2 tasks, 2 files)
- Phase 53, Plan 01: 2 min (2 tasks, 6 files)
- Phase 53, Plan 02: 3 min (2 tasks, 9 files)
- Phase 53, Plan 03: 4 min (2 tasks, 11 files)

**Previous milestone (v1.0 Email Copilot):**
- Phases: 6 core + 3 patches (48, 49, 49.1)
- Average plan duration: ~4.5 min

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 init]: Company-first not person-first — B2B engagement is account-level
- [v2.0 init]: No manual data entry — accounts/contacts/outreach created by skills and seed commands only
- [v2.0 init]: Clean break migration — seed from existing GTM stack files
- [v2.0 init]: Pipeline and Accounts as separate surfaces — different JTBD (triage vs nurture)
- [v2.0 roadmap]: UTIL-01 placed in Phase 50 alongside data model — seed CLI (Phase 51) needs normalization before it can run
- [50-01]: RLS loop pattern used for CRM tables — iterate CRM_TABLES list, emit 4 policies per table
- [50-01]: UniqueConstraint on (tenant_id, normalized_name) for account deduplication
- [50-01]: context_entries.account_id is nullable FK with SET NULL — retrospective linking without hard requirement
- [50-02]: Two-phase suffix stripping in normalize_company_name — single pass before period removal, loop only after period removal to avoid over-stripping brand names like "Boston Consulting"
- [50-02]: _bare_suffixes check gated on period removal — "The Company" → "company" (no periods, check skipped), "Inc." → "" (period removed, check applied)
- [51-01]: SELECT-then-INSERT for contacts/activities (no unique constraint) instead of ON CONFLICT
- [51-01]: openpyxl added as explicit project dependency — was system-installed but absent from pyproject.toml
- [51-01]: In-memory dedup before DB calls reduces round trips on re-runs
- [Phase 52-backend-apis]: No-prefix router pattern for outreach endpoints spanning two URL groups
- [Phase 52-backend-apis]: _graduate_account() shared helper for consistent auto/manual graduation logic
- [52-01]: Correlated subquery for contact_count in account list query — avoids left join complexity when counting subquery already scoped
- [52-01]: 3-source timeline (outreach, context_entries, uploaded_files) merged in Python — simpler than UNION ALL with mismatched column shapes
- [52-01]: next_action_due accepted as ISO string in UpdateAccountRequest to simplify frontend integration
- [52-03]: Timeline v1 includes outreach + context entries only; UploadedFile has no account_id FK so documents deferred
- [52-03]: Pulse bump_suggested uses two-subquery approach (max sent_at + replied accounts) with outerjoin to find zero-reply stale prospects
- [52-03]: Timeline router declared without prefix — each path is self-contained to avoid collision with /accounts/ prefix router
- [53-01]: Simple HTML table with Tailwind — no table library needed for accounts list
- [53-01]: 300ms debounce on search to balance responsiveness with API call reduction
- [53-01]: Feature directory pattern: types/, hooks/, components/, api.ts at root
- [53-02]: Initial-then-paginate pattern for timeline — show embedded recent_timeline first, switch to paginated hook on load-more
- [53-02]: Known intel keys get human-readable labels, unknown keys rendered as generic key-value pairs
- [53-02]: ActionBar buttons show toast stubs — actual skill integration deferred to future phase
- [53-03]: PipelineParams cast to Record<string,unknown> for api.get compatibility
- [53-03]: PulseSignals self-contained component (fetches own data) rather than prop-driven
- [53-03]: Conditional Briefing sections gated on activeFocus name matching (revenue)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-27
Stopped at: Completed 53-02-PLAN.md — Account detail page with contacts, timeline, intel, action bar (7d1896e)
Resume file: None
