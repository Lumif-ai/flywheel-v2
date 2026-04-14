---
phase: 131-backend-atomic-release
plan: "03"
subsystem: api
tags: [fastapi, sqlalchemy, broker, solicitations, recommendations, email-dispatch]

requires:
  - phase: 131-02
    provides: BrokerClientService, BrokerContactService, create_context_entity; SolicitationDraft and BrokerRecommendation ORM models
  - phase: 131-01
    provides: broker/ package scaffold with _shared.py validate_transition, ALLOWED_TRANSITIONS

provides:
  - solicitations.py — 5 endpoints covering the full SolicitationDraft lifecycle (list, create, edit, approve, approve-send)
  - recommendations.py — 3 endpoints covering BrokerRecommendation lifecycle (draft, edit, approve-send)
  - Both sub-routers included in main_router.py under /broker prefix
  - Carrier email sourced from carrier_contacts table (batch loaded, not N+1)
  - Body preserved after solicitation send (WRK-08 PII retention)
  - Approve-send for recommendations creates Document record and transitions project to delivered

affects: [131-04, 132-frontend-clients]

tech-stack:
  added: []
  patterns:
    - "Carrier contact lookup batched via _load_carrier_contacts() — one query for all carrier_config_ids, returns dict[UUID, str|None]"
    - "Existing active draft check before INSERT on draft-solicitations to guard unique partial index"
    - "approve-send for solicitations accepts both 'pending' and 'approved' statuses — both paths lead to sent"
    - "approve-send for recommendations creates Document row then flushes before commit — document_id available in response"

key-files:
  created:
    - backend/src/flywheel/api/broker/solicitations.py
    - backend/src/flywheel/api/broker/recommendations.py
  modified:
    - backend/src/flywheel/api/broker/main_router.py

key-decisions:
  - "approve_solicitation used user.sub (not user.user_id) — TokenPayload has no user_id attribute, only sub (UUID)"
  - "build_submission_package not called from draft-solicitations — function takes carrier_quote_id (FK to carrier_quotes), not a solicitation_draft_id; passing the wrong ID type would cause silent FK violations or corrupt SubmissionDocument rows; empty documents list returned instead"
  - "approve-send for solicitations accepts status 'pending' or 'approved' — WRK-03 creates approved drafts that then need sending; restricting to only 'pending' would break the approve-then-send workflow"

patterns-established:
  - "Pattern: solicitation drafts are SolicitationDraft rows, not columns on CarrierQuote — all draft workflow uses the solicitation_drafts table"
  - "Pattern: recommendation send creates a Document record in the documents table with module='broker'"

duration: 15min
completed: 2026-04-15
---

# Phase 131 Plan 03: Solicitations and Recommendations Sub-Routers Summary

**5-endpoint solicitations sub-router and 3-endpoint recommendations sub-router implemented using SolicitationDraft and BrokerRecommendation tables — replacing the removed draft_* columns on CarrierQuote and recommendation_* columns on BrokerProject**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-15
- **Completed:** 2026-04-15
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- Created `solicitations.py` with 5 endpoints: GET list, POST batch-draft, PUT edit, POST approve (WRK-03, no send), POST approve-send (WRK-08 body preserved)
- Carrier email sourced exclusively from `carrier_contacts` table via batch `_load_carrier_contacts()` helper — no N+1 queries, no references to deprecated `carrier_configs.email_address`
- Duplicate draft protection: `draft-solicitations` checks for existing active draft (status in draft/pending/approved) before INSERT to respect unique partial index
- Created `recommendations.py` with 3 endpoints: POST draft-recommendation (creates BrokerRecommendation with AI content, transitions project to 'recommended'), PUT edit, POST approve-send (transitions rec to sent, project to delivered, creates Document record)
- Updated `main_router.py` to include both sub-routers; all 8 routes registered under `/broker` prefix

## Task Commits

All tasks committed as a single per-plan commit:

1. **Task 1: Create solicitations.py sub-router** - `928cc47` (feat)
2. **Task 2: Create recommendations.py sub-router** - `928cc47` (feat, same commit)

**Plan commit:** `928cc47` — feat(131-03): add solicitations and recommendations sub-routers

## Files Created/Modified

