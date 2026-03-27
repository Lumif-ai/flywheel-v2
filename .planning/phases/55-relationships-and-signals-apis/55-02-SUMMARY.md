---
phase: 55-relationships-and-signals-apis
plan: 02
subsystem: api

tags: [fastapi, sqlalchemy, anthropic, circuit-breaker, rate-limiting, ai, relationships]

requires:
  - phase: 55-01
    provides: "graduated_at partition predicate, relationships router with 4 endpoints, Account.ai_summary_updated_at column"

provides:
  - "SynthesisEngine service with enforce_rate_limit(), generate(), ask() static methods"
  - "POST /relationships/{id}/synthesize endpoint (RAPI-07) — rate-limited AI summary generation"
  - "POST /relationships/{id}/ask endpoint (RAPI-08) — Q&A with source attribution"
  - "DB-level rate-limit via ai_summary_updated_at: 5-minute window, 429 with Retry-After header"
  - "Sparse-data guard: fewer than 3 context entries returns None/graceful message without LLM call"
  - "Source attribution: [source:UUID] markers parsed from LLM response into structured sources list"

affects: [55-03, 56-frontend-pipeline-relationships]

tech-stack:
  added: []
  patterns:
    - "Rate-limit gate pattern: enforce_rate_limit() ALWAYS called before generate() — prevents LLM invocation even when ai_summary is NULL"
    - "Sparse-data contract: generate() updates ai_summary_updated_at to None result so rate limit applies on subsequent calls"
    - "Source attribution via regex [source:{UUID}] markers — LLM instructed to cite context entry IDs, parsed into structured list"
    - "Circuit breaker reuse: anthropic_breaker.can_execute() / record_success() / record_failure() pattern from onboarding_streams.py"

key-files:
  created:
    - backend/src/flywheel/services/synthesis_engine.py
  modified:
    - backend/src/flywheel/api/relationships.py

key-decisions:
  - "enforce_rate_limit() called BEFORE generate() — this is the critical contract. Rate limit applies even when ai_summary is NULL so a null-result synthesis still locks out the 5-min window"
  - "Sparse data in generate() still updates ai_summary_updated_at — prevents users from hammering synthesis on accounts with few entries"
  - "ask() endpoint has no rate limit — it is stateless (does not write to account)"
  - "SynthesisEngine is a class with static methods (not a singleton or instance) — stateless, session injected per call"
  - "AskResponse.sources list is built only from matched UUIDs present in the fetched entries — no hallucinated sources possible"

duration: 3min
completed: 2026-03-27
---

# Phase 55 Plan 02: SynthesisEngine and AI Endpoints Summary

**SynthesisEngine service with DB-level rate limiting and source attribution — POST /synthesize (RAPI-07) and POST /ask (RAPI-08) wired into relationships router**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-27T06:07:53Z
- **Completed:** 2026-03-27T06:10:46Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 updated)

## Accomplishments

- `SynthesisEngine` service created at `backend/src/flywheel/services/synthesis_engine.py` with three static methods:
  - `enforce_rate_limit(account)` — checks `ai_summary_updated_at` against 5-min window, raises HTTP 429 with `Retry-After` header
  - `generate(db, account)` — fetches up to 20 context entries, calls Haiku via circuit breaker, returns None + updates timestamp for sparse data
  - `ask(db, account, question)` — fetches up to 50 entries, answers question with `[source:UUID]` attribution parsed via regex
- `POST /relationships/{id}/synthesize` (RAPI-07) added: `enforce_rate_limit()` called BEFORE `generate()` — LLM is never invoked when rate-limited
- `POST /relationships/{id}/ask` (RAPI-08) added: no rate limit, graceful insufficient-context response when fewer than 3 entries
- Pydantic schemas added: `SynthesizeResponse`, `AskRequest` (min 5 / max 1000 chars), `AskResponse`
- Router now has 8 endpoints total (was 6 after Plan 01 + RAPI-05/06 additions)

## Task Commits

Per-plan batch commit (commit_strategy=per-plan):

1. **Tasks 1+2 batch:** `8d390a4` feat(55-02): add SynthesisEngine service and POST /synthesize + POST /ask endpoints

## Files Created/Modified

- `backend/src/flywheel/services/synthesis_engine.py` — New: SynthesisEngine with enforce_rate_limit, generate, ask
- `backend/src/flywheel/api/relationships.py` — Added RAPI-07/08 endpoints, SynthesizeResponse/AskRequest/AskResponse schemas, SynthesisEngine import

## Decisions Made

- `enforce_rate_limit()` must precede `generate()` in the synthesize handler — the plan calls this "the most important detail in the entire plan". This guarantees the 429 fires before any LLM invocation, even when `ai_summary` is currently NULL
- Sparse data case (< 3 entries) in `generate()` still sets `ai_summary_updated_at = now` — this is intentional so the 5-minute rate window applies, preventing rapid re-attempts on thin accounts
- `ask()` carries no rate limit — it reads context entries and answers a question without writing to the account; stateless Q&A does not need throttling
- Source attribution uses regex `[source:{UUID}]` pattern — LLM is instructed to embed these markers; parser only returns sources that match entries actually fetched (cannot hallucinate UUIDs)

## Deviations from Plan

**1. [Rule — Observation] relationships.py had RAPI-05 and RAPI-06 added (notes and file upload)**
- **Found during:** Task 2 setup (file read before edit)
- **Issue:** Plan 02 expected 4 routes from Plan 01 and planned to add 2 → 6 total. The file already had 6 routes (RAPI-05 + RAPI-06 added since Plan 01 committed). No conflict — plan's 2 endpoints added on top.
- **Fix:** Proceeded with adding RAPI-07 and RAPI-08. Router now has 8 routes. Updated docstring to reflect all 8.
- **Files modified:** backend/src/flywheel/api/relationships.py

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `POST /relationships/{id}/synthesize` and `POST /relationships/{id}/ask` both live
- Rate-limit contract established: callers can read `Retry-After` header to know when to retry
- SynthesisEngine is ready for Plan 03 (Signals API) to reference if needed
- Phase 55-03 (Signals / Pipeline API) can follow the same graduated_at partition predicate pattern
- Phase 56 (Frontend) can call synthesize on demand and poll ai_summary from GET /relationships/{id}

---
*Phase: 55-relationships-and-signals-apis*
*Completed: 2026-03-27*
