# Phase 6: Feedback Flywheel — Research

**Researched:** 2026-03-25
**Domain:** ML feedback loops, diff analysis, incremental model updates, background job patterns (Python/FastAPI/SQLAlchemy async)
**Confidence:** HIGH — all findings based on direct codebase inspection of the production code this phase extends

---

## Summary

Phase 6 closes the learning loop: user actions on drafts (edits and dismissals) feed back into the voice profile and scorer, and new thread arrivals trigger re-scoring. The codebase already has all the raw materials needed — the `user_edits` column preserves original draft bodies for diff analysis, dismiss status is already written by the endpoint, and `_score_new_emails()` in `gmail_sync.py` already calls `score_email()` for every new email in a thread. The work is wiring these signals into two new engines: `email_voice_updater.py` (learns from edits) and `email_dismiss_tracker.py` (learns from dismissals), plus ensuring FEED-03 re-scoring triggers correctly for new messages in existing threads.

The key architectural insight: Phase 6 does NOT need a new feedback table. The `email_drafts.user_edits` column is the edit signal; draft `status='dismissed'` is the dismiss signal; and the existing `_score_new_emails()` already re-scores new messages in existing threads as a side-effect of the sync loop. The main work is (a) building engines that read and process these signals, (b) deciding *when* to trigger them (debounced vs. immediate, batch vs. per-event), and (c) ensuring the scoring system incorporates dismiss patterns when building prompts.

**Primary recommendation:** Implement voice update as an in-process background task triggered at approve-time (not a separate loop), and implement dismiss-based scoring adjustment via a `sender_dismiss_stats` look-aside at score time — no new table required, just a query against `email_drafts` with `status='dismissed'` joined to `emails.sender_email`.

---

## User Constraints

No CONTEXT.md exists for this phase. Full discretion applies.

**Prior decisions that constrain this phase (from roadmap):**

| Decision | Source | Constraint |
|----------|--------|------------|
| Voice profile created from top-20 substantive sent bodies via Haiku | Phase 2 | Updater must use same Haiku model and same JSON schema |
| Voice profile injected into system prompt at drafting time | Phase 4 | Profile must stay in `email_voice_profiles` table; no new profile format |
| `user_edits` stores edits; `draft_body` preserved | Phase 4 | Diff is `draft_body` vs `user_edits`; both columns always available at approve time |
| Send first, null body after | Phase 4 | Diff must be extracted BEFORE `draft_body` is nulled (i.e., at approve time, before the null) |
| Scorer bypasses execute_run() — called directly | Phase 3 | Re-scoring must follow same direct-call pattern |
| get_thread_priority() is read-time MAX query, not stored column | Phase 3 | FEED-03 re-scoring works by ensuring new messages get scored; thread priority auto-updates because it's computed at read time |
| Daily cap 500/day | Phase 3 | Re-scoring of existing threads counts against the cap |

---

## Codebase Inventory

### Files Phase 6 Touches Directly

