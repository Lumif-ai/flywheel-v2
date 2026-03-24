---
phase: 03-email-scorer-skill
plan: "01"
subsystem: email
tags: [anthropic, haiku, postgresql, fts, sqlalchemy, email-scoring, context-store]

# Dependency graph
requires:
  - phase: 01-data-layer-and-gmail-foundation
    provides: Email, EmailScore, ContextEntity, ContextEntry ORM models
  - phase: 02-sync-worker-and-voice-profile
    provides: gmail_sync.py Haiku pattern (AsyncAnthropic + json/regex parse), settings.flywheel_subsidy_api_key usage

provides:
  - skills/email-scorer/SKILL.md — seed-compatible skill definition (engine: email_scorer)
  - backend/src/flywheel/engines/email_scorer.py — standalone async scoring engine

affects:
  - 03-02-gmail-sync-integration (calls score_email() from _sync_one_integration)
  - 05-email-copilot-ui (reads EmailScore rows with priority, category, context_refs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-LLM enrichment: Python fetches sender entity + FTS context entries before any LLM call"
    - "plainto_tsquery for user-derived text FTS (prevents SQL errors from subject punctuation)"
    - "pg_insert ON CONFLICT on named constraint for idempotent upsert"
    - "Hallucination filtering: LLM-returned context_ref IDs validated against pre-fetched ID sets"
    - "SCORE-09 escalation bias: when uncertain, score UP (false negatives are critical failures)"
    - "Caller-commits: engine does not call db.commit(), caller controls transaction"
    - "Non-fatal scoring: exceptions log email.id only (no PII), return None, sync loop continues"

key-files:
  created:
    - skills/email-scorer/SKILL.md
    - backend/src/flywheel/engines/email_scorer.py
  modified: []

key-decisions:
  - "Scorer bypasses execute_run() — called directly from sync loop with subsidy key (no user_id needed)"
  - "plainto_tsquery instead of to_tsquery for FTS — prevents SQL errors from email subject punctuation"
  - "Hallucination filtering on context_refs — LLM-returned IDs validated against pre-fetched sets before storage"
  - "Non-fatal scoring — exceptions log only email.id (no PII), return None, sync always completes"
  - "Caller-commits pattern — engine does not commit, consistent with Phase 2 voice_profile_init pattern"

patterns-established:
  - "Pre-LLM enrichment: all context fetched in Python before LLM call, passed as structured JSON"
  - "FTS subject search: strip Re:/Fwd: prefixes, use plainto_tsquery for arbitrary text"
  - "EmailScore upsert: pg_insert ON CONFLICT on uq_email_score_email constraint"

# Metrics
duration: 13min
completed: 2026-03-24
---

# Phase 3 Plan 01: Email Scorer Skill Summary

**async email scoring engine with Claude Haiku: pre-LLM sender entity lookup + plainto_tsquery FTS + SCORE-09 escalation bias + hallucination-filtered context_refs upserted to email_scores**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-24T11:45:52Z
- **Completed:** 2026-03-24T11:59:07Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Created `skills/email-scorer/SKILL.md` — seed-compatible skill definition with engine: email_scorer, contract_reads (context_entities, context_entries), contract_writes (email_scores), web_tier 1
- Created `backend/src/flywheel/engines/email_scorer.py` — 571-line async scoring engine with full pipeline: sender entity lookup, FTS context search, Haiku scoring call, response validation, idempotent upsert
- Scoring prompt embeds signal hierarchy table, 3 few-shot examples (scores 5/4/2), SCORE-09 aggressive escalation bias, 6-category enum, 4-action enum, and context_refs traceability format

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SKILL.md and email_scorer.py scoring engine** - `e3af4a3` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `skills/email-scorer/SKILL.md` — Seed-compatible skill definition declaring engine: email_scorer with contract_reads/writes, web_tier, tags, token_budget; includes scoring rubric documentation
- `backend/src/flywheel/engines/email_scorer.py` — Async scoring engine: score_email() entry point, _lookup_sender_entity() (domain ilike + aliases.contains), _search_context_entries() (plainto_tsquery FTS + ts_rank order), _build_score_prompt() with SCORE_SYSTEM_PROMPT constant (full rubric, 3 few-shot examples, SCORE-09 bias), _parse_score_response() (priority clamp, category/action enum validation, hallucination filtering), _upsert_email_score() (pg_insert ON CONFLICT on uq_email_score_email)

## Decisions Made

- **Bypass execute_run():** The scorer is called directly from the sync loop using `settings.flywheel_subsidy_api_key`. No user_id in background context means routing through execute_run() would require BYOK extension. Direct call is consistent with voice_profile_init.
- **plainto_tsquery not to_tsquery:** Email subjects contain commas, parentheses, and special chars that break to_tsquery. plainto_tsquery handles arbitrary text safely.
- **Hallucination filtering:** LLM returns context_ref IDs. We validate each ID against the pre-fetched entity/entry ID sets. Any ID not in the pre-fetch sets is silently dropped. Prevents fabricated references from polluting the context_refs column.
- **Non-fatal pattern:** score_email() wraps the full pipeline in try/except, logs only email.id and error type (no PII), returns None on any failure. The sync loop in Plan 02 must continue even if scoring fails.
- **Caller-commits:** _upsert_email_score() does not call db.commit(). Consistent with Phase 2 pattern where gmail_sync.py controls the transaction lifecycle.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The scoring engine uses the existing `settings.flywheel_subsidy_api_key` which was configured in Phase 2.

## Next Phase Readiness

Plan 03-02 (gmail sync integration) can proceed immediately:
- `score_email(db, tenant_id, email)` is the entry point signature Plan 02 will call
- Returns `dict | None` — caller checks for None and skips on scoring failure
- Caller must set RLS context (`set_config('app.tenant_id', ...)`) before calling
- Caller must commit after calling (engine does not commit)

No blockers. Engine is importable and syntax-valid (`from flywheel.engines.email_scorer import score_email` confirmed).

---
*Phase: 03-email-scorer-skill*
*Completed: 2026-03-24*
