---
phase: 59-team-privacy-foundation
verified: 2026-03-28T18:00:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Confirm 404 vs 403 for cross-user integration DELETE"
    expected: "ROADMAP criterion #2 states User B gets 403 Forbidden on DELETE /integrations/{user_a_id}. Implementation intentionally returns 404. Confirm 404 is acceptable."
    why_human: "The SPEC (PRIV-06) and implementation explicitly chose 404 to avoid leaking resource existence. The ROADMAP success criterion says 403. One of these needs to be updated — human must confirm which is correct."
---

# Phase 59: Team Privacy Foundation Verification Report

**Phase Goal:** User-level RLS policies enforce that personal data (emails, integrations, calendar, skill runs) is invisible to other team members. This is the security prerequisite for any multi-user or team feature.
**Verified:** 2026-03-28T18:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User B in the same tenant calling any email query gets zero of User A's emails | VERIFIED | `Email.user_id == user.sub` in list_threads (line 184), get_thread (line 291), get_digest (line 492) — 3 query filters confirmed |
| 2 | User B querying integrations sees only their own integrations | VERIFIED | `Integration.user_id == user.sub` in list_integrations (line 107), disconnect_integration (line 620), sync_integration (line 651) — 3 filters confirmed |
| 3 | User B querying skill_runs sees only their own runs (plus tenant-shared NULL-user runs) | VERIFIED | `SkillRun.user_id == user.sub` in list_runs base (line 419), list_runs count_q (line 420), get_run (line 458), get_run_attribution (line 482), get_run_trace (line 531) — 5 query locations confirmed |
| 4 | User B querying work_items sees only their own items (plus tenant-shared NULL-user items) | VERIFIED | Migration has Pattern 2 for work_items: `user_id IS NULL OR user_id = current_setting('app.user_id', true)::uuid` in both USING and WITH CHECK — RLS handles this at DB level (no API endpoint for work_items in this phase) |
| 5 | All 7 tables have user_isolation RLS policies replacing tenant_isolation policies | VERIFIED | `backend/alembic/versions/031_user_level_rls.py` contains exactly 7 `CREATE POLICY user_isolation` statements (grep count: 7). Revision chain: `031_user_level_rls -> 030_grad_at`. Python syntax valid. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/031_user_level_rls.py` | Alembic migration with user-level RLS policies on 7 tables | VERIFIED | Exists, 337 lines, valid Python, 7 `CREATE POLICY user_isolation` statements, correct DROP patterns per table |
| `backend/src/flywheel/api/email.py` | User-scoped email queries and draft ownership checks | VERIFIED | `Email.user_id == user.sub` appears 3 times (list endpoints); `email.user_id != user.sub` appears 3 times (draft ownership checks in approve_draft, dismiss_draft, edit_draft); `Integration.user_id == user.sub` in trigger_sync |
| `backend/src/flywheel/api/integrations.py` | User-scoped integration queries | VERIFIED | `Integration.user_id == user.sub` appears 3 times (list, disconnect, sync) |
| `backend/src/flywheel/api/skills.py` | User-scoped skill run queries | VERIFIED | `SkillRun.user_id == user.sub` appears 5 times (base query, count_q, get_run, attribution, trace) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `031_user_level_rls.py` | `app.user_id` session variable | `current_setting('app.user_id', true)::uuid` in USING/WITH CHECK | VERIFIED | Pattern used in all 7 table policies; `app.user_id` appears 15 times in the migration |
| `backend/src/flywheel/api/deps.py` | `app.user_id` session variable | `get_tenant_db` calls `get_tenant_session(user_id=str(user.sub))` | VERIFIED | `deps.py` line 128: `user_id=str(user.sub)` passed to `get_tenant_session`, which executes `set_config('app.user_id', uid, true)` (session.py line 60) |
| `backend/src/flywheel/api/email.py` | `user.sub` (TokenPayload) | `Email.user_id == user.sub` in WHERE clauses | VERIFIED | 3 list endpoint filters + 3 draft ownership checks verified |
| `backend/src/flywheel/api/integrations.py` | `user.sub` (TokenPayload) | `Integration.user_id == user.sub` in WHERE clauses | VERIFIED | 3 endpoint filters verified |
| `backend/src/flywheel/api/skills.py` | `user.sub` (TokenPayload) | `SkillRun.user_id == user.sub` in WHERE clauses | VERIFIED | 5 query location filters verified |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| PRIV-01: user_isolation policy on emails, email_voice_profiles (direct user_id) | SATISFIED | Pattern 1 in migration: DROP 4 per-op policies, CREATE user_isolation with tenant_id AND user_id |
| PRIV-02: user_isolation policy on integrations (direct user_id, different policy name) | SATISFIED | Migration correctly uses `integrations_tenant_isolation` (not generic `tenant_isolation`) for DROP |
| PRIV-03: user_isolation policy on work_items, skill_runs (nullable user_id) | SATISFIED | Pattern 2: `user_id IS NULL OR user_id = current_setting(...)` — system rows remain tenant-visible |
| PRIV-04: user_isolation policy on email_scores, email_drafts (FK subquery) | SATISFIED | Pattern 3: `email_id IN (SELECT id FROM emails WHERE user_id = ...)` — no user_id column needed |
| PRIV-05: API-layer user_id filters on email endpoints | SATISFIED | 7 locations hardened in email.py |
| PRIV-06: API-layer user_id filters on integration endpoints | SATISFIED | 3 locations hardened in integrations.py; returns 404 on cross-user access (see human verification) |
| PRIV-07: API-layer user_id filters on skill run endpoints | SATISFIED | 5 query locations hardened in skills.py |

### Anti-Patterns Found

None detected in modified files. No TODO/FIXME/placeholder comments. No empty implementations. No stub handlers.

### Human Verification Required

#### 1. Confirm 403 vs 404 for cross-user DELETE /integrations

**Test:** User B calls `DELETE /integrations/{user_a_integration_id}` (a valid UUID belonging to User A in the same tenant).
**Expected per ROADMAP:** 403 Forbidden
**Actual behavior:** 404 Not Found

**Why human:** The ROADMAP success criterion #2 explicitly states "gets 403 Forbidden". The SPEC (PRIV-06) and both implementation layers (RLS + API WHERE clause) intentionally return 404 to avoid leaking resource existence to potential attackers. The SUMMARY documents this as a deliberate security decision. One of these needs to be updated:

- **Option A:** Accept 404 as the correct behavior and update ROADMAP criterion #2 to say "gets 404 Not Found" — this is the better security posture.
- **Option B:** Change the implementation to return 403 — this would require loading the integration without the user_id filter first (to distinguish "not found" from "forbidden"), which leaks resource existence.

The implementation is functionally correct for user isolation — User B cannot read, modify, or delete User A's integration regardless of the status code. This is a naming/documentation gap, not a security gap.

### Gaps Summary

No functional gaps. All 7 tables have user-level RLS policies. All personal data API endpoints have defense-in-depth user_id filters. The RLS-to-session-variable wiring is confirmed end-to-end through `get_tenant_db -> get_tenant_session -> set_config('app.user_id')`.

The single human verification item is a documentation inconsistency between the ROADMAP (says 403) and the SPEC + implementation (intentionally returns 404). This does not affect security correctness — user isolation is enforced at both database and API layers regardless.

---

_Verified: 2026-03-28T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