| File | Role | What Phase 6 Needs |
|------|------|--------------------|
| `backend/src/flywheel/api/email.py` | `approve_draft`, `dismiss_draft`, `edit_draft` endpoints | Hook voice update into `approve_draft` (after send, before null) |
| `backend/src/flywheel/services/gmail_sync.py` | `_score_new_emails()`, `voice_profile_init()` | FEED-03 already works via `_score_new_emails()`; verify behavior |
| `backend/src/flywheel/engines/email_scorer.py` | `score_email()`, `_build_score_prompt()` | Add dismiss signal to scoring prompt |
| `backend/src/flywheel/db/models.py` | `EmailVoiceProfile`, `EmailDraft`, `EmailScore` | No schema changes needed for MVP |
| `backend/src/flywheel/config.py` | Settings | May need `voice_update_min_edits: int = 5` config |

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/src/flywheel/engines/email_voice_updater.py` | Diff analysis + incremental voice profile update |
| `backend/src/flywheel/engines/email_dismiss_tracker.py` | Dismiss pattern query + scoring adjustment signal |

---

## Architecture Patterns

### Pattern 1: Approve-Time Voice Update (VOICE-04 / FEED-02)

**What:** When `approve_draft` runs successfully (email sent), extract diff between `draft_body` and `user_edits`, use Haiku to identify what changed, and incrementally update the voice profile.

**When to trigger:** Inside `approve_draft` endpoint, AFTER send succeeds, BEFORE `draft_body` is nulled — this is the only moment both `draft_body` and `user_edits` coexist and are non-null.

**Debounce decision:** The requirement says "debounced" but the FastAPI endpoint context makes true time-based debouncing impractical. The recommended implementation is a **count-based gate**: only update the voice profile if a minimum number of edits exist (default 5, configurable). This achieves the same effect as debouncing — avoids noisy single-edit updates — without needing asyncio timers or a separate loop.

**Execution model:** Use `BackgroundTasks` (already used in `trigger_sync`) — fire-and-forget, non-blocking. The approve endpoint returns 200 immediately; voice update runs after response.

**Trigger guard:** Only trigger when `draft.user_edits is not None` AND `draft.draft_body is not None` — skip if user didn't edit (no diff to learn from).

**Sequence:**
```
approve_draft endpoint
  1. verify draft + email + integration
  2. send_reply() — may raise, stops here on failure
  3. BEFORE null: if user_edits is not None → extract diff signal
  4. null draft_body, set status='sent'
  5. commit
  6. background_tasks.add_task(update_voice_from_edit, ...)
