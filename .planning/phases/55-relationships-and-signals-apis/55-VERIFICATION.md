---
phase: 55-relationships-and-signals-apis
verified: 2026-03-27T06:17:31Z
status: human_needed
score: 4/5 must-haves verified
human_verification:
  - test: "Confirm source attribution appears in POST /ask response"
    expected: "Response includes at least one source in the 'sources' array, each citing a specific context entry UUID"
    why_human: "The mechanism is correctly wired (LLM is prompted with [ID:{UUID}] entries and instructed to cite [source:{UUID}] markers), but whether the LLM actually includes source markers in its response is non-deterministic and requires a live call with a real account that has 3+ context entries"
---

# Phase 55: Relationships and Signals APIs Verification Report

**Phase Goal:** The backend API surface is complete — every relationship surface and signal badge has a stable endpoint. The partition predicate preventing accounts from leaking across Pipeline and Relationships surfaces is enforced at the query level. AI synthesis is rate-limited and never auto-triggered.
**Verified:** 2026-03-27T06:17:31Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/v1/relationships/?type=advisor returns only graduated advisor accounts — a prospect account with no graduated_at does not appear even if it has advisor in relationship_type | VERIFIED | `base_where` list always contains `Account.graduated_at.isnot(None)` as first predicate; type filter is appended (AND not OR). Both conditions must be true. A prospect without `graduated_at` fails predicate 1 regardless of relationship_type. |
| 2 | POST /api/v1/relationships/{id}/synthesize called twice within 5 minutes returns 429 on the second call — LLM not invoked; called with null ai_summary returns cached null not new LLM invocation | VERIFIED | `enforce_rate_limit()` called at position 259 in function body, `SynthesisEngine.generate()` at position 1144 — rate limit gate always fires first. Sparse-data case in `generate()` sets `ai_summary_updated_at = now` before returning `None` — so second call within window hits 429 regardless of summary being null. |
| 3 | POST /api/v1/relationships/{id}/ask returns answer with at least one source attribution citing the specific context entry — does not call LLM when account has fewer than 3 context entries | PARTIAL | Sparse data guard verified: `len(entries) < _MIN_CONTEXT_ENTRIES` returns graceful message without LLM call. Source attribution mechanism wired: system prompt includes `[source:{entry_id}]` instruction, entries formatted with `[ID: {entry.id}]`, regex parser extracts markers. However, whether the LLM actually includes markers in a live response requires human verification. |
| 4 | GET /api/v1/signals/ returns per-type badge counts (prospects/customers/advisors/investors separately) — counts are non-zero when stale accounts or overdue follow-ups exist | VERIFIED | `_compute_signals_for_type()` called for all 4 types (`prospect`, `customer`, `advisor`, `investor`). Each call fires 4 queries covering `reply_received`, `followup_overdue`, `commitment_due`, `stale_relationship`. `graduated_at.isnot(None)` in `base_filters` for every query. Non-zero counts depend on data state (human verification for live data). |
| 5 | PATCH /api/v1/relationships/{id}/type rejects empty type array and rejects unknown type values — minimum-one-type validation at API layer | VERIFIED | `UpdateTypeRequest.validate_types` field_validator: empty list raises `"At least one relationship type required"`, unknown type raises `"Unknown type: {value}. Allowed: advisor, customer, investor, prospect"`. Tested programmatically — both raise `ValidationError` before any DB touch. |

