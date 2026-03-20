---
phase: 20-skill-execution
verified: 2026-03-20T14:48:25Z
status: human_needed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "stage events delivered to browser -- 'stage' and 'result' added to SSEEventType and eventTypes array in sse.ts"
    - "rendered_html, tokens_used, cost_estimate delivered via SSE done event; ChatStream reads rendered_html with fetch fallback"
    - "ConcurrentRunLimitExceeded detected in catch block; shows friendly assistant message (status: complete) instead of red error box"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run a skill from the chat input with real Anthropic API key configured"
    expected: "Skill executes, stage events update the 'Running skill...' badge, output renders in chat on completion with tokens_used/cost visible"
    why_human: "Requires running backend+frontend stack with real BYOK API key"
  - test: "Close the browser tab mid-execution, reopen chat and reconnect"
    expected: "Late-connecting SSE client replays events_log from the beginning and shows full execution history"
    why_human: "Cannot simulate browser disconnect and late-connect replay in automated check"
  - test: "Start 3 concurrent runs, then send a 4th chat message while all 3 are active"
    expected: "4th message shows 'You have 3 skills running right now. Please wait for one to finish before starting another.' as a normal assistant bubble (not a red error box)"
    why_human: "Requires running backend to trigger 429 and observe actual rendered UI state"
---

# Phase 20: Skill Execution Verification Report

**Phase Goal:** Users can run skills through chat with reliable background execution and real-time streaming
**Verified:** 2026-03-20T14:48:25Z
**Status:** human_needed (all automated checks pass)
**Re-verification:** Yes -- after gap closure plan 20-04

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User types natural-language request, Haiku classifies intent, correct skill executes with clarify if ambiguous | VERIFIED | chat_orchestrator.py and chat.py are substantive and wired. 'stage' now in sse.ts eventTypes -- stage events reach ChatStream.tsx handleEvent |
| 2 | Skill execution runs via Postgres job queue (FOR UPDATE SKIP LOCKED), continues if browser tab closed | VERIFIED | job_queue.py uses SKIP LOCKED correctly, job_queue_loop started in lifespan, stale_job_cleaner also started |
| 3 | Late-connecting client receives replayed SSE events from events_log | VERIFIED | skills.py stream endpoint replays events_log[seen_events:] correctly. Initial load replays all stored events before polling |
| 4 | User can see tokens_used and cost_estimate for each completed skill run | VERIFIED | Executor done event now includes tokens_used, cost_estimate, run_id. Synthetic done event fetches final_run and includes rendered_html, tokens_used, cost_estimate. ChatStream reads rendered_html from done event with fetch fallback |
| 5 | When user hits 3-concurrent-run limit, additional runs queued with visible UI message, stale jobs cleaned after 10 min | VERIFIED | catch block detects ConcurrentRunLimitExceeded, renders friendly assistant message with status 'complete' (not error box). Stale cleaner 10-min threshold confirmed unchanged |

**Score:** 5/5 truths verified

### Gap Closure Verification

#### Gap 1: stage events silently dropped -- CLOSED

`frontend/src/lib/sse.ts` line 4 now reads:
```
type SSEEventType = 'thinking' | 'text' | 'skill_start' | 'stage' | 'result' | 'clarify' | 'error' | 'done'
```

Line 35 `eventTypes` array now contains all 8 types including `'stage'` and `'result'`. `addEventListener` is called for both. `ChatStream.tsx` `stage` case (lines 33-40) and `result` case (lines 41-44) are now reachable.

#### Gap 2: rendered output not delivered via SSE done event -- CLOSED

`backend/src/flywheel/services/skill_executor.py` lines 144-153: done event now emits `run_id`, `tokens_used`, `cost_estimate` (rendered_html intentionally omitted to avoid JSONB bloat -- documented decision).

`backend/src/flywheel/api/skills.py` lines 272-287: synthetic done event fetches `final_run` from DB and includes `rendered_html`, `tokens_used`, `cost_estimate`.

`frontend/src/features/chat/components/ChatStream.tsx` lines 45-56: done case reads `rendered_html` from event; if absent, falls back to `api.get('/skills/runs/{runId}')` to fetch it. `runId` is available from props.

#### Gap 3: concurrent limit shows generic error -- CLOSED