```

**Critical invariant:** The diff must be captured (or the task must be queued) BEFORE the null happens. Since the null is in the same transaction as the commit, the background task must receive `draft_body` and `user_edits` as string arguments, NOT as ORM references (ORM object will be expired/detached after commit).

### Pattern 2: Diff Analysis Engine (FEED-02)

**What:** Compare `draft_body` (AI generated) vs `user_edits` (what user actually sent). Use difflib for structural diff, then Haiku to interpret what the changes signal about voice.

**Diff approach:** `difflib.ndiff()` or `difflib.unified_diff()` — both available in stdlib, no new dependencies. Focus on:
- Lines/sentences added (user preferred this phrasing)
- Lines/sentences removed (user rejected this phrasing)
- Sign-off changes (high signal for `sign_off` field)
- Length difference (avg_length calibration)

**LLM call:** Same Haiku model, same JSON schema as `voice_profile_init`. Pass: original draft, user's version, current voice profile, and ask for updated voice profile fields. Return only the fields that changed, merge with existing profile.

**Merge strategy:** Don't replace the entire profile on each edit — use weighted averaging or additive updates:
- `avg_length`: running average with weight toward new observations
- `phrases`: union with deduplication, capped at 10 items; score/rank by frequency
- `tone`, `sign_off`: replace only if edit clearly demonstrates a change (Haiku decides)
- `samples_analyzed`: increment by 1

### Pattern 3: Dismiss Signal Integration (FEED-01)

**What:** After N dismissals from a sender category, that category (or sender domain) should score lower. There is NO need for a new table — `email_drafts.status='dismissed'` joined to `emails.sender_email`/`emails.sender_name` is the signal.

**Query at score time:** In `_build_score_prompt()` (or as a pre-step in `score_email()`), run a cheap COUNT query:

```sql
SELECT COUNT(*) FROM email_drafts ed
JOIN emails e ON ed.email_id = e.id
WHERE e.tenant_id = :tid
AND e.sender_email = :sender_email
AND ed.status = 'dismissed'
AND ed.updated_at >= now() - interval '30 days'
```

**Scoring adjustment:** If dismiss_count >= threshold (default 3), add a `DISMISS SIGNAL` block to the scoring prompt. The Haiku scorer already knows to score DOWN based on signals in the prompt. No score math in Python — let Haiku do it.

**Threshold:** 3 dismissals in 30 days for a specific sender. 2 dismissals for a sender domain pattern (multiple senders from same domain). These should be configurable.

**Alternative considered:** Storing dismiss_count in a separate table. Rejected: the query is cheap (indexed by `email_drafts.tenant_id, status`) and avoids table proliferation.

### Pattern 4: Thread Re-scoring (FEED-03)

**What:** When a new message arrives in an existing thread, the thread's priority score updates automatically.

**Key insight from codebase:** This ALREADY WORKS. The `_score_new_emails()` function in `gmail_sync.py` is called for every new email in both full and incremental syncs. Since `get_thread_priority()` is a read-time MAX query (SCORE-07), as soon as the new message is scored, the thread's displayed priority automatically reflects the highest-scored unhandled message — including the new arrival.

**What Phase 6 actually needs to verify for FEED-03:**
1. New messages in existing threads ARE being picked up by incremental sync (they arrive as `messagesAdded` history events — YES, confirmed in `sync_gmail()`)
2. These new messages ARE passed to `_score_new_emails()` — YES, `new_email_ids` includes them
3. The scored message IS included in `get_thread_priority()`'s MAX query — YES, no filter by creation time

**Conclusion for FEED-03:** The re-scoring trigger is already implemented. The plan for 06-02 should be to write a test that verifies this behavior and document it — not to build new infrastructure.

### Recommended Structure for New Engines

```
backend/src/flywheel/engines/
├── email_voice_updater.py    # VOICE-04 / FEED-02: diff analysis + voice update
├── email_dismiss_tracker.py  # FEED-01: dismiss signal query + prompt injection
└── (existing engines)
```

### Anti-Patterns to Avoid

- **Nulling draft_body before extracting diff:** The approve endpoint nulls `draft_body` AFTER send. Phase 6 must read `draft_body` before the null operation, not after.
- **ORM object access after commit:** After `await db.commit()`, ORM objects are expired. Pass strings, not ORM references, into background tasks.
- **Full voice profile re-extraction on each edit:** Calling `voice_profile_init()` logic (fetch 200 sent emails, analyze 20) on every approved edit would be expensive and slow. Use incremental update with a lightweight diff prompt instead.
- **New feedback table:** The existing `email_drafts` table is the feedback store. Don't create `email_feedback` or `dismiss_signals` tables — JOIN queries are sufficient and cheaper to maintain.
- **Blocking the approve endpoint:** Voice update must run as a background task. Updating the profile can take 1-2 seconds (Haiku call) — the user should not wait for it.
- **Scoring dismiss signals at every email:** The dismiss COUNT query adds latency per email scored. Cache the result per-session or batch the lookup — or only query when the sender has at least one dismiss record (use a fast existence check first).

---

## Standard Stack

### Core (already in project)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `anthropic` | (project pinned) | Haiku LLM calls for diff analysis and voice update | Same client/model as existing engines |
| `sqlalchemy` (async) | (project pinned) | DB queries for dismiss signal, voice profile upsert | Follow existing `pg_insert().on_conflict_do_update()` pattern |
| `fastapi.BackgroundTasks` | (project pinned) | Fire voice update after approve response | Already used in `trigger_sync` endpoint |
| `difflib` | Python stdlib | Structural diff between draft_body and user_edits | No install needed |

### No New Dependencies Required

Phase 6 is purely additive on top of existing patterns. The diff library is stdlib. All LLM, DB, and background task infrastructure is already in place.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic diff | Custom NLP tokenizer | `difflib.ndiff()` + Haiku interpretation | difflib captures structural changes; Haiku interprets meaning |
| Debouncing | asyncio.Timer / Redis TTL | Count-based gate (check N edits exist before updating) | Simpler, no timer infrastructure, achieves same goal |
| Dismiss storage | New `email_dismiss_signals` table | Query `email_drafts WHERE status='dismissed'` | Data already exists; table proliferation adds maintenance cost |
| Score adjustment math | Numeric penalty in Python | Inject dismiss signal into Haiku prompt | Haiku already knows the scoring rubric; keeps adjustment logic centralized |
| Thread re-scoring loop | New background job | `_score_new_emails()` already scores new thread messages | Already implemented; document + test only |

---

## Common Pitfalls

### Pitfall 1: Draft Body Already Nulled When Update Fires

**What goes wrong:** Background task tries to read `draft.draft_body` from DB to compute diff, but the approve endpoint already nulled it in the same transaction.

**Why it happens:** Tempting to pass only `draft_id` to the background task and re-load the draft. But after approve, `draft_body=None` and `status='sent'`.

**How to avoid:** Capture the string values of `draft.draft_body` and `draft.user_edits` before the null operation in the endpoint handler. Pass these string values (not the draft ORM object or ID) to the background task.

```python
# In approve_draft, BEFORE null:
original_body = draft.draft_body          # capture here
edited_body = draft.user_edits            # capture here
# ... null and commit ...
background_tasks.add_task(
    update_voice_from_edit,
    tenant_id=user.tenant_id,
    user_id=user.id,
    original_body=original_body,          # pass strings
    edited_body=edited_body,
)
```

**Warning sign:** `update_voice_from_edit` receiving `None` for `original_body`.

### Pitfall 2: Voice Update Triggers on Every Approval (Including Unedited)

**What goes wrong:** Voice update fires even when user approved without editing (no diff signal), wasting a Haiku call and potentially degrading the profile with empty signal.

**Why it happens:** Not checking `user_edits is not None` before triggering.

**How to avoid:** Guard: `if edited_body is not None and edited_body != original_body`.

**Warning sign:** Voice profile `samples_analyzed` increasing rapidly even when user is approving without editing.

### Pitfall 3: Dismiss Signal Query Runs on Every Single Email Score

**What goes wrong:** `score_email()` hits the DB for dismiss count on every email, even for brand-new senders with no dismiss history. At 500 emails/day, this is 500 extra DB round-trips per sync.

**Why it happens:** Injecting the dismiss lookup into `score_email()` without a fast-path exit.

**How to avoid:** Either (a) check existence in `email_drafts WHERE status='dismissed' AND sender_email=X LIMIT 1` first (fast index scan), or (b) run dismiss lookup only when `sender_entity` is not None (known sender), or (c) batch the dismiss lookup before the scoring loop.

**Warning sign:** `_score_new_emails()` taking noticeably longer after Phase 6.

### Pitfall 4: Min-Edit Gate Never Reached for New Users

**What goes wrong:** Voice profile never updates because user hasn't hit the edit threshold (e.g., 5 edits). Approval feedback is silently discarded.

**Why it happens:** Count-based gate set too high, or user approves without editing often.

**How to avoid:** Make the threshold configurable (`voice_update_min_edits: int = 1` as default, not 5). Log when a diff is available but threshold not met, so it's observable. Consider tracking pending-update-count separately so the update fires once threshold is crossed.

**Warning sign:** `samples_analyzed` never increases even after 10+ approve actions.

### Pitfall 5: Voice Profile `phrases` Array Grows Without Bound

**What goes wrong:** Every incremental update adds new phrases. After 50 edits, the phrases list has 50 items, degrading draft quality (too many constraints) and increasing token cost.

**Why it happens:** Appending new phrases without pruning.

**How to avoid:** Cap `phrases` at 10 items. When merging, have Haiku rank phrases by how often they appear in edits and keep the top 10. Prune on each update.

### Pitfall 6: RLS Context Not Set in Background Task

**What goes wrong:** Background task opens a new DB session but forgets to set `app.tenant_id` via `tenant_session()` / `set_config`. All queries return empty results silently (RLS blocks them).

**Why it happens:** Background tasks don't inherit the request's DB session.

**How to avoid:** Use the existing `tenant_session()` context manager from `flywheel.db.session`, same as the sync loop and `trigger_sync`. Pass `tenant_id` and `user_id` as string parameters to the background function.

---

## Code Examples

### Example 1: Capturing Diff Before Null in Approve Endpoint

```python
# Source: backend/src/flywheel/api/email.py (approve_draft) — pattern to extend

