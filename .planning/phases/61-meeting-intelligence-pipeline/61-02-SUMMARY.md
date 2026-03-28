---
phase: 61-meeting-intelligence-pipeline
plan: 02
subsystem: api
tags: [meetings, accounts, crm, domain-matching, prospect-creation]

# Dependency graph
requires:
  - phase: 61-01
    provides: _execute_meeting_processor() 7-stage pipeline with Stage 5 placeholder

provides:
  - auto_link_meeting_to_account() — domain-match attendees to existing accounts with free email exclusion
  - auto_create_prospect() — dedup-safe prospect account creation with all required NOT NULL fields
  - upsert_account_contacts() — email-based dedup contact upsert for matched accounts
  - Stage 5 of _execute_meeting_processor() wired to real auto-linking (no more placeholder)

affects: [62-meeting-intelligence-frontend, relationships-surfaces, pipeline-grid, signal-badges]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Free email provider exclusion list (frozenset) in constants — checked before any domain-based account creation
    - Mail subdomain stripping (_MAIL_SUBDOMAINS) — normalize mail.acme.com -> acme.com before matching
    - Dedup-before-create pattern — Account.normalized_name check before auto_create_prospect insert
    - Most-contacts tie-breaking — when multiple domain matches exist, pick account with most AccountContacts

key-files:
  created: []
  modified:
    - backend/src/flywheel/engines/meeting_processor_web.py
    - backend/src/flywheel/services/skill_executor.py

key-decisions:
  - "FREE_EMAIL_DOMAINS frozenset defined at module level — never auto-create accounts for gmail/yahoo/hotmail/outlook/icloud/protonmail/aol/live/msn/me"
  - "auto_link_meeting_to_account returns first created prospect when multiple external domains have no match — caller gets one canonical account_id"
  - "Stage 5 preserves existing_account_id when already set — manual account assignments are never overridden by auto-linking"
  - "upsert_account_contacts checks (tenant_id, account_id, email) triple — prevents duplicate contacts from re-processing same meeting"
  - "_normalize_domain strips mail./email./smtp./mx./www. prefixes before matching — ensures mail.acme.com matches acme.com account"

patterns-established:
  - "auto_create_prospect includes status='prospect', relationship_type=['prospect'], relationship_status='new', pipeline_stage='identified' — minimum viable Account for pipeline grid display"
  - "Stage 5 logs at INFO when existing account preserved, auto-linked, or no match — full audit trail in run logs"

# Metrics
duration: 4min
completed: 2026-03-28
---

# Phase 61 Plan 02: Account Auto-Linking for Meeting Intelligence Summary

**Domain-match attendee emails to existing CRM accounts, auto-create prospect accounts for unknown external domains, and upsert attendees as AccountContact rows — wiring Stage 5 of the 7-stage meeting pipeline.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-28T04:02:11Z
- **Completed:** 2026-03-28T04:06:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added three auto-linking helpers to `meeting_processor_web.py`: `auto_link_meeting_to_account` (domain query + free-email exclusion + multi-match tie-breaking), `auto_create_prospect` (dedup-safe Account creation with all NOT NULL fields), `upsert_account_contacts` (email-keyed dedup)
- Replaced Stage 5 placeholder in `_execute_meeting_processor()` with real auto-linking — `account_id` now flows from a real domain match (or prospect creation) through to Stage 6 (ContextEntry rows) and Stage 7 (meeting.account_id)
- Free email provider exclusion prevents auto-creating junk accounts for gmail/yahoo/outlook attendees; mail subdomain normalization ensures mail.acme.com matches accounts with domain=acme.com

## Task Commits

Plan-level commit (commit_strategy=per-plan):

1. **Tasks 1+2: account auto-linking helpers + Stage 5 wiring** - `321ade1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/src/flywheel/engines/meeting_processor_web.py` — Added `FREE_EMAIL_DOMAINS`, `_MAIL_SUBDOMAINS`, `_normalize_domain()`, `_extract_external_domains()`, `upsert_account_contacts()`, `auto_create_prospect()`, `auto_link_meeting_to_account()`; updated module docstring and imports
- `backend/src/flywheel/services/skill_executor.py` — Replaced Stage 5 placeholder; added `auto_link_meeting_to_account` and `upsert_account_contacts` to local imports; updated Stage 5 docstring

## Decisions Made

- `FREE_EMAIL_DOMAINS` defined as a module-level frozenset constant — checked in `_extract_external_domains()` so both auto-linking and prospect creation always apply the same exclusion list
- `auto_link_meeting_to_account` returns the first created prospect when multiple external domains exist with no existing accounts — gives the pipeline one canonical account_id rather than requiring the caller to handle multiple
- Stage 5 preserves `existing_account_id` (already set on the meeting row) — manual account assignments are never overridden by auto-discovery
- `upsert_account_contacts` deduplicates on `(tenant_id, account_id, email)` — safe to re-process the same meeting without creating duplicate contact rows
- When multiple domain matches exist, tie-break by AccountContact count (most contacts = most engaged account) via `outerjoin + group_by + order_by count desc`

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The venv at `backend/.venv` uses Python 3.12, verified before running import checks (system Python 3.9 does not support `str | None` union syntax used in models).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Stage 5 now produces real account_ids — meetings are no longer orphaned from CRM accounts
- ContextEntry rows written in Stage 6 now carry account_id when a match is found
- meeting.account_id set in Stage 7 — relationship surface and signal badge phases can read this directly
- Plan 03 (meeting list API + frontend) can now display linked account names alongside processed meetings

## Self-Check: PASSED

All files confirmed present. Commit 321ade1 verified in git log.

---
*Phase: 61-meeting-intelligence-pipeline*
*Completed: 2026-03-28*
