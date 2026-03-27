---
phase: 59-team-privacy-foundation
plan: 02
subsystem: api
tags: [privacy, user-isolation, defense-in-depth, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 59-team-privacy-foundation/59-01
    provides: RLS policies on email, integrations, skill_runs tables at database level
provides:
  - API-layer user_id filters on all personal data endpoints (email, integrations, skill runs)
  - Defense-in-depth ownership checks for draft endpoints (approve/dismiss/edit)
  - PRIV-05, PRIV-06, PRIV-07 compliance
affects: [60-user-context-store, 61-skill-runner, any phase touching email/integrations/skills endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth: API-layer user_id filter + RLS DB-layer — double isolation for personal data"
    - "Draft ownership: load parent email, check email.user_id != user.sub, return 404 (not 403) to avoid leaking resource existence"
    - "Symmetric filter pattern: both base query AND count_q get user_id filter in paginated endpoints to prevent pagination math breakage"

key-files:
  created: []
  modified:
    - backend/src/flywheel/api/email.py
    - backend/src/flywheel/api/integrations.py
    - backend/src/flywheel/api/skills.py

key-decisions:
  - "Return 404 (not 403) on ownership mismatches — avoids leaking resource existence to potential attackers"
  - "user.sub (not user.id) used for all user_id comparisons — TokenPayload exposes .sub as the UUID field"
  - "stream_run() left unchanged — it uses get_tenant_session which sets app.user_id, and RLS (PRIV-04) handles enforcement"
  - "Both base and count_q in list_runs() get user_id filter — ensures pagination totals stay accurate (count and items both user-scoped)"

patterns-established:
  - "API-level user_id filter pattern: .where(Model.user_id == user.sub) on every personal data SELECT"
  - "Draft ownership pattern: load parent Email by draft.email_id, check email.user_id != user.sub, raise 404"

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 59 Plan 02: API-Layer User_id Defense-in-Depth Filters Summary

**Explicit user_id WHERE clauses added to 13 query locations across email, integrations, and skills endpoints — API-layer isolation complementing Plan 01's RLS policies**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T17:16:43Z
- **Completed:** 2026-03-28T17:19:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- email.py: 7 endpoints hardened — list_threads, get_thread, get_digest filter by Email.user_id; approve/dismiss/edit_draft verify parent email ownership; trigger_sync integration lookup scoped to user
- integrations.py: list_integrations, disconnect_integration, sync_integration all filter by Integration.user_id == user.sub
- skills.py: list_runs (base+count_q), get_run, get_run_attribution, get_run_trace all filter by SkillRun.user_id == user.sub — 5 query locations

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: email.py user_id filters (PRIV-05)** — included in `ba0185b`
2. **Task 2: integrations.py + skills.py filters (PRIV-06, PRIV-07)** — included in `ba0185b`

**Plan code commit:** `ba0185b` (feat(59-02): add user_id defense-in-depth filters to email, integrations, and skills APIs)

## Files Created/Modified
- `backend/src/flywheel/api/email.py` — Added Email.user_id==user.sub to list_threads/get_thread/get_digest; parent email ownership check to approve/dismiss/edit_draft; Integration.user_id filter to trigger_sync
- `backend/src/flywheel/api/integrations.py` — Added Integration.user_id==user.sub to list_integrations, disconnect_integration, sync_integration
- `backend/src/flywheel/api/skills.py` — Added SkillRun.user_id==user.sub to list_runs (both base and count_q), get_run, get_run_attribution, get_run_trace

## Decisions Made
- Returned 404 (not 403) on all ownership failures — plan specified this pattern explicitly to avoid leaking resource existence to potential attackers
- Used `user.sub` consistently (not `user.id`) — TokenPayload uses `.sub` as the UUID field for the authenticated user
- Left `stream_run()` unchanged — it already uses `get_tenant_session` which sets `app.user_id` and RLS handles enforcement; plan specified not to modify it
- Both `base` and `count_q` in `list_runs()` received user_id filters — prevents pagination math breakage where count would include all tenant runs but items are user-scoped

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- PRIV-05, PRIV-06, PRIV-07 complete — combined with Plan 01's RLS policies, user data is isolated at both database and application layers
- Phase 59 complete: all privacy foundation work done for team multi-user support
- Phase 60 (user context store) can proceed — its email/skill data access will correctly scope to the requesting user at both layers

---
*Phase: 59-team-privacy-foundation*
*Completed: 2026-03-28*