# Capture strings BEFORE null — ORM object expires after commit
original_body = draft.draft_body
edited_body = draft.user_edits
has_edit = (edited_body is not None and edited_body != original_body)

# Send the reply first (may raise — leave draft in pending if so)
await send_reply(...)

# Null body, commit
draft.draft_body = None
draft.status = "sent"
draft.updated_at = datetime.now(timezone.utc)
await db.commit()

# Fire voice update in background only if user actually edited
if has_edit and original_body is not None:
    background_tasks.add_task(
        update_voice_from_edit,
        tenant_id=user.tenant_id,
        user_id=user.id,
        original_body=original_body,
        edited_body=edited_body,
    )
```

### Example 2: Background Task with Tenant Session

```python
# Source: pattern from backend/src/flywheel/api/email.py trigger_sync

async def update_voice_from_edit(
    tenant_id: UUID,
    user_id: UUID,
    original_body: str,
    edited_body: str,
) -> None:
    """Background: update voice profile from a single edit diff."""
    factory = get_session_factory()
    async with tenant_session(factory, str(tenant_id), str(user_id)) as db:
        try:
            await email_voice_updater.update_from_edit(
                db, tenant_id, user_id, original_body, edited_body
            )
        except Exception:
            logger.exception(
                "voice update failed for tenant_id=%s user_id=%s",
                tenant_id,
                user_id,
            )
            # Non-fatal — approve was already successful
