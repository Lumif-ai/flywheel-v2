# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Use accumulated work knowledge to eliminate the cognitive load of email triage and response
**Current focus:** Phase 5 — Review API and Frontend

## Current Position

Phase: 5 of 6 (Review API and Frontend)
Plan: 1 of 3 in current phase
Status: In progress
Last activity: 2026-03-24 — Phase 5 Plan 01 complete (email read API endpoints + api.ts put method)

Progress: [████████░░] 72%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~4 min
- Total execution time: ~0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-layer-and-gmail-foundation | 2 | ~10 min | ~5 min |
| 02-sync-worker-and-voice-profile | 2 | ~11 min | ~5.5 min |
| 04-email-drafter-skill | 2 | ~9 min | ~4.5 min |
| 05-review-api-and-frontend | 1 (in progress) | ~5 min | ~5 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Separate gmail-read OAuth grant — never modify existing send-only integration; `provider="gmail-read"` Integration row
- [Pre-Phase 1]: Extract + discard email body — PII minimization; fetch on-demand for drafting only
- [Pre-Phase 1]: historyId full-sync fallback required from day one — retrofitting requires state migration
- [Pre-Phase 1]: Voice profile filter must exclude auto-replies before any extraction — poisoned first draft destroys trust
- [Pre-Phase 1]: Thread-level display, message-level scoring — highest unhandled score wins per thread
- [Phase 1, Plan 01]: Email + EmailScore + EmailDraft + EmailVoiceProfile ORM models added to models.py; migration 020_email_models; no body column on emails (PII minimization)
- [Phase 1, Plan 02]: No include_granted_scopes on gmail-read grant — isolates read credential from send-only gmail
- [Phase 1, Plan 02]: Pre-allocate history_id=None in pending Integration row — Phase 2 sync worker expects this slot
- [Phase 1, Plan 02]: Three scopes (readonly+modify+send) on single grant — avoids second OAuth prompt for draft approval
- [Phase 2, Plan 01]: historyId captured from get_profile() BEFORE pagination in _full_sync — prevents missed messages during initial sync
- [Phase 2, Plan 01]: Integration re-loaded inside tenant_session — avoids DetachedInstanceError when crossing session boundaries
- [Phase 2, Plan 01]: asyncio.wait_for(60s) per integration + gather(return_exceptions=True) — concurrent multi-user polling, never crashes loop
- [Phase 2, Plan 02]: Double idempotency guard for voice_profile_init — existence check in caller + inner guard in function itself
- [Phase 2, Plan 02]: Only top-20 substantive bodies sent to Haiku — cost control while preserving recency signal
- [Phase 2, Plan 02]: Voice init failure is non-fatal — email sync always completes regardless of Haiku call outcome
- [Phase 2, Plan 02]: Minimum 3 substantive bodies required before profile creation — prevents meaningless profiles
- [Phase 3, Plan 01]: Scorer bypasses execute_run() — called directly from sync loop with subsidy key (no user_id in background context)
- [Phase 3, Plan 01]: plainto_tsquery for FTS — prevents SQL errors from email subject punctuation (commas, parens)
- [Phase 3, Plan 01]: Hallucination filtering on context_refs — LLM-returned IDs validated against pre-fetched sets before storage
- [Phase 3, Plan 01]: Non-fatal scoring — exceptions log only email.id (no PII), return None, sync always completes
- [Phase 3, Plan 01]: Caller-commits pattern — scoring engine does not call db.commit(), consistent with Phase 2 pattern
- [Phase 3, Plan 02]: Score-after-commit pattern — _score_new_emails() called only after upsert db.commit() so scoring failure never loses emails
- [Phase 3, Plan 02]: upsert_email() returns UUID via .returning(Email.id) — avoids extra SELECT round-trip for scoring
- [Phase 3, Plan 02]: Daily cap default 500/day — prevents Haiku cost runaway during initial full sync
- [Phase 3, Plan 02]: get_thread_priority() is read-time MAX query, not stored column (SCORE-07)
- [Phase 3, Plan 02]: email-scorer added to skill_executor subsidy key allowlist — background scoring never has user API key
- [Phase 4, Plan 01]: Drafter bypasses execute_run() — called directly from sync loop (same pattern as scorer)
- [Phase 4, Plan 01]: Sonnet for drafting not Haiku — first-draft quality is trust-building; Haiku produces flat prose
- [Phase 4, Plan 01]: Simple INSERT not on_conflict for EmailDraft — no unique constraint on email_drafts.email_id; caller guards via LEFT JOIN IS NULL
- [Phase 4, Plan 01]: Voice profile injected into system prompt not user turn — higher constraint weight with Sonnet
- [Phase 4, Plan 01]: Context assembly reuses EmailScore.context_refs UUIDs — no FTS re-run; deterministic and cheap
- [Phase 4, Plan 01]: fetch_error stored in context_used JSONB — no schema change; structured error trace for 401/403 fallback
- [Phase 4, Plan 02]: Draft wired after scoring — ensures EmailScore rows committed before LEFT JOIN IS NULL query
- [Phase 4, Plan 02]: send first, null body after — approve endpoint nulls draft_body only on confirmed Gmail send success
- [Phase 4, Plan 02]: user_edits for edits — preserves original draft_body for Phase 6 diff analysis
- [Phase 4, Plan 02]: get_message_id_header on-demand — no schema change; lightweight metadata call at approval time
- [Phase 5, Plan 01]: Single JOIN + Python grouping for thread list — one DB round-trip, no N+1 per thread
- [Phase 5, Plan 01]: BackgroundTasks _run_sync() snapshots IDs before task — avoids ORM detached instance in background context
- [Phase 5, Plan 01]: Thread max_priority computed only over unreplied messages — consistent with scoring intent
- [Phase 5, Plan 01]: digest uses INNER JOIN (only scored emails are meaningful in digest)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4, RESOLVED]: Draft context assembly and voice injection format — validated in 04-RESEARCH.md, implemented in 04-01
- [Pre-Phase 5]: `gmail.readonly` restricted scope verification takes 2-6 weeks — initiate no later than end of Phase 2
- [Phase 5]: Tailwind v4 + `@tailwindcss/typography` plugin compatibility needs verification at Phase 5 setup

## Session Continuity

Last session: 2026-03-24
Stopped at: Phase 5 Plan 01 complete — email read API endpoints (threads, thread detail, sync, digest) and api.ts put method. Phase 5 Plan 02 (inbox UI) is next.
Resume file: None
