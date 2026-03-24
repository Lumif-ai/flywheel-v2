---
phase: 04-email-drafter-skill
verified: 2026-03-24T13:50:26Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 4: Email Drafter Skill Verification Report

**Phase Goal:** Emails scored as important have draft replies waiting — written in the user's voice, assembled with relevant context, and never storing the raw email body beyond draft generation.
**Verified:** 2026-03-24T13:50:26Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Emails with priority 3+ and suggested_action=draft_reply get an EmailDraft row with draft_body containing a voice-matched reply | VERIFIED | `_draft_important_emails()` queries EmailScore with `priority >= 3` AND `suggested_action == 'draft_reply'`, calls `draft_email()`, which inserts an EmailDraft row with `status="pending"` and generated `draft_body` |
| 2 | Draft reasoning lists which context entries were assembled (traceable to specific meetings, deals, or entity notes) | VERIFIED | `context_used` JSONB column on EmailDraft stores the `context_refs` list (entry UUIDs + entity UUIDs) passed from EmailScore. `_assemble_draft_context()` loads up to 5 ContextEntry + 3 ContextEntity rows by UUID and formats them as labeled text blocks |
| 3 | When Gmail API returns 401/403 during body fetch, system falls back to snippet and records a structured error in context_used | VERIFIED | `_fetch_body_with_fallback()` catches `HttpError` with `status in (401, 403)`, returns `(email.snippet, "body_fetch_failed:{status}")`. `_upsert_email_draft()` appends `{"fetch_error": fetch_error}` to `context_used` JSONB list |
| 4 | When no voice profile exists (cold-start), a generic professional draft is still generated using DEFAULT_VOICE_STUB | VERIFIED | `_load_voice_profile()` returns `DEFAULT_VOICE_STUB = {"tone": "professional and direct", "avg_length": 80, "sign_off": "Best,", "phrases": []}` when `EmailVoiceProfile` is not found; drafting proceeds normally |
| 5 | Draft engine failure never blocks or crashes the sync loop | VERIFIED | `_draft_important_emails()` has per-email try/except continuing on failure. Both `_full_sync()` and `sync_gmail()` wrap the drafting block in outer try/except with `# Non-fatal — sync and scoring already committed` |
| 6 | After sync, emails with priority 3+ and suggested_action=draft_reply have an EmailDraft row created automatically | VERIFIED | `_draft_important_emails()` wired in both `_full_sync()` (line 479) and `sync_gmail()` incremental path (line 594); LEFT JOIN IS NULL idempotency guard prevents duplicate drafts |
| 7 | User can approve a draft via POST /api/v1/email/drafts/{id}/approve and the email is sent as a threaded reply in Gmail | VERIFIED | Endpoint exists at `/email/drafts/{draft_id}/approve`; calls `send_reply()` with `In-Reply-To` + `References` MIME headers; body is nulled after successful send |
| 8 | After draft is sent, EmailDraft.draft_body is nulled and status is 'sent' | VERIFIED | In approve endpoint: `draft.draft_body = None`, `draft.status = "sent"` set ONLY after successful `send_reply()` call; allows retry on failure |
| 9 | Raw email body is never stored beyond draft generation | VERIFIED | `get_message_body()` is called on-demand only inside `draft_email()` — not during sync. Body is passed to Sonnet via prompt and not persisted anywhere (SKILL.md confirms: "Body is fetched from Gmail API only at draft generation time and not persisted beyond the LLM call") |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/engines/email_drafter.py` | Draft generation engine with voice injection and context assembly | VERIFIED | 505 lines; exports `draft_email()`, `DEFAULT_VOICE_STUB`; 5 private helpers present; imports confirm from `.venv/bin/python` |
| `backend/src/flywheel/config.py` | `draft_visibility_delay_days` setting | VERIFIED | `draft_visibility_delay_days: int = 0  # 0 = immediate visibility for dogfood` at line 66 |
| `skills/email-drafter/SKILL.md` | SkillDefinition seed entry for email-drafter | VERIFIED | Frontmatter: `engine: email_drafter`, `contract_reads`, `contract_writes`, `token_budget: 15000`; 5 documentation sections present |
| `backend/src/flywheel/api/email.py` | Draft lifecycle REST endpoints (approve, dismiss, edit) | VERIFIED | 255 lines; 3 routes: `/email/drafts/{draft_id}/approve`, `/email/drafts/{draft_id}/dismiss`, `/email/drafts/{draft_id}` (PUT); confirmed by import |
| `backend/src/flywheel/services/gmail_read.py` | `send_reply()` and `get_message_id_header()` functions | VERIFIED | Both functions present at lines 439 and 485; MIME In-Reply-To + References headers for thread continuity |
| `backend/src/flywheel/services/gmail_sync.py` | `_draft_important_emails()` wired into both sync paths | VERIFIED | 3 occurrences: definition + 2 call sites (_full_sync at line 479, sync_gmail at line 594) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `email_drafter.py` | `EmailScore.context_refs` | UUID load from context_refs list | VERIFIED | `_assemble_draft_context()` iterates `context_refs`, extracts `type="entry"` and `type="entity"` UUIDs, loads from DB |
| `email_drafter.py` | `gmail_read.get_message_body` | On-demand body fetch with 401/403 fallback | VERIFIED | `_fetch_body_with_fallback()` calls `get_message_body(creds, email.gmail_message_id)` with `HttpError` catch for 401/403 |
| `email_drafter.py` | `EmailVoiceProfile` | Voice profile load + DEFAULT_VOICE_STUB fallback | VERIFIED | `_load_voice_profile()` queries `EmailVoiceProfile` by tenant_id + user_id; returns `DEFAULT_VOICE_STUB` on `None` |
| `gmail_sync.py` | `email_drafter.py` | `_draft_important_emails` calls `draft_email` per qualifying email | VERIFIED | Import at line 36: `from flywheel.engines.email_drafter import draft_email`; called inside `_draft_important_emails()` loop |
| `api/email.py` | `gmail_read.send_reply` | Approve endpoint calls send_reply for threaded Gmail send | VERIFIED | Import at lines 23-27; called in `approve_draft()` with all required args including `thread_id` and `in_reply_to` |
| `email_dispatch.py` | gmail-read provider | Provider list includes gmail-read | VERIFIED | `Integration.provider.in_(["gmail", "gmail-read", "outlook"])` at line 49; routing case at line 67 |
| `main.py` | `api/email.py` | include_router for email_router | VERIFIED | `from flywheel.api.email import router as email_router` at line 37; `app.include_router(email_router, prefix="/api/v1")` at line 165 |