```

### Example 3: Voice Profile Incremental Update (Haiku Prompt Structure)

```python
# In email_voice_updater.py — same pattern as VOICE_SYSTEM_PROMPT in gmail_sync.py

UPDATE_VOICE_PROMPT = """\
You are updating a voice profile based on how a user edited an AI-generated email draft.

CURRENT VOICE PROFILE:
{current_profile_json}

AI-GENERATED DRAFT (original):
{original_body}

USER'S EDITED VERSION (what they actually sent):
{edited_body}

DIFF SUMMARY:
{diff_summary}

Analyze what the edits reveal about the user's actual voice preferences.
Return ONLY the fields that should change, as a JSON object. Omit unchanged fields.
Allowed fields: tone, avg_length, sign_off, phrases_to_add, phrases_to_remove

Example response:
{{"sign_off": "Thanks,", "phrases_to_add": ["happy to help"], "avg_length": 65}}
"""
```

### Example 4: Dismiss Signal Query for Scoring

```python
# In email_dismiss_tracker.py — helper to inject dismiss signal into score prompt

async def get_dismiss_count(
    db: AsyncSession,
    tenant_id: UUID,
    sender_email: str,
    days: int = 30,
    threshold: int = 3,
) -> int:
    """Count recent dismissals for a sender. Returns 0 if below threshold."""
    result = await db.execute(
        sa_text(
            "SELECT COUNT(*) FROM email_drafts ed "
            "JOIN emails e ON ed.email_id = e.id "
            "WHERE e.tenant_id = :tid "
            "AND e.sender_email = :sender "
            "AND ed.status = 'dismissed' "
            "AND ed.updated_at >= now() - interval ':days days'"
        ).bindparams(tid=tenant_id, sender=sender_email, days=days)
    )
    count = result.scalar_one()
    return count if count >= threshold else 0
```

### Example 5: Dismiss Signal Injection into Scoring Prompt

```python
# In email_scorer._build_score_prompt — add dismiss block when count > 0

if dismiss_count > 0:
    dismiss_block = (
        f"\nDISMISS SIGNAL: User has dismissed {dismiss_count} draft(s) for this "
        f"sender in the past {days} days. Score DOWN: this sender category produces "
        f"drafts the user doesn't want to send."
    )
else:
    dismiss_block = ""

user_message = f"""
CONTEXT AVAILABLE:
{entity_block}
{entries_block}
{dismiss_block}

EMAIL TO SCORE:
...
"""
```

### Example 6: Diff Summary Generation (stdlib, no LLM)

```python
import difflib

def _compute_diff_summary(original: str, edited: str) -> str:
    """Compute a human-readable diff summary from original to edited."""
    original_lines = original.splitlines(keepends=True)
    edited_lines = edited.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        original_lines, edited_lines,
        fromfile="original", tofile="edited", lineterm=""
    ))
    if not diff:
        return "No changes detected."
    # Cap diff at 50 lines to control token usage
    return "\n".join(diff[:50])
