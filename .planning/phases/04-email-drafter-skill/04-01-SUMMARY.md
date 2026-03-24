---
phase: 04-email-drafter-skill
plan: 01
subsystem: api
tags: [email, anthropic, sonnet, voice-profile, gmail, background-engine]

# Dependency graph
requires:
  - phase: 03-email-scorer-skill
    provides: EmailScore with context_refs; score_email() pattern (non-fatal, caller-commits, subsidy key)
  - phase: 02-sync-worker-and-voice-profile
    provides: EmailVoiceProfile ORM with tone/avg_length/sign_off/phrases; get_valid_credentials()
  - phase: 01-data-layer-and-gmail-foundation
    provides: EmailDraft ORM model; gmail_read.get_message_body(); ContextEntry/ContextEntity models
provides:
  - email_drafter.py engine with draft_email() entry point
  - Voice profile injection via DRAFT_SYSTEM_PROMPT with DEFAULT_VOICE_STUB cold-start
  - Context assembly from EmailScore.context_refs (no FTS re-run)
  - On-demand body fetch with 401/403 fallback to snippet
  - EmailDraft INSERT with visible_after from config
  - draft_visibility_delay_days config setting
  - skills/email-drafter/SKILL.md for seed registration
affects:
  - 04-02 (gmail_sync.py wiring: _draft_important_emails dispatch)
  - 04-03 (REST API layer for draft lifecycle: approve, dismiss, edit)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "draft_email() mirrors score_email(): non-fatal, caller-commits, subsidy API key, no execute_run()"
    - "Voice profile in system prompt (not user turn) for stronger constraint weighting"
    - "Context assembly reuses scorer context_refs by UUID — no second FTS pass"
    - "Simple INSERT for EmailDraft (no on_conflict — no unique constraint on email_id in migration)"
    - "Body fetch 401/403 fallback stores fetch_error in context_used JSONB"

key-files:
  created:
    - backend/src/flywheel/engines/email_drafter.py
    - skills/email-drafter/SKILL.md
  modified:
    - backend/src/flywheel/config.py

key-decisions:
  - "Drafter bypasses execute_run() — called directly from sync loop (same as scorer)"
  - "Sonnet for drafting, not Haiku — first-draft quality is trust-building; Haiku produces flat prose"
  - "Simple INSERT not on_conflict — no unique constraint on email_drafts.email_id; caller guards via LEFT JOIN IS NULL"
  - "Voice profile injected into system prompt, not user turn — higher constraint weight with Sonnet"
  - "Context assembly reuses EmailScore.context_refs UUIDs — no FTS re-run; deterministic and cheap"
  - "Body fetch error (401/403) stored in context_used JSONB — no schema change, structured error trace"
  - "draft_visibility_delay_days = 0 for dogfood — immediate visibility"

patterns-established:
  - "Pattern: draft_email(db, tenant_id, email, score, integration, api_key=None) -> dict | None"
  - "Pattern: non-fatal outer try/except, log email.id + tenant_id only (no PII), return None"
  - "Pattern: caller-commits — engine never calls db.commit()"
  - "Pattern: DEFAULT_VOICE_STUB cold-start — generic professional draft if no voice profile"

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 4 Plan 01: Email Drafter Engine Summary

**Claude Sonnet draft engine with voice profile injection, context assembly from scorer refs, and 401/403 body fetch fallback — mirroring email_scorer.py patterns exactly**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T13:38:30Z
- **Completed:** 2026-03-24T13:42:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `engines/email_drafter.py` with `draft_email()` entry point and 5 private helpers — exact mirror of email_scorer.py patterns (non-fatal, caller-commits, subsidy API key, bypasses execute_run())
- Voice profile injection via structured `DRAFT_SYSTEM_PROMPT` with `DEFAULT_VOICE_STUB` for cold-start — tone, avg_length, sign_off, and phrases (capped at 5) injected as system prompt constraints
- Context assembly loads up to 5 ContextEntry + 3 ContextEntity rows by UUID from EmailScore.context_refs — no FTS re-run
- Body fetch with 401/403 fallback to snippet; empty body skip guard prevents Sonnet calls on calendar invites
- Added `draft_visibility_delay_days: int = 0` to config.py
- Created `skills/email-drafter/SKILL.md` with correct frontmatter for seed registration

## Task Commits

Tasks 1 and 2 committed together (per-plan commit strategy):

1. **Tasks 1+2: email_drafter engine + SKILL.md** - `f0ad25c` (feat)

## Files Created/Modified

- `backend/src/flywheel/engines/email_drafter.py` — Draft generation engine: voice injection, context assembly, on-demand body fetch, EmailDraft upsert
- `backend/src/flywheel/config.py` — Added `draft_visibility_delay_days: int = 0`
- `skills/email-drafter/SKILL.md` — SkillDefinition seed entry with frontmatter and pipeline documentation

## Decisions Made

- **Sonnet not Haiku:** Draft quality is trust-sensitive; first drafts set user expectations. Haiku produces acceptable JSON but flat prose. Sonnet used for all draft generation.
- **Simple INSERT (not on_conflict):** No unique constraint on `email_drafts.email_id` in migration 020. Caller guards via `LEFT JOIN email_drafts IS NULL` before invoking draft_email(). Simple INSERT is correct.
- **Voice profile in system prompt:** System prompt instructions carry higher weight than user turn with Sonnet. Voice constraints (tone, avg_length, sign_off) treated as constraints, not suggestions.
- **Context assembly from scorer refs:** EmailScore.context_refs already ran FTS and entity lookup. Drafter loads by UUID — no second FTS pass, deterministic, cheap.
- **fetch_error in context_used JSONB:** 401/403 body fetch failures stored as `{"fetch_error": "body_fetch_failed:401"}` in context_used. No schema change needed — JSONB is extensible.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The `python` command is not available in this environment; used `.venv/bin/python` for verification (standard venv pattern for this backend).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `draft_email()` engine is complete and importable — ready to be wired into gmail_sync.py
- Plan 04-02 will add `_draft_important_emails()` dispatch in gmail_sync.py to call draft_email() after scoring
- No blockers for Plan 04-02

---
*Phase: 04-email-drafter-skill*
*Completed: 2026-03-24*

## Self-Check: PASSED

- FOUND: backend/src/flywheel/engines/email_drafter.py
- FOUND: backend/src/flywheel/config.py (draft_visibility_delay_days = 0)
- FOUND: skills/email-drafter/SKILL.md (engine: email_drafter)
- FOUND: .planning/phases/04-email-drafter-skill/04-01-SUMMARY.md
- FOUND commit: f0ad25c feat(04-01): add email_drafter engine and SKILL.md seed definition