- `backend/src/flywheel/api/broker/solicitations.py` — 5 endpoints for SolicitationDraft lifecycle; batch carrier contact lookup; WRK-08 body retention; existing draft dedup guard
- `backend/src/flywheel/api/broker/recommendations.py` — 3 endpoints for BrokerRecommendation lifecycle; approve-send creates Document record; project status transitions via validate_transition
- `backend/src/flywheel/api/broker/main_router.py` — Added imports and include_router calls for both sub-routers

## Decisions Made

- `user.sub` used throughout instead of `user.user_id` — `TokenPayload` only exposes `sub` (UUID) and `tenant_id` (property); the plan incorrectly referenced `user.user_id` in `approve_solicitation`
- `build_submission_package` not called from `draft-solicitations` — the function creates `SubmissionDocument` rows with a FK to `carrier_quotes.id`; passing a `SolicitationDraft.id` there would either cause an FK violation or silently create corrupt rows linking documents to a non-existent quote; the endpoint returns `documents: []` instead
- `approve-send` for solicitations accepts both `pending` and `approved` statuses — the `approve` endpoint (WRK-03) puts drafts in `approved` state; the `approve-send` endpoint must accept `approved` too or the approve → send workflow is broken

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed wrong attribute reference: `user.user_id` → `user.sub`**
- **Found during:** Task 1 (solicitations.py `approve_solicitation` function)
- **Issue:** Plan used `user.user_id` to set `approved_by_user_id`, but `TokenPayload` has no `user_id` attribute — only `sub` (UUID) and `tenant_id` (computed property). Would raise AttributeError at runtime.
- **Fix:** Changed to `user.sub` — consistent with how all other broker endpoints set user-owned fields
- **Files modified:** backend/src/flywheel/api/broker/solicitations.py
- **Verification:** Module imports cleanly; confirmed by checking existing broker.py which uses `user.sub` throughout
- **Committed in:** 928cc47

**2. [Rule 1 - Bug] Removed `build_submission_package` call from draft-solicitations**
- **Found during:** Task 1 (draft_solicitations function)
- **Issue:** Plan called `build_submission_package(db, project_id, draft.id)` but the function signature is `(db, project_id, carrier_quote_id: UUID)` — it creates `SubmissionDocument` rows with an FK to `carrier_quotes.id`. Passing a `SolicitationDraft.id` would create SubmissionDocument rows pointing to a non-existent or wrong carrier quote.
- **Fix:** Removed `build_submission_package` call; pass empty `documents: []` list in response. Documents will be linked to CarrierQuotes when quotes are received, not at draft time.
- **Files modified:** backend/src/flywheel/api/broker/solicitations.py
- **Verification:** No import of `build_submission_package` in solicitations.py; `documents` key still present in response dict
- **Committed in:** 928cc47

**3. [Rule 2 - Missing Critical] Extended approve-send to accept 'approved' status**
- **Found during:** Task 1 (approve_send_solicitation function)
- **Issue:** Plan restricted approve-send to `status == 'pending'` only. But WRK-03 creates the `approve` endpoint specifically to put drafts in `approved` state before sending. If approve-send only accepts `pending`, users who use the approve-only endpoint cannot subsequently send without editing the draft (which resets nothing).
- **Fix:** Changed status check to `status not in ("pending", "approved")` — both states are valid pre-send states; `approved_at` is set to existing value if already set, otherwise `now`
- **Files modified:** backend/src/flywheel/api/broker/solicitations.py
- **Committed in:** 928cc47

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical logic)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

None — all verifications passed on first run.

## Self-Check

**Files exist:**
- `backend/src/flywheel/api/broker/solicitations.py` — FOUND
- `backend/src/flywheel/api/broker/recommendations.py` — FOUND

**Route counts:**
- solicitations_router: 5 routes — PASSED
- recommendations_router: 3 routes — PASSED
- main router includes both — PASSED

**WRK-08 body preservation:** 0 `body=None` assignments in approve-send — PASSED
**Carrier email source:** _load_carrier_contacts from carrier_contacts, no carrier.email_address — PASSED

## Self-Check: PASSED

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 04 can now build the remaining sub-routers (clients, contacts, carriers, projects, quotes) that the monolith broker.py still handles
- solicitations and recommendations endpoints are live in the broker/ package and will be active as soon as Plan 04 removes broker.py and makes main_router.py the sole route provider
- No blockers

---
*Phase: 131-backend-atomic-release*
*Completed: 2026-04-15*
