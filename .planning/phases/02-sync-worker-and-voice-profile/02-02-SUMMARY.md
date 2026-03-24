---
phase: 02-sync-worker-and-voice-profile
plan: "02"
subsystem: api
tags: [anthropic, haiku, gmail, voice-profile, nlp, email-filtering]

# Dependency graph
requires:
  - phase: 02-01-sync-worker-and-voice-profile
    provides: gmail_sync.py with _sync_one_integration, sync_gmail, email_sync_loop
  - phase: 01-02-data-layer-and-gmail-foundation
    provides: EmailVoiceProfile ORM model with uq_voice_profile_tenant_user constraint
  - phase: 01-02-data-layer-and-gmail-foundation
    provides: list_sent_messages, get_message_body in gmail_read.py
provides:
  - voice_profile_init(): idempotent voice extraction from substantive sent emails
  - _is_substantive(): filter for auto-replies, OOO, calendar acceptances, one-liners
  - _extract_voice_profile(): AsyncAnthropic Haiku call with json.loads + regex fallback
  - Voice profile wired into sync loop — runs after first sync when no profile exists
affects:
  - phase-03-email-scoring (scorer can assume voice profile is pre-populated)
  - phase-04-drafting (drafter uses EmailVoiceProfile.tone + phrases + sign_off)

# Tech tracking
tech-stack:
  added: [anthropic (AsyncAnthropic)]
  patterns:
    - AsyncAnthropic Haiku call with json.loads + regex fallback for robust parsing
    - pg_insert().on_conflict_do_update() upsert pattern for idempotent profile storage
    - Double idempotency guard (caller check + function-level guard)
    - Non-fatal voice init with try/except in sync loop — email sync always succeeds

key-files:
  created: []
  modified:
    - backend/src/flywheel/services/gmail_sync.py

key-decisions:
  - "Voice section placed after _sync_one_integration in file — Python resolves functions at call time so ordering is correct"
  - "Double idempotency guard: existence check in _sync_one_integration + inner check in voice_profile_init itself (belt and suspenders)"
  - "Only 20 most recent substantive bodies sent to LLM — controls Haiku token cost while preserving recency signal"
  - "Minimum 3 substantive bodies required — prevents meaningless profiles from sparse senders"
  - "Voice init failure is non-fatal — email sync always completes even if Haiku call or upsert fails"

patterns-established:
  - "Pattern: _is_substantive() filter applies before any LLM call — poisoned voice data from auto-replies destroyed in filtering"
  - "Pattern: AsyncAnthropic + json.loads + re.search fallback for robust JSON extraction (matches onboarding_streams.py)"
  - "Pattern: Collect up to N samples, send top-M to LLM for cost control"

# Metrics
duration: 8min
completed: 2026-03-24
---

# Phase 2 Plan 02: Voice Profile Init Summary

**Haiku-based writing voice extraction from substantive sent emails, filtering auto-replies/OOO/calendar, upserted as EmailVoiceProfile once per user after first sync**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-24T10:55:44Z
- **Completed:** 2026-03-24T11:03:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `_is_substantive()` with 12 auto-reply/OOO/calendar patterns + sentence count gate (3+ real sentences required)
- Added `_extract_voice_profile()` calling claude-haiku-4-5-20251001 via AsyncAnthropic with json.loads + regex fallback for robust JSON parsing
- Added `voice_profile_init()` — idempotent, fetches 200 sent stubs, collects up to 100 substantive bodies, sends top 20 to Haiku, upserts EmailVoiceProfile using pg_insert + on_conflict_do_update
- Wired voice init into `_sync_one_integration` after successful `sync_gmail`, with non-fatal try/except wrapper and double idempotency guards

## Task Commits

Both tasks were committed together in one atomic commit:

1. **Task 1: Add voice_profile_init and helpers** — included in `b7fcd7c`
2. **Task 2: Wire voice_profile_init into email_sync_loop** — included in `b7fcd7c`

| Task | Description | Commit | Type |
|------|-------------|--------|------|
| 1 | Add VOICE_SYSTEM_PROMPT, _HAIKU_MODEL, _AUTO_REPLY_PATTERNS, _is_substantive, _extract_voice_profile, voice_profile_init | b7fcd7c | feat |
| 2 | Wire voice_profile_init into _sync_one_integration with existence check + try/except | b7fcd7c | feat |

## Files Created/Modified

- `backend/src/flywheel/services/gmail_sync.py` — Added voice profile extraction section (220 lines): imports for `json`, `re`, `anthropic`, `settings`, `EmailVoiceProfile`, `get_message_body`, `list_sent_messages`; constants VOICE_SYSTEM_PROMPT + _HAIKU_MODEL + _AUTO_REPLY_PATTERNS; functions _is_substantive, _extract_voice_profile, voice_profile_init; wiring in _sync_one_integration

## Decisions Made

- **Double idempotency guard:** Existence check in `_sync_one_integration` before calling `voice_profile_init`, plus a second check inside `voice_profile_init` itself. The outer check avoids the function call overhead on every 5-minute sync cycle; the inner check is the canonical guard for direct calls.
- **Top-20 sample limit:** Collect up to 100 substantive bodies from 200 sent stubs, but send only the 20 most recent to Haiku. Balances quality (recent style is most representative) with cost (Haiku at ~$0.00025/1K tokens is cheap, but 100 × ~500 words each would be excessive).
- **Minimum 3 bodies threshold:** If fewer than 3 substantive emails are found, skip profile creation. Better to have no profile than a misleading one from a single OOO email.
- **Non-fatal wiring:** Voice init exception is caught and logged but does not propagate — email sync is always considered successful regardless of voice init outcome.
- **Section ordering:** Voice extraction functions are placed after `_sync_one_integration` in the file. Python function resolution is runtime so this is correct; logically the sync flow section reads first, then the voice extraction implementation it delegates to.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — virtual environment was in `backend/.venv/` (not project root `.venv/`). Adjusted verification commands accordingly, no code changes needed.

## User Setup Required

None — no external service configuration required. Uses `settings.flywheel_subsidy_api_key` which is already configured for Anthropic API access (same key used by onboarding_streams.py).

## Next Phase Readiness

- Voice profile will be populated for any user after their first Gmail sync completes
- Phase 3 (email scoring) can safely assume `EmailVoiceProfile` exists for active users
- Phase 4 (drafting) can query `EmailVoiceProfile` for `tone`, `avg_length`, `sign_off`, `phrases` to inject into draft prompts
- Concern: scorer prompt engineering is still uncharted — flag for `/gsd:research-phase` before planning Phase 3

---
*Phase: 02-sync-worker-and-voice-profile*
*Completed: 2026-03-24*
