---
phase: 06-feedback-flywheel
verified: 2026-03-24T23:31:24Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 6: Feedback Flywheel Verification Report

**Phase Goal:** The system learns from the user's corrections — draft edits improve future voice profile accuracy, and re-scoring keeps thread priorities fresh as conversations evolve.
**Verified:** 2026-03-24T23:31:24Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After approving an edited draft, voice profile samples_analyzed increments and updated_at advances | VERIFIED | `update_from_edit` line 253: `new_samples = current_samples + 1`, line 268: `updated_at=datetime.now(timezone.utc)` — persisted via UPDATE |
| 2 | After dismissing 3+ drafts from same sender in 30 days, subsequent emails include a DISMISS SIGNAL block in the scoring prompt | VERIFIED | `get_dismiss_signal` returns block string when `count >= threshold`; injected into `_build_score_prompt` via `dismiss_signal=dismiss_block` at scorer line 530 |
| 3 | Voice update only fires when user_edits differs from draft_body (no-op on unedited approvals) | VERIFIED | `has_edit = edited_body is not None and edited_body != original_body` at email.py line 624; background task only fires when `has_edit and original_body is not None` |
| 4 | Voice update runs as background task — approve endpoint returns 200 before profile update completes | VERIFIED | `background_tasks.add_task(_run_voice_update, ...)` at email.py line 634 — fires after `await db.commit()`, approve response is already returned |
| 5 | When a new message arrives in an existing thread, that thread's priority score updates to reflect the latest message | VERIFIED | `_score_new_emails` scores new messages regardless of thread; `list_threads` computes `max_priority` dynamically at read time across all emails in thread via Python grouping |
| 6 | Thread priority (MAX query) automatically reflects the newly scored message without additional code | VERIFIED | `get_thread_priority` is `SELECT MAX(es.priority) FROM email_scores ... WHERE e.gmail_thread_id = :thread_id`; `list_threads` recomputes max from joined score rows at every request |
| 7 | After dismissing several drafts for a sender category, subsequent emails from similar senders score lower | VERIFIED | `dismiss_draft` sets `status='dismissed'`; `get_dismiss_signal` counts these; DISMISS SIGNAL block injected into prompt instructs scorer to "Score DOWN: this sender category produces drafts the user doesn't want to send" |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/engines/email_voice_updater.py` | Diff analysis + incremental voice profile update via Haiku | VERIFIED | 290 lines, full implementation: `_compute_diff_summary` + `update_from_edit` with difflib, Haiku call, profile merge, samples_analyzed increment |
| `backend/src/flywheel/engines/email_dismiss_tracker.py` | Dismiss count query for sender-based scoring adjustment | VERIFIED | 84 lines, `get_dismiss_signal` with real COUNT query using `make_interval(days => :days)`, threshold gate, non-fatal error handling |
| `backend/src/flywheel/api/email.py` | Modified approve_draft with diff capture + background voice update | VERIFIED | `approve_draft` has `BackgroundTasks` param; captures `original_body`/`edited_body` before null; fires `_run_voice_update` after commit; `_run_voice_update` helper at lines 429-458 |
| `backend/src/flywheel/engines/email_scorer.py` | Modified `_build_score_prompt` with dismiss signal injection | VERIFIED | `dismiss_signal: str = ""` param at line 261; injected into user_message at line 336; `score_email` calls `get_dismiss_signal` at lines 520-526 |
| `backend/src/flywheel/config.py` | `voice_update_min_edits`, `dismiss_lookback_days`, `dismiss_threshold` settings | VERIFIED | Lines 69-73: all three settings present with correct defaults (1, 30, 3) |
| `backend/src/flywheel/services/gmail_sync.py` | FEED-03 documentation comments in 3 locations | VERIFIED | 3 FEED-03 occurrences confirmed: `_score_new_emails` docstring (line 208), `_full_sync` append (line 450), `sync_gmail` incremental loop (line 562) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `api/email.py` | `engines/email_voice_updater.py` | `BackgroundTasks.add_task` in `approve_draft` | WIRED | `from flywheel.engines import email_voice_updater` at line 30; `background_tasks.add_task(_run_voice_update, ...)` at line 634; `_run_voice_update` calls `email_voice_updater.update_from_edit` |
| `engines/email_scorer.py` | `engines/email_dismiss_tracker.py` | `get_dismiss_signal` called in `score_email` before prompt build | WIRED | `from flywheel.engines.email_dismiss_tracker import get_dismiss_signal` at line 45; called at lines 520-526 between Step 2 and Step 3 |
| `engines/email_scorer.py` | `config.py` | `settings.dismiss_lookback_days` and `settings.dismiss_threshold` passed to `get_dismiss_signal` | WIRED | Lines 524-525: `days=settings.dismiss_lookback_days, threshold=settings.dismiss_threshold` |
| `api/email.py` | `draft.draft_body` before null | String capture BEFORE null operation | WIRED | Lines 622-624: `original_body = draft.draft_body` and `edited_body = draft.user_edits` captured before `draft.draft_body = None` at line 627 |
| `services/gmail_sync.py sync_gmail` | `services/gmail_sync.py _score_new_emails` | `new_email_ids.append` includes new messages in existing threads | WIRED | Lines 562-565: `messagesAdded` events append to `new_email_ids`; `_score_new_emails(db, integration.tenant_id, new_email_ids)` called at line 593 |

### Requirements Coverage (Success Criteria)

| Requirement | Status | Notes |
|-------------|--------|-------|
| SC1: After 5 edited+approved drafts, `samples_analyzed` increases and phrase/pattern field reflects new signal | SATISFIED | `update_from_edit` increments `samples_analyzed` by 1 per approved edit; merges `phrases_to_add`/`phrases_to_remove` from Haiku response; updates `tone`, `sign_off`, `avg_length` |
| SC2: New message in existing thread updates thread priority score (not locked to original) | SATISFIED | Thread priority is computed at read-time as MAX across all EmailScore rows for the thread; new messages scored via `_score_new_emails` add new rows that participate in the MAX computation |
| SC3: After dismissing several drafts for a sender category, subsequent emails from similar senders score lower | SATISFIED | `dismiss_draft` sets `status='dismissed'`; `get_dismiss_signal` queries this within the rolling window; DISMISS SIGNAL block injected into Haiku prompt instructs scorer to score DOWN |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `engines/email_scorer.py` | 263-276 | `_build_score_prompt` docstring Args section does not document the `dismiss_signal` parameter | Info | Cosmetic documentation gap; function signature and behavior are correct |

No blocker or warning anti-patterns found. No TODO/FIXME/placeholder comments in new files. No stub returns.

### Human Verification Required

#### 1. Voice Profile Phrase Update Signal Quality

**Test:** Approve a draft where you've meaningfully edited the sign-off (e.g., changed "Thanks," to "Best regards,"). Check the `email_voice_profiles` table row for your user — confirm `sign_off` changed and `samples_analyzed` incremented.
**Expected:** `sign_off` = "Best regards," (or similar), `samples_analyzed` = previous + 1, `updated_at` advanced.
**Why human:** Haiku's interpretation of diffs is non-deterministic — the exact fields returned depend on the model's judgment about what constitutes a meaningful change. Trivial diffs may correctly return `{}` (no-op path).

#### 2. Dismiss Signal Threshold Behavior

**Test:** Dismiss 3 drafts from the same sender address. Then trigger a sync bringing in a new email from that sender. Check the scoring logs or `email_scores` reasoning field — it should reference the DISMISS SIGNAL context.
**Expected:** Priority of new email from this sender is lower than comparable emails from unknown senders (all else equal). The reasoning field may reference the dismiss signal.
**Why human:** The scoring outcome depends on Haiku interpreting the DISMISS SIGNAL block — the signal is injected correctly but the score delta varies by email content and context.

#### 3. Thread Priority Refresh on New Message

**Test:** Open a thread with a low-priority first message (e.g., priority 2). Send a follow-up from the same sender with urgency keywords ("ASAP", "urgent deadline"). After sync, check that the thread's `max_priority` in the API response reflects the new message's higher score.
**Expected:** Thread shows priority 4 or 5 after the new message is synced and scored.
**Why human:** Requires an actual Gmail sync cycle with a real or test email to observe the end-to-end behavior.

---

## Notes on FEED-03 Architecture

FEED-03 (thread re-scoring on new messages) requires no new code because:

1. The incremental sync loop processes `messagesAdded` history events — these include new messages in existing threads.
2. New message `email_id`s are appended to `new_email_ids` and scored via `_score_new_emails`.
3. Thread priority (`max_priority`) is computed at read-time as `MAX(priority)` over all EmailScore rows for the thread — no stored thread-level priority column exists to become stale.

This satisfies Success Criterion 2 architecturally without any new code in Phase 6 Plan 02.

---

_Verified: 2026-03-24T23:31:24Z_
_Verifier: Claude (gsd-verifier)_
