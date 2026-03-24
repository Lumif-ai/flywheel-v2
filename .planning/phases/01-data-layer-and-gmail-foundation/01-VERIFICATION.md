---
phase: 01-data-layer-and-gmail-foundation
verified: 2026-03-24T09:30:31Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 1: Data Layer and Gmail Foundation — Verification Report

**Phase Goal:** The database and Gmail read service are in place — the foundation every subsequent phase depends on. OAuth grants for Gmail read are architecturally separate from existing send-only credentials and can never break existing users.

**Verified:** 2026-03-24T09:30:31Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                          | Status     | Evidence |
|----|-----------------------------------------------------------------------------------------------|------------|----------|
| 1  | Four new tables (emails, email_scores, email_drafts, email_voice_profiles) exist via Alembic  | VERIFIED   | `020_email_models.py` creates all four with `op.execute()` CREATE TABLE statements; chains from `019_documents` |
| 2  | All four tables have RLS enabled and forced with tenant_isolation policies (SELECT/INSERT/UPDATE/DELETE) | VERIFIED | Migration has `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and 4 per-operation policies per table; DO block at end asserts `relrowsecurity=true` at migration time |
| 3  | app_user role has GRANT on all four tables                                                     | VERIFIED   | `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user` present for all four tables |
| 4  | EmailVoiceProfile has UniqueConstraint(tenant_id, user_id)                                    | VERIFIED   | `uq_voice_profile_tenant_user` in ORM `__table_args__` and `CONSTRAINT uq_voice_profile_tenant_user UNIQUE (tenant_id, user_id)` in migration |
| 5  | emails table has UniqueConstraint(tenant_id, gmail_message_id)                                | VERIFIED   | `uq_email_tenant_message` in ORM `__table_args__` and migration |
| 6  | gmail_read.py can list inbox message headers without fetching body content                    | VERIFIED   | `list_message_headers` uses `messages().list()` returning stubs (id + threadId); `get_message_headers` uses `format="metadata"` with only From/To/Subject/Date headers |
| 7  | gmail_read.py can fetch a single message body on-demand                                       | VERIFIED   | `get_message_body` calls `format="full"` and `_extract_body()` to decode base64 text/plain or text/html |
| 8  | gmail_read.py can list sent messages                                                           | VERIFIED   | `list_sent_messages` calls `labelIds=["SENT"]` |
| 9  | User can initiate Gmail read OAuth flow with correct scopes via /gmail-read/authorize          | VERIFIED   | Endpoint at `GET /gmail-read/authorize` creates `Integration(provider="gmail-read")` and calls `generate_gmail_read_auth_url`; SCOPES = [readonly, modify, send]; no `include_granted_scopes` in code |
| 10 | OAuth callback creates Integration row with provider="gmail-read" — existing provider="gmail" rows never touched | VERIFIED | `gmail_read_callback` filters exclusively on `Integration.provider == "gmail-read"`; `google_gmail.py` has zero diffs since phase start |
| 11 | No email content (subject, snippet, body) appears in any log statement in gmail_read.py       | VERIFIED   | All logger calls log only `message_id`, `thread_id`, `label_ids`, `max_results`, or `start_history_id`; `_extract_body` warning logs only `msg.get("id")`; confirmed with grep — zero matches for `logger.*snippet`, `logger.*subject`, `logger.*body` |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/db/models.py` | Email, EmailScore, EmailDraft, EmailVoiceProfile ORM classes | VERIFIED | All four classes present (lines 899–1050); 1050-line file is substantive; each class has correct `__tablename__`, `__table_args__`, and columns matching DATA-01 through DATA-04 |
| `backend/alembic/versions/020_email_models.py` | Migration creating all four tables with RLS | VERIFIED | 283-line file; creates all four tables with RLS, grants, policies, and set_updated_at triggers on email_drafts and email_voice_profiles |
| `backend/src/flywheel/services/gmail_read.py` | Gmail read service with OAuth flow and message operations | VERIFIED | 459-line file; all 6 API operations present (list_message_headers, get_message_headers, get_message_body, list_sent_messages, get_history, get_profile) plus OAuth and credential functions |
| `backend/src/flywheel/api/integrations.py` | gmail-read/authorize and gmail-read/callback endpoints | VERIFIED | 688-line file; both endpoints wired at lines 313 and 350; `_PROVIDER_DISPLAY` includes "gmail-read" |
| `backend/src/flywheel/config.py` | google_gmail_read_redirect_uri setting | VERIFIED | Line 45: `google_gmail_read_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail-read/callback"` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/flywheel/db/models.py` | `backend/alembic/versions/020_email_models.py` | `__tablename__ = "emails"` in ORM maps to CREATE TABLE in migration | WIRED | Four ORM class tablenames exactly match migration table names |
| `backend/alembic/versions/020_email_models.py` | `019_documents` | `down_revision = "019_documents"` | WIRED | `down_revision: Union[str, None] = "019_documents"` at line 21; `019_documents.py` exists |
| `backend/src/flywheel/api/integrations.py` | `backend/src/flywheel/services/gmail_read.py` | `from flywheel.services.gmail_read import` | WIRED | Import present at line 48–52 in integrations.py; `generate_gmail_read_auth_url` called at line 340, `exchange_gmail_read_code` at line 388, `serialize_gmail_read_credentials` at line 401 |
| `backend/src/flywheel/services/gmail_read.py` | `backend/src/flywheel/config.py` | `settings.google_gmail_read_redirect_uri` | WIRED | Used in `_create_oauth_flow()` at lines 68 and 74 |
| `backend/src/flywheel/api/integrations.py` | Integration model | `provider="gmail-read"` in all row operations | WIRED | 6 occurrences of `provider.*gmail-read` in integrations.py; authorize creates with `provider="gmail-read"`, callback filters by `provider="gmail-read"` |

---

### Requirements Coverage

| Requirement | Description | Status | Notes |
|-------------|-------------|--------|-------|
| DATA-01 | Email model stores Gmail pointer (message_id, thread_id, sender, subject, received_at, labels) — no body storage | SATISFIED | All six fields present on Email ORM; no body column in model or migration |
| DATA-02 | EmailScore model stores priority, category, suggested_action, reasoning, context_refs, sender_entity_id | SATISFIED | All six fields present on EmailScore ORM |
| DATA-03 | EmailDraft model stores draft_body, status, context_used, user_edits, visible_after | SATISFIED | All five fields present on EmailDraft ORM |
| DATA-04 | EmailVoiceProfile model stores tone, avg_length, sign_off, phrases, samples_analyzed | SATISFIED | All five fields present on EmailVoiceProfile ORM |
| DATA-05 | All models are tenant-isolated via RLS (consistent with existing architecture) | SATISFIED | All four tables have ENABLE + FORCE RLS with four per-operation policies using `current_setting('app.tenant_id', true)::uuid` |
| DATA-06 | Alembic migration creates all new tables with proper indexes and constraints | SATISFIED | Migration creates 3 indexes on emails, 1 on email_scores, 1 on email_drafts, and unique constraints as specified |
| GMAIL-01 | System can initiate OAuth flow with gmail.readonly + gmail.modify + gmail.send scopes (separate from existing send-only integration) | SATISFIED | SCOPES list in gmail_read.py has all three; uses `google_gmail_read_redirect_uri` not `google_gmail_redirect_uri`; no `include_granted_scopes` in code |
| GMAIL-02 | System stores Gmail read credentials as a separate Integration row (does not modify existing gmail send integration) | SATISFIED | All new endpoints use `provider="gmail-read"` exclusively; `google_gmail.py` untouched (last commit `87ba820` pre-dates phase) |

---

### Anti-Patterns Found

None detected.

| File | Pattern | Severity | Verdict |
|------|---------|----------|---------|
| `gmail_read.py` | No TODOs, FIXMEs, empty returns, or placeholder implementations | — | Clean |
| `integrations.py` | No TODOs, FIXMEs, or stub endpoints | — | Clean |
| `020_email_models.py` | No stub SQL, no missing policies | — | Clean |
| `models.py` | No stub classes, no missing columns | — | Clean |

---

### Human Verification Required

The following items cannot be verified statically and require a running database and/or live OAuth credentials:

#### 1. Alembic Migration Applies Against Live DB

**Test:** Run `alembic upgrade head` against the local dev DB (or Supabase).
**Expected:** `020_email_models` applies without error; all four tables appear in `pg_tables`; `SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('emails','email_scores','email_drafts','email_voice_profiles')` returns 4 rows all `t/t`.
**Why human:** Cannot run DB migrations programmatically in this context. The SUMMARY notes migration was verified against local dev DB (`localhost:5434`) during execution, but this needs production/Supabase validation before Phase 2.

#### 2. Gmail Read OAuth Round-Trip

**Test:** Navigate to `/api/v1/integrations/gmail-read/authorize`, complete the Google OAuth consent screen, and confirm callback completes.
**Expected:** A new Integration row with `provider="gmail-read"` and `status="connected"` appears in DB; the existing `provider="gmail"` Integration row is unmodified.
**Why human:** Requires live Google OAuth credentials and a running backend server.

#### 3. No Email Content in Logs During Parse Error

**Test:** Trigger a parse failure in `_extract_body` (e.g., send a malformed MIME message) and inspect application logs.
**Expected:** Log output shows only `message_id` in the warning line — no subject, snippet, body text, or sender name.
**Why human:** Cannot trigger a live API parse error statically; requires running app with real Gmail API credentials.

---

### Summary

Phase 1 goal is achieved. The database foundation and Gmail read service are both fully implemented and correctly wired:

- All four email tables are defined in both the ORM layer (models.py) and the Alembic migration (020_email_models.py), with RLS enforced at the database level — matching existing table patterns exactly.
- The Gmail read service (gmail_read.py) provides the full set of operations needed by downstream phases: inbox listing, header fetch, on-demand body fetch, sent listing, history sync, and profile retrieval.
- The OAuth endpoints are architecturally isolated from the existing send-only Gmail integration: separate redirect URI config, separate `provider="gmail-read"` rows, no `include_granted_scopes`, and zero touches to `google_gmail.py`.
- No email content appears in any log statement — only message IDs and operation metadata are logged.

Three human verification items are flagged but do not block the status determination — they are operational confirmations (DB migration applied, OAuth round-trip, log inspection) that require a live environment.

---

_Verified: 2026-03-24T09:30:31Z_
_Verifier: Claude (gsd-verifier)_
