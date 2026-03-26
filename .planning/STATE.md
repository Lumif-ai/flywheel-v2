# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v2.0 — Phase 52: Backend APIs

## Current Position

Phase: 52 of 53 (Backend APIs)
Plan: 2 of 3 in current phase (52-01 and 52-02 complete)
Status: In progress
Last activity: 2026-03-26 — 52-01 complete: Accounts and Contacts REST API — 8 endpoints (950950b); 52-02 complete: outreach API with AUTO-01 graduation and pipeline view (9df1119)

Progress: [███░░░░░░░] 30% (v2.0 milestone)

## Performance Metrics

**Velocity (v2.0):**
- Total plans completed: 3 (this milestone)
- Phase 50, Plan 01: 2 min (1 task, 1 file)
- Phase 50, Plan 02: 6 min (2 tasks, 4 files)
- Phase 51, Plan 01: 7 min (2 tasks, 4 files)
- Phase 52, Plan 01: 2 min (2 tasks, 2 files)
- Phase 52, Plan 02: 2 min (2 tasks, 2 files)

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

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-26
Stopped at: Completed 52-01-PLAN.md — Accounts and Contacts REST API 8 endpoints (950950b)
Resume file: None