---

### Requirements Coverage

No REQUIREMENTS.md entries mapped to Phase 4 checked — phase goals derived from ROADMAP.md goal statement.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (none) | — | — | No anti-patterns detected in email_drafter.py, api/email.py, gmail_sync.py |

No TODOs, FIXMEs, placeholder returns, stub handlers, or empty implementations found.

---

### Assumptions Made (Need Confirmation)

No SPEC-GAPS.md found. No open assumptions flagged.

---

### Human Verification Required

The following items cannot be verified programmatically:

#### 1. Draft Voice Fidelity

**Test:** After a sync cycle with a real voice profile, review a generated draft for tone and sign-off adherence.
**Expected:** Draft reads in the user's characteristic tone, uses their sign-off, stays near their avg_length word target.
**Why human:** LLM output quality and voice fidelity cannot be measured by grep.

#### 2. Threaded Reply in Gmail UI

**Test:** Approve a pending draft via the API and verify the sent email appears inside the original Gmail thread (not as a new conversation).
**Expected:** Email appears in the original thread with the reply in-line.
**Why human:** Gmail threading display requires a real Gmail account and UI inspection.

#### 3. Draft Visibility After Approval

**Test:** After approving a draft, confirm `draft_body` is NULL in the database.
**Expected:** `EmailDraft.draft_body IS NULL` and `status = 'sent'` for the approved draft.
**Why human:** Requires a live DB query against real test data post-approval; not mockable statically.

---

## Summary

All 9 observable truths are verified against the actual codebase. All 6 required artifacts exist, are substantive (not stubs), and are properly wired. All 7 key links are active. No anti-patterns found.

The phase goal is achieved: scored emails (priority >= 3, suggested_action=draft_reply) receive auto-generated EmailDraft rows containing voice-matched replies assembled from context_refs, with on-demand body fetch and 401/403 fallback — and the raw email body is never persisted beyond the LLM call. The draft lifecycle API (approve/dismiss/edit) is wired into main.py and ready for frontend consumption.

Three human verification items remain (voice fidelity, Gmail thread display, post-approval PII nulling confirmation) but these do not block phase completion — they require live integration testing.

---

_Verified: 2026-03-24T13:50:26Z_
_Verifier: Claude (gsd-verifier)_
