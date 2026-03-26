# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Founders never lose track of an account again — single screen with all contacts, timeline, commitments, intel, next actions, all auto-populated from skill runs
**Current focus:** Milestone v2.0 — Phase 50: Data Model and Utilities

## Current Position

Phase: 50 of 53 (Data Model and Utilities)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-03-26 — 50-02 complete: CRM ORM models + normalize_company_name utility

Progress: [██░░░░░░░░] 20% (v2.0 milestone)

## Performance Metrics

**Velocity (v2.0):**
- Total plans completed: 2 (this milestone)
- Phase 50, Plan 01: 2 min (1 task, 1 file)
- Phase 50, Plan 02: 6 min (2 tasks, 4 files)

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

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-26
Stopped at: Completed 50-02-PLAN.md — CRM ORM models + normalize_company_name utility (85b0df9)
Resume file: None