```

---

## State of the Art

| Old Approach | Current Approach (Phase 6) | Impact |
|--------------|---------------------------|--------|
| Voice profile fixed at init | Voice profile incrementally updated from edits | Profile improves over time without full re-extraction |
| Scoring ignores user feedback | Dismiss signals inject into scoring prompt | High-dismissal senders score lower automatically |
| Thread priority fixed at first-score time | Thread priority auto-updates on new messages | Priority reflects latest conversation state |

---

## FEED-03 Re-scoring: Existing Implementation Analysis

The requirements say "System re-scores threads when new messages arrive in existing threads." Based on codebase inspection, this is already implemented:

1. **Incremental sync** (`sync_gmail` in `gmail_sync.py`) processes `messagesAdded` history events — this includes new messages in existing threads.
2. **`_score_new_emails()`** is called on the `new_email_ids` list from each sync cycle — this includes the new thread messages.
3. **`get_thread_priority()`** is a read-time MAX query — it automatically incorporates the newly scored message.

**What the plan actually needs for FEED-03 (06-02):**
- Write an integration test that verifies a new message in an existing thread gets scored and the thread priority updates
- Document the FEED-03 behavior in the codebase
- Confirm the daily cap doesn't prevent re-scoring of active threads (it uses `scored_at >= today` which counts re-scores, but since the new message is a different email_id, it's a new score row — doesn't double-count)

---

## Open Questions

1. **Debounce threshold for voice update**
   - What we know: Requirement says "debounced". Count-based gate is the recommended implementation.
   - What's unclear: What minimum edit count produces meaningful signal? Too low = noisy updates; too high = profile never improves.
   - Recommendation: Default to `voice_update_min_edits = 1` (every edit triggers an update) and add the config. The Haiku diff prompt handles cases where the diff is trivial (will return empty JSON if no meaningful change). Adjust based on dogfood feedback.

2. **Dismiss decay window**
   - What we know: 30-day lookback is the initial plan.
   - What's unclear: Should dismissals expire to avoid permanent scoring penalties? A user who dismissed a sender 6 months ago but now wants to re-engage would be penalized.
   - Recommendation: Use 30-day rolling window for dismiss count. This gives natural decay.

3. **Voice update frequency cap**
   - What we know: No cap exists on how often voice profile is updated.
   - What's unclear: If user approves 20 edits in a day, 20 Haiku calls are made.
   - Recommendation: Add a `voice_update_cooldown_minutes: int = 60` config. If last `updated_at` on voice profile is within the cooldown, batch pending edits instead of updating immediately. Low priority for MVP — at $0.00025/call, 20 Haiku calls = $0.005.

4. **Phrases deduplication strategy**
   - What we know: `phrases` is a JSONB array, currently set by full extraction.
   - What's unclear: How to merge new phrases from incremental updates without duplicates or semantic near-duplicates.
   - Recommendation: Simple string deduplication (lowercase comparison) for MVP. Cap at 10. LLM-based semantic dedup is over-engineered for now.

---

## Sources

### Primary (HIGH confidence)
- Direct inspection: `backend/src/flywheel/api/email.py` — approve/edit/dismiss endpoints
- Direct inspection: `backend/src/flywheel/services/gmail_sync.py` — sync loop, `_score_new_emails()`, `voice_profile_init()`, `_extract_voice_profile()`
- Direct inspection: `backend/src/flywheel/engines/email_scorer.py` — scoring pipeline, prompt structure
- Direct inspection: `backend/src/flywheel/engines/email_drafter.py` — draft pipeline, voice profile loading
- Direct inspection: `backend/src/flywheel/db/models.py` — `EmailVoiceProfile`, `EmailDraft`, `EmailScore` schemas
- Direct inspection: `backend/alembic/versions/020_email_models.py` — migration confirming column set
- Direct inspection: `backend/src/flywheel/config.py` — settings patterns
- Python stdlib docs: `difflib` module — `unified_diff`, `ndiff` (stable stdlib since 2.1)

### Secondary (MEDIUM confidence)
- Python FastAPI `BackgroundTasks` docs — fire-and-forget pattern (stable API, confirmed in existing codebase usage at `api/email.py:362`)

---

## Metadata

**Confidence breakdown:**
- Codebase analysis (FEED-03 already works): HIGH — confirmed by reading `gmail_sync.py`
- Voice update pattern (approve-time, BackgroundTasks): HIGH — mirrors existing `trigger_sync` pattern
- Diff analysis approach (difflib + Haiku): HIGH for difflib (stdlib), MEDIUM for Haiku prompt design (no prior test)
- Dismiss signal pattern (query on email_drafts): HIGH — schema confirmed, query straightforward

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (codebase-grounded research; valid until code changes)