**Score:** 4/5 truths verified (Truth 3 is partial pending human confirmation of LLM source attribution behavior)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/030_graduated_at.py` | graduated_at nullable timestamptz column on accounts | VERIFIED | Migration adds `TIMESTAMP(timezone=True) NULL` column, partial index `idx_account_graduated_at WHERE graduated_at IS NOT NULL`. Revision `030_grad_at`, down_revision `029_status_phase_a`. |
| `backend/src/flywheel/api/relationships.py` | Relationships router with 8 endpoints (RAPI-01 through RAPI-08) | VERIFIED | 8 routes confirmed via `len(router.routes)`. All 8 endpoints present: GET list, GET detail, PATCH type, POST graduate, POST notes, POST files, POST synthesize, POST ask. |
| `backend/src/flywheel/services/synthesis_engine.py` | SynthesisEngine with generate(), ask(), enforce_rate_limit() | VERIFIED | Class exists with all 3 static methods. Rate limit window 5 min, min context entries 3. Circuit breaker pattern via `anthropic_breaker`. |
| `backend/src/flywheel/api/signals.py` | Signals router with GET /signals/ endpoint returning badge counts | VERIFIED | 1 route confirmed. All 4 signal types defined with correct priorities. `graduated_at.isnot(None)` appears 4 times (once in each signal query via `base_filters`). |
| `backend/src/flywheel/db/models.py` | graduated_at column on Account ORM model | VERIFIED | `Account.graduated_at` attribute present, column type TIMESTAMP, nullable=True. Partial index in `__table_args__`. |
| `backend/src/flywheel/api/outreach.py` | _graduate_account() sets graduated_at = now | VERIFIED | Line 156: `account.graduated_at = now` present in `_graduate_account()`. |
| `backend/src/flywheel/main.py` | Both routers registered at /api/v1 | VERIFIED | `relationships_router` at line 177, `signals_router` at line 178. Confirmed programmatically: `/api/v1/relationships/` and `/api/v1/signals/` appear in app routes. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `relationships.py` | `db/models.py` | `Account.graduated_at.isnot(None)` partition predicate | WIRED | Appears in every endpoint that queries graduated accounts (7 of 8 endpoints). POST /graduate intentionally omits it. |
| `relationships.py` | `synthesis_engine.py` | `SynthesisEngine.enforce_rate_limit()` + `SynthesisEngine.generate()` + `SynthesisEngine.ask()` | WIRED | Import at line 41. Used in `/synthesize` (enforce_rate_limit before generate) and `/ask` endpoints. |
| `relationships.py` | `Account.ai_summary_updated_at` | DB-level rate limit check before LLM call | WIRED | `enforce_rate_limit()` reads `account.ai_summary_updated_at` and compares against 5-minute window. |
| `synthesis_engine.py` | `anthropic.AsyncAnthropic` | `client.messages.create` with circuit breaker | WIRED | Pattern confirmed: `anthropic_breaker.can_execute()` check, `client.messages.create(...)`, `record_success()` / `record_failure()`. Present in both `generate()` and `ask()`. |
| `signals.py` | `db/models.py` | `Account.graduated_at.isnot(None)` partition predicate | WIRED | Inside `base_filters` list that is unpacked into every signal query (4 queries per type, 4 types = 16 total query executions). |
| `main.py` | `relationships.py` | `include_router(relationships_router)` | WIRED | Line 177 in `main.py`. |
| `main.py` | `signals.py` | `include_router(signals_router)` | WIRED | Line 178 in `main.py`. |

---

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| RAPI-01: GET /relationships/ with type filter and partition predicate | SATISFIED | `base_where` always contains partition predicate; type filter additive |
| RAPI-02: GET /relationships/{id} with contacts, timeline, cached ai_summary | SATISFIED | contacts via `selectinload`, timeline via separate query (10 entries), ai_summary from column — LLM never called on read |
| RAPI-03: PATCH /relationships/{id}/type with validation | SATISFIED | Pydantic `field_validator` rejects empty array and unknown types |
| RAPI-04: POST /relationships/{id}/graduate with 409 guard | SATISFIED | Returns 409 if `graduated_at` already set; no partition predicate (targets non-graduated) |
| RAPI-05: POST /relationships/{id}/notes | SATISFIED | Creates ContextEntry with `account_id=account.id`, partition predicate enforced |
| RAPI-06: POST /relationships/{id}/files | SATISFIED | httpx upload to Supabase Storage, 10 MB limit validated, ContextEntry logged |
| RAPI-07: POST /relationships/{id}/synthesize (rate-limited) | SATISFIED | enforce_rate_limit before generate, 429 with Retry-After header, sparse data sets timestamp |
| RAPI-08: POST /relationships/{id}/ask with source attribution | PARTIAL | Mechanism wired; LLM source attribution output needs human verification |
| SIG-01: GET /signals/ per-type badge counts | SATISFIED | 4 TypeBadge objects returned, one per relationship type |
| SIG-02: Signal taxonomy with 4 types and priorities | SATISFIED | `SIGNAL_TYPES` dict with P1/P2/P3 priorities matches spec |

---

### Anti-Patterns Found

No anti-patterns detected. All scanned files (`relationships.py`, `synthesis_engine.py`, `signals.py`, `030_graduated_at.py`) are clean — no TODOs, FIXMEs, placeholder returns, or stub implementations.

One semantic note on the `commitment_due` signal query: it checks `next_action_due < seven_days_ahead` but does not filter out already-overdue commitments (`next_action_due >= now`). This means past-due commitments with `next_action_type='commitment'` appear in both `followup_overdue` AND `commitment_due` counts simultaneously, potentially double-counting. This is consistent with the plan spec ("commitment coming due within a week") but product intent for overdue commitments may need confirmation.

---

### Human Verification Required

#### 1. Source attribution in POST /ask response

**Test:** With an account that has 3 or more context entries, call `POST /api/v1/relationships/{id}/ask` with a question that relates to content in one of the entries.
**Expected:** The `sources` array in the response contains at least one entry with `id`, `source`, and `date` fields corresponding to the context entry that contains the relevant information.
**Why human:** The mechanism is correctly implemented — the LLM is prompted to use `[source:{entry_id}]` markers and entries are formatted with their UUIDs — but whether the model (claude-haiku-4-5-20251001) reliably includes these markers in its response under real conditions is non-deterministic and cannot be verified without a live API call.

#### 2. Signal counts are non-zero with appropriate data

**Test:** With an account that has `graduated_at` set, `relationship_type` containing `advisor`, and `last_interaction_at` older than 90 days, call `GET /api/v1/signals/`.
**Expected:** The `advisor` TypeBadge has `total_signals > 0` and `counts.stale_relationship > 0`.
**Why human:** The query logic is correctly implemented, but verifying non-zero counts requires live data in the database with the right conditions.

---

### Gaps Summary

No blocking gaps. All structural requirements are implemented and wired. The one partial item (RAPI-08 source attribution) has a correctly implemented mechanism — the only open question is LLM output reliability under live conditions, which is a behavioral property not checkable via static analysis.

---

*Verified: 2026-03-27T06:17:31Z*
*Verifier: Claude (gsd-verifier)*