`frontend/src/features/chat/store.ts` lines 148-162: catch block checks `message.includes('concurrent') || message.includes('ConcurrentRunLimitExceeded')`. Concurrent limit errors render as `status: 'complete'` with friendly text; all other errors retain `status: 'error'` with red error box.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/src/flywheel/services/chat_orchestrator.py` | VERIFIED | Unchanged -- Haiku call, JSON parsing, fallback handling, all 3 action types |
| `backend/src/flywheel/services/job_queue.py` | VERIFIED | Unchanged -- FOR UPDATE SKIP LOCKED, job_queue_loop wired in lifespan |
| `backend/src/flywheel/services/skill_executor.py` | VERIFIED | done event now includes tokens_used, cost_estimate, run_id (commit bf162d9) |
| `backend/src/flywheel/services/cost_tracker.py` | VERIFIED | Unchanged -- calculate_cost wired in skill_executor |
| `backend/src/flywheel/services/circuit_breaker.py` | VERIFIED | Unchanged -- 3-state machine, 60s recovery, singleton |
| `backend/src/flywheel/services/stale_job_cleaner.py` | VERIFIED | Unchanged -- 10-min threshold, waiting_for_api recovery |
| `backend/src/flywheel/api/chat.py` | VERIFIED | Unchanged -- POST /chat, intent routing, SkillRun creation |
| `backend/src/flywheel/api/skills.py` | VERIFIED | Synthetic done event now fetches final_run for rendered_html + cost (commit bf162d9) |
| `backend/src/flywheel/main.py` | VERIFIED | Unchanged -- routers registered, background tasks started |
| `frontend/src/features/chat/store.ts` | VERIFIED | ConcurrentRunLimitExceeded detection added (commit 302442a) |
| `frontend/src/features/chat/components/ChatStream.tsx` | VERIFIED | stage/result cases now reachable; done case reads rendered_html with fetch fallback (commit bf162d9) |
| `frontend/src/lib/sse.ts` | VERIFIED | 'stage' and 'result' added to both type union and eventTypes array (commit bf162d9) |
| `frontend/src/types/events.ts` | VERIFIED | StageEvent, ResultEvent interfaces added; DoneEvent enriched with cost fields |
| Alembic migration 006 | VERIFIED | Unchanged -- adds skill_runs to supabase_realtime publication |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| chat.py | chat_orchestrator.classify_intent | lazy import + await | WIRED | Unchanged |
| chat.py | rate_limit.check_concurrent_run_limit | direct import | WIRED | Unchanged |
| main.py | job_queue_loop | asyncio.create_task in lifespan | WIRED | Unchanged |
| skill_executor.py | execution_gateway.execute_skill | asyncio.to_thread + _env_lock | WIRED | Unchanged |
| skill_executor.py | circuit_breaker.anthropic_breaker | direct import | WIRED | Unchanged |
| ChatStream.tsx | useSSE hook | import + call with stage/result in listener list | WIRED | Fixed -- stage and result events now delivered |
| ChatStream.tsx | done event -> setStreamOutput | event handler with fallback fetch | WIRED | Fixed -- reads rendered_html from done, falls back to API fetch |
| store.ts catch | concurrent limit detection | string match on error message | WIRED | Fixed -- isConcurrentLimit branch renders friendly message |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| EXEC-01: Chat intent classification | SATISFIED | classify_intent, POST /chat, SkillRun creation all wired |
| EXEC-02: Postgres job queue FOR UPDATE SKIP LOCKED | SATISFIED | claim_next_job uses .with_for_update(skip_locked=True) |
| EXEC-03: Background execution (browser tab close) | SATISFIED | Job claimed by worker before browser disconnect |
| EXEC-04: Late-connect SSE replay from events_log | SATISFIED | events_log replay in stream_run |
| EXEC-05: tokens_used and cost_estimate per run | SATISFIED | Delivered via enriched SSE done event; ChatStream reads and displays |
| EXEC-06: BYOK key decryption for execution | SATISFIED | _get_user_api_key + decrypt_api_key |
| EXEC-07: Circuit breaker 3-failure / 60s recovery | SATISFIED | CircuitBreaker singleton with correct thresholds |
| EXEC-08: Stale job cleanup 10-min threshold | SATISFIED | STALE_THRESHOLD = timedelta(minutes=10) |
| EXEC-09: waiting_for_api re-queue on recovery | SATISFIED | stale_job_cleaner checks anthropic_breaker.can_execute() |
| EXEC-10: 3-concurrent-run limit with visible UI | SATISFIED | 429 caught, friendly assistant message shown (reject-with-message accepted as equivalent) |

### Anti-Patterns (Remaining)

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/features/chat/components/ChatStream.tsx` | 62 | `runId` used inside useCallback but not in dependency array | Warning | Stale closure risk if runId changes for the same component instance -- not a blocker since runId is stable per stream |
| `frontend/src/lib/realtime.ts` | 51-86 | `useSkillRunRealtime` exported but never imported | Info | Background notification hook is still orphaned. Tab-close scenario relies on SSE replay (working), so not blocking |

### Human Verification Required

#### 1. End-to-End Chat Execution with Stage Events

**Test:** Configure a real Anthropic API key in Settings (BYOK), open the chat view, type "Research Acme Corp", submit
**Expected:** Intent classified as a skill, SkillRun created, "Running skill..." badge appears (stage event visible), output renders in chat on completion with tokens used and cost shown
**Why human:** Requires running stack with real API key; stage event delivery now has correct listener but visual rendering cannot be confirmed without execution

#### 2. Late-Connect SSE Replay

**Test:** Start a slow skill run, close the browser tab immediately, reopen the app and navigate back to the running job
**Expected:** SSE reconnects, replays all past events from events_log, shows execution state from the beginning
**Why human:** Cannot simulate browser tab close and reconnect in automated check

#### 3. Concurrent Limit UX

**Test:** Start 3 skill runs simultaneously, then send a 4th chat message while all 3 are active
**Expected:** 4th message appears as a normal assistant bubble (not a red error box) reading "You have 3 skills running right now. Please wait for one to finish before starting another."
**Why human:** Requires running backend to trigger the 429 and observe actual rendered UI state; string matching depends on ApiError propagating the expected keyword

### Gaps Summary

No automated gaps remain. All 3 previously identified gaps are closed by commits bf162d9 and 302442a.

The remaining items are human-only verifications that cannot be assessed without a running stack and real API credentials.

---

_Verified: 2026-03-20T14:48:25Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes -- after plan 20-04 gap closure_
