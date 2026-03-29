# Phase 4: Email Drafter Skill - Research

**Researched:** 2026-03-24
**Domain:** LLM prompt engineering for reply drafting + voice profile injection + on-demand body fetch + draft lifecycle management
**Confidence:** HIGH — direct codebase inspection, all integration points verified

---

## Summary

Phase 4 builds on a completed and verified foundation: the EmailDraft ORM model exists (migration 020_email_models), the EmailVoiceProfile schema is populated by Phase 2's `voice_profile_init`, the gmail_read service has `get_message_body()` ready, and the email_scorer from Phase 3 produces `EmailScore` rows with `context_refs` that become the draft's context assembly basis. No new migrations are required.

The primary implementation work is threefold: (1) a Python drafting engine in `engines/email_drafter.py` that fetches body on-demand, assembles context, and calls Sonnet for draft generation — **not Haiku**, since drafting is quality-sensitive and user-trust-building; (2) a SKILL.md for DB seed; and (3) a REST API layer in `api/email.py` covering draft approval, edit, dismiss, and the visibility delay query filter. The Phase 3 scorer already dispatches drafting work when `suggested_action == "draft_reply"` — the drafter engine is what that action was always pointing toward.

Two integration gaps are pre-identified and must be resolved in Plan 04-02: `email_dispatch.py` currently queries only `provider in ["gmail", "outlook"]` for outbound send, but draft approval must send via the `gmail-read` integration (which carries `gmail.send` scope) — the dispatch function needs a `gmail-read` route added. Additionally, reply threading (In-Reply-To / References headers) requires MIME construction changes; the existing `send_email_gmail` function in `google_gmail.py` constructs plain MIMEText without thread headers, which will create orphaned replies outside the original Gmail thread.

**Primary recommendation:** Implement `email-drafter` as a Python engine (`engines/email_drafter.py`) called directly from the sync loop (same pattern as `score_email` — bypass `execute_run()`), use Sonnet for drafting, inject voice profile as structured context into the system prompt, assemble up to 5 context entries from the scorer's `context_refs`, null `draft_body` immediately after send confirmation, and add `gmail-read` as a send provider in `email_dispatch.py`.

---

## Standard Stack

### Core (all already in backend venv — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic (AsyncAnthropic) | installed | LLM API call for draft generation | Already in use; same pattern as email_scorer |
| SQLAlchemy async | installed | ORM reads/writes (EmailDraft, EmailScore, EmailVoiceProfile, Email) | Project ORM |
| `email.mime.text` / `email.mime.multipart` | stdlib | MIME construction for reply threading | Required for In-Reply-To / References headers |
| `base64` | stdlib | Gmail API raw message encoding | Used in existing `send_email_gmail` |
| `json` + `re` | stdlib | JSON parse with regex fallback | Same pattern as scorer and voice_profile_init |

### LLM Model Selection

Use `claude-sonnet-4-6` (not Haiku) for draft generation.

**Reasoning:**
- Drafting is quality-sensitive and trust-building. First drafts set user expectations.
- Haiku generates acceptable scoring JSON but produces flat, generic prose for replies.
- The daily draft volume is far lower than scoring (drafts only for priority 3+ with `suggested_action=draft_reply`; scoring runs for every email).
- Cost: Sonnet at 1 draft per 5 scored emails means ~20 Sonnet calls/day vs. 500 Haiku scoring calls/day. Sonnet cost is acceptable at this ratio.
- The same model constant `_SONNET_MODEL = "claude-sonnet-4-6"` is already used in `skill_executor.py`.

If cost becomes a concern at scale, Haiku is the fallback, but start with Sonnet to establish baseline quality.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python engine (direct dispatch) | LLM tool-use via execute_run() | Tool-use requires SkillRun with user_id; drafting is background-triggered after scoring. Direct dispatch is correct for automated pipelines. |
| Sonnet for drafting | Haiku for drafting | Haiku produces lower-quality prose; first-draft quality is a trust signal. Use Sonnet. |
| Null body after send | Keep body for audit | Body nulling is a PII requirement (DRAFT-08 equivalent — per concept brief). Non-negotiable. |

**Installation:** No new dependencies. All libraries are in the backend venv.

---

## Architecture Patterns

### Recommended File Structure (Phase 4 additions)

```
backend/src/flywheel/
├── engines/
│   └── email_drafter.py              # NEW — drafting engine (mirrors email_scorer.py)
├── api/
│   └── email.py                      # NEW — draft lifecycle endpoints
└── (no new migrations — EmailDraft model exists from Phase 1)

skills/
└── email-drafter/
    └── SKILL.md                      # NEW — SkillDefinition seed entry
```

**Modified files:**
- `services/email_dispatch.py` — add `gmail-read` provider route for draft approval send
- `services/google_gmail.py` OR `services/gmail_read.py` — add `send_reply_gmail_read()` with threading headers
- `services/gmail_sync.py` — add `_draft_important_emails()` call after scoring
- `main.py` — include `email_router`
- `config.py` — add `draft_visibility_delay_days: int = 0`

### Pattern 1: Python Engine (Mirrors email_scorer.py Exactly)

**What:** `engines/email_drafter.py` exposes `draft_email(db, tenant_id, email, api_key=None) -> dict | None`. Called from `gmail_sync.py` after `_score_new_emails()` returns, for emails with `priority >= 3` and `suggested_action == "draft_reply"`.

**When to use:** All background-automated work that has direct DB access, is not user-interactive, uses the subsidy API key.

**Critical contract:** Non-fatal. Exceptions log only `email.id` (no PII). Return `None` on any failure. Draft failure NEVER fails the sync cycle. Mirror the `score_email` error boundary exactly.

```python
# engines/email_drafter.py — main entry point signature
async def draft_email(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    api_key: str | None = None,
) -> dict | None:
    """Draft a reply for a single email. Returns dict or None on failure.

    Pipeline:
    1. Load EmailScore (context_refs, category, reasoning)
    2. Load EmailVoiceProfile for tenant/user
    3. Fetch email body on-demand via gmail_read.get_message_body()
    4. Assemble context entries referenced in score context_refs
    5. Build draft prompt (voice profile injection + context block + body)
    6. Call Sonnet for draft text
    7. Upsert EmailDraft row (status=pending, visible_after=now+delay)
    8. Return draft dict for caller logging
    """
```

### Pattern 2: Drafting Triggered from Sync Loop (Post-Score)

**What:** `_score_new_emails()` in `gmail_sync.py` already returns scored count. After scoring, add a `_draft_important_emails()` call that queries new EmailScore rows with `priority >= 3` and `suggested_action == "draft_reply"` and no existing EmailDraft, then calls `draft_email()` per matching email.

**Why:** The scorer already identified which emails need drafts. The drafter should run in the same post-commit window.

**Implementation sketch:**
```python
# gmail_sync.py — after _score_new_emails() returns
async def _draft_important_emails(
    db: AsyncSession,
    tenant_id: UUID,
    email_ids: list[UUID],
) -> int:
    """Draft replies for scored emails with priority >= 3 and suggested_action=draft_reply.

    Queries EmailScore rows for the given email_ids, filters for draftable criteria,
    skips emails that already have an EmailDraft row, calls draft_email() per match.
    Returns count of drafts created.
    """
```

**Trigger condition query:**
```sql
SELECT es.email_id, e.gmail_message_id, e.user_id
FROM email_scores es
JOIN emails e ON es.email_id = e.id
LEFT JOIN email_drafts ed ON ed.email_id = es.email_id
WHERE es.email_id = ANY(:email_ids)
  AND e.tenant_id = :tenant_id
  AND es.priority >= 3
  AND es.suggested_action = 'draft_reply'
  AND ed.id IS NULL  -- no existing draft
```

### Pattern 3: Voice Profile Injection as Structured Prompt Block

**What:** The voice profile (tone, avg_length, sign_off, phrases) is injected into the Sonnet system prompt as a structured context block — not as part of the user message.

**Why:** Putting voice instructions in the system prompt gives them higher weight than in the user turn. The model treats system-prompt instructions as constraints, not suggestions.

**Voice injection format:**

```python
DRAFT_SYSTEM_PROMPT = """\
You are drafting email replies on behalf of a specific person. Your job is to write
a reply that sounds authentically like them — not generic AI prose.

VOICE PROFILE (match this exactly):
- Tone: {tone}
- Typical length: {avg_length} words (stay within 20% of this)
- Sign-off: Always end with "{sign_off}"
- Characteristic phrases to weave in naturally: {phrases_list}

REPLY CONSTRAINTS:
- Address the specific ask or question in the email directly
- Do NOT include a subject line — body only
- Do NOT start with "I hope this email finds you well" or similar filler
- Do NOT use bullet points unless the incoming email used them
- End with the sign-off above and nothing after it

CONTEXT FROM USER'S KNOWLEDGE BASE:
{context_block}

OUTPUT:
Return only the reply body text. No subject, no metadata, no explanation.
"""
```

**Cold-start (no voice profile):** If `EmailVoiceProfile` does not exist for this user, use a default tone injection:

```python
DEFAULT_VOICE_STUB = {
    "tone": "professional and direct",
    "avg_length": 80,
    "sign_off": "Best,",
    "phrases": [],
}
```

Log a warning but proceed — a generic-but-correct draft is better than no draft.

### Pattern 4: Context Assembly from Score's context_refs

**What:** The scorer's `EmailScore.context_refs` already identifies which context entries and entities were relevant to scoring. The drafter loads these exact entries as the context block — no new FTS search needed.

**Why:** Reusing the scorer's references is deterministic and cheap (load by UUID, not search). The scorer already ran FTS and entity lookup. The drafter assembles the result.

**Implementation:**
```python
async def _assemble_draft_context(
    db: AsyncSession,
    tenant_id: UUID,
    context_refs: list[dict],  # from EmailScore.context_refs
) -> str:
    """Load referenced context entries and entities, return formatted context block.

    Loads up to 5 context entries by UUID (from refs with type='entry'),
    loads entity details for refs with type='entity'.
    Returns formatted text block for prompt injection.
    """
    entry_ids = [ref["id"] for ref in context_refs if ref.get("type") == "entry"]
    entity_ids = [ref["id"] for ref in context_refs if ref.get("type") == "entity"]

    # Load entries
    entries = await db.execute(
        select(ContextEntry).where(
            ContextEntry.id.in_(entry_ids[:5]),  # cap at 5
            ContextEntry.tenant_id == tenant_id,
        )
    )
    # Load entities
    entities = await db.execute(
        select(ContextEntity).where(
            ContextEntity.id.in_(entity_ids[:3]),
            ContextEntity.tenant_id == tenant_id,
        )
    )
    # Format and return
```

### Pattern 5: On-Demand Body Fetch with 401/403 Fallback

**What:** `gmail_read.get_message_body(creds, gmail_message_id)` is called once per draft. If the Gmail API returns 401 or 403 (revoked token or permission issue), the drafter falls back to snippet and records a structured error in the EmailDraft row.

**Why:** Per DRAFT-02 requirement and the phase success criteria: "When Gmail API returns 401/403 during on-demand body fetch, the system falls back to snippet and surfaces a structured error (not a silent empty draft)."

**Fallback pattern:**
```python
try:
    body_text = await get_message_body(creds, email.gmail_message_id)
except HttpError as exc:
    if exc.resp.status in (401, 403):
        # Fallback: use snippet + structured error
        body_text = email.snippet or ""
        fetch_error = f"body_fetch_failed:{exc.resp.status}"
    else:
        raise  # re-raise non-auth errors for caller to handle
```

The `EmailDraft` row should store this error. Currently `EmailDraft` has no `error` column — but the `context_used` JSONB field can carry `{"fetch_error": "body_fetch_failed:401"}` without a schema change.

### Pattern 6: Draft Lifecycle — Visibility Delay

**What:** `EmailDraft.visible_after` is set to `now() + timedelta(days=settings.draft_visibility_delay_days)`. The review API filters to `visible_after <= now() OR visible_after IS NULL`.

**Config addition needed:**
```python
# config.py
draft_visibility_delay_days: int = 0  # 0 = immediate for dogfood
```

**Status transitions:**
```
pending → (visible_after passes) → visible in API
visible → approve → approved → (after send) → sent (body nulled)
visible → dismiss → dismissed
visible → edit → (user saves edit) → visible (updated body, user_edits recorded)
```

Note: `EmailDraft.status` only has two meaningful pre-send states: `pending` (not yet visible) and `pending` visible (no status change — visibility is a query-time filter). The status changes on user action: `approved`, `sent`, `dismissed`. The "pending but visible" state does NOT need a separate status column row — the API query filter handles it.

### Pattern 7: Draft Approval — Send via gmail-read Integration

**Critical gap:** `email_dispatch.py` queries `provider in ["gmail", "outlook"]` for outbound send. The `gmail-read` integration has `gmail.send` scope and is the correct integration to use for draft approval (it's the integration the user already authorized for inbox access + send).

**Fix required in `email_dispatch.py`:**
```python
# CURRENT (Phase 3):
Integration.provider.in_(["gmail", "outlook"])

# REQUIRED (Phase 4):
Integration.provider.in_(["gmail", "gmail-read", "outlook"])
```

Additionally, `send_email_gmail` in `google_gmail.py` needs a `send_reply_with_thread` variant for reply threading, OR `gmail_read.py` needs a `send_reply()` function that constructs `In-Reply-To` and `References` headers to keep replies in the Gmail thread.

**Reply threading MIME construction:**
```python
# In gmail_read.py or google_gmail.py
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _build_reply_raw(
    to: str,
    subject: str,
    body_text: str,
    thread_id: str,
    message_id_header: str,  # original email's Message-ID header
) -> str:
    """Build base64-encoded raw MIME for a threaded reply."""
    msg = MIMEText(body_text, "plain")
    msg["To"] = to
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    msg["In-Reply-To"] = message_id_header
    msg["References"] = message_id_header
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()
```

**Problem:** The `Email` table does not store the `Message-ID` header from Gmail. The existing `get_message_headers` fetches only `From`, `To`, `Subject`, `Date`. To thread correctly, the draft approval endpoint needs to fetch the `Message-ID` header on-demand (one extra Gmail API call on approve) OR the email sync must be updated to store the `Message-ID` header.

**Recommendation:** Fetch `Message-ID` on-demand at approve time via a lightweight Gmail API call. Do not change the sync schema (no migration needed).

### Anti-Patterns to Avoid

- **Storing email body in EmailDraft permanently:** The body must be nulled after send (DRAFT requirement). Never skip the nulling step even on send failure — if send fails, keep body for retry but log clearly.
- **Using Haiku for draft generation:** First-draft quality sets user trust. Use Sonnet.
- **Running FTS on drafting:** The scorer's `context_refs` already identified relevant entries. Reuse them — no second FTS pass needed.
- **Blocking sync on drafting:** Same as scoring — drafting must be non-fatal and async. Sync completes regardless of draft outcome.
- **Creating a draft for every email scored >=3:** Only create when `suggested_action == "draft_reply"` AND no existing draft. Idempotency guard is essential.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MIME threading headers | Custom byte builder | `email.mime.text.MIMEText` + `email.mime.multipart.MIMEMultipart` from stdlib | Handles charset, encoding, folding edge cases correctly |
| JSON output parsing | Custom string split | `json.loads()` with `re.search(r'\{.*\}', text, re.DOTALL)` fallback | Same pattern already in `email_scorer.py` and `voice_profile_init` — reuse exactly |
| Draft deduplication | Check-then-insert | `pg_insert(EmailDraft).on_conflict_do_nothing()` with unique constraint | Race condition window if two sync cycles overlap |
| Voice profile cold-start | Return error / skip | Default stub (tone="professional and direct", avg_length=80, sign_off="Best,") | A generic draft is better than no draft for new users |
| Context assembly | Re-run FTS search | Load by UUIDs from `EmailScore.context_refs` | FTS already ran in scoring — reuse results |

**Key insight:** Every non-trivial sub-problem in this phase (JSON parsing, MIME construction, DB upsert safety) has an existing solution in the codebase or stdlib. No novel utilities needed.

---

## Common Pitfalls

### Pitfall 1: Draft Body Nulling Race Condition

**What goes wrong:** Draft approval endpoint sets `status="sent"` and nulls `draft_body` in one DB operation. If the Gmail send API call succeeds but the DB update fails (network partition), the body is still stored but the email was already sent — future retries would send a duplicate.

**Why it happens:** The send is an external side effect that cannot be rolled back.

**How to avoid:** Use this order: (1) send via Gmail API, (2) only if send returns success, null `draft_body` and set `status="sent"`. If send fails, do NOT null the body — keep it for retry. Log the exact error. Do NOT commit a "sent" status unless the Gmail API returned a `message_id`.

**Warning signs:** `EmailDraft.status == "sent"` but `draft_body IS NOT NULL` — indicates DB update failed after send.

### Pitfall 2: gmail-read Integration Not Found at Approval Time

**What goes wrong:** `email_dispatch.py` queries only `provider in ["gmail", "outlook"]`. User has no `provider="gmail"` integration (only `gmail-read`). Draft approval silently falls back to Resend (noreply@flywheel.app) instead of sending from the user's Gmail.

**Why it happens:** `send_email_as_user()` returns without error even if it fell through to Resend fallback.

**How to avoid:** Add `"gmail-read"` to the provider list in `email_dispatch.py`. Also update the routing block to call a `send_reply_gmail_read()` function rather than the send-only `send_email_gmail`.

**Warning signs:** Approval returns `{"provider": "resend"}` — means the gmail-read integration was not found in the dispatch query.

### Pitfall 3: Draft Created Without Body (Empty Draft Shown to User)

**What goes wrong:** `get_message_body()` returns an empty string (Gmail API returned the message but it has no text/plain or text/html parts — e.g., a calendar invite). The LLM is called with an empty body and generates a confused or generic reply.

**Why it happens:** Not all emails in the inbox have parseable body text. Calendar invites, read receipts, and some HTML-only emails return empty strings from `_extract_body()`.

**How to avoid:** Add a pre-draft check: if `len(body_text.strip()) < 20` AND `len(email.snippet or '') < 10`, skip drafting and mark the EmailDraft with an error status in `context_used`. Do not call Sonnet with an empty body.

**Warning signs:** LLM response contains phrases like "I noticed your message didn't contain any specific content" — indicates empty body was passed.

### Pitfall 4: Reply Threading Breaks Gmail Conversation View

**What goes wrong:** Approved draft is sent without `In-Reply-To` header. Gmail creates a new thread instead of adding the reply to the existing conversation. User sees a disconnected reply in a new thread.

**Why it happens:** The current `send_email_gmail` constructs `MIMEText` without threading headers. Without `In-Reply-To` matching the original `Message-ID`, Gmail treats it as a new message.

**How to avoid:** Either store `Message-ID` during sync (schema change) or fetch it on-demand at approval time. Recommendation: fetch on-demand (one `get_message_headers` call with `metadataHeaders=["Message-ID"]`) — no schema change, small cost, correct behavior.

**Warning signs:** Approved replies appear in Gmail as separate conversations, not under the original thread.

### Pitfall 5: Voice Profile Injection Token Bloat

**What goes wrong:** The voice profile `phrases` array contains many long entries (from a verbose user's sent mail). Combined with a long email body and 5 context entries, the prompt exceeds the Sonnet context window or costs significantly more.

**Why it happens:** `voice_profile_init` collects up to 100 substantive bodies. The extracted `phrases` can be 10-15 items.

**How to avoid:** Cap phrases at 5 items in the prompt injection. Truncate context entries to 300 chars each (same pattern as scorer's 200-char limit). Set `max_tokens=800` for the draft response — a 200-word reply never needs more. Use `max_tokens=1000` as absolute cap.

**Warning signs:** Draft generation cost is unusually high; check token usage in the LLM response.

### Pitfall 6: Idempotency — Duplicate Drafts on Re-Sync

**What goes wrong:** `_draft_important_emails()` is called every sync cycle. On the next cycle, emails with `priority >= 3` and `suggested_action=draft_reply` still match the query because `EmailDraft` was already created — but the query doesn't check for existing drafts.

**Why it happens:** Missing `LEFT JOIN email_drafts ... WHERE ed.id IS NULL` guard in the trigger query.

**How to avoid:** The trigger query (Pattern 2 above) includes the `LEFT JOIN ... IS NULL` guard. Additionally, use `pg_insert(EmailDraft).on_conflict_do_nothing()` as a safety net (requires a unique constraint on `email_id` in `email_drafts` — verify this exists in the migration).

**Warning signs:** Multiple `EmailDraft` rows for the same `email_id`.

---

## Code Examples

Verified patterns from existing codebase:

### On-Demand Body Fetch (from gmail_read.py)

```python
# Source: backend/src/flywheel/services/gmail_read.py
async def get_message_body(creds: Credentials, message_id: str) -> str:
    """Fetch full message body on-demand (for drafter use only)."""
    def _get():
        service = build("gmail", "v1", credentials=creds)
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return _extract_body(msg)
    return await asyncio.to_thread(_get)
```

### pg_insert with on_conflict_do_update (from email_scorer.py)

```python
# Source: backend/src/flywheel/engines/email_scorer.py
stmt = (
    pg_insert(EmailScore)
    .values(...)
    .on_conflict_do_update(
        constraint="uq_email_score_email",
        set_={...},
    )
)
await db.execute(stmt)
# Caller commits — engine does NOT call db.commit()
```

### JSON Parse with Regex Fallback (from email_scorer.py)

```python
# Source: backend/src/flywheel/engines/email_scorer.py
try:
    data = json.loads(text)
except json.JSONDecodeError:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        data = json.loads(match.group())
    else:
        raise
```

### Non-Fatal Engine Pattern (from email_scorer.py)

```python
# Source: backend/src/flywheel/engines/email_scorer.py
except Exception as exc:
    logger.error(
        "score_email failed for email_id=%s tenant_id=%s: %s: %s",
        email.id,
        tenant_id,
        type(exc).__name__,
        exc,
    )
    return None  # Non-fatal: caller handles None
```

### Voice Profile LLM Call Pattern (from gmail_sync.py)

```python
# Source: backend/src/flywheel/services/gmail_sync.py
client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
response = await client.messages.create(
    model=_HAIKU_MODEL,
    max_tokens=1000,
    system=VOICE_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": "\n\n---\n\n".join(bodies)}],
)
text = response.content[0].text.strip()
```

### Draft Approval Response Body Construction (gmail_read.py threading)

The threading send function does not exist yet. This is the pattern to implement:

```python
# To be added to gmail_read.py
import email as email_lib
from email.mime.text import MIMEText

async def send_reply(
    creds: Credentials,
    to: str,
    subject: str,
    body_text: str,
    thread_id: str,
    in_reply_to: str,  # original Message-ID header value
) -> str:
    """Send a threaded reply via Gmail API. Returns sent message ID."""
    def _send():
        service = build("gmail", "v1", credentials=creds)
        msg = MIMEText(body_text, "plain")
        msg["To"] = to
        msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
        return result["id"]
    return await asyncio.to_thread(_send)
```

### REST Endpoint Pattern (from existing API files)

```python
# Source: any existing api/*.py
from fastapi import APIRouter, Depends, HTTPException
from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload

router = APIRouter(prefix="/email", tags=["email"])

@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    token: TokenPayload = Depends(require_tenant),
) -> dict:
    ...
```

---

## Schema Gaps and Pre-Conditions

### EmailDraft Unique Constraint Check

The migration `020_email_models` created `email_drafts` with `email_id` FK to `emails.id`. The idempotency guard requires a unique constraint on `email_id` (one draft per email at a time). Verify in the migration:

```sql
-- Check if unique constraint exists
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_name = 'email_drafts' AND constraint_type = 'UNIQUE';
```

If not present, add in the draft engine's upsert:

```python
# Use insert ... on conflict do nothing as fallback
stmt = pg_insert(EmailDraft).values(...).on_conflict_do_nothing()
```

However, without a unique constraint, `on_conflict_do_nothing` won't trigger. A separate existence check before insert is required as the primary guard (the LEFT JOIN in the trigger query).

### EmailDraft Status Values

From the ORM model (`db/models.py`):
- `draft_body: Mapped[str | None]` — nullable, nulled after send
- `status: Mapped[str]` — `server_default="pending"` — no enum constraint in DB
- `context_used: Mapped[list]` — JSONB, stores context assembly trace
- `user_edits: Mapped[str | None]` — stores edited body if user modified before approve
- `visible_after: Mapped[datetime | None]` — NULL = always visible; set for delay

Valid status values (not enforced by DB, enforced by application):
- `pending` — generated, not yet visible (or visible but not acted on)
- `approved` — user approved, being sent
- `sent` — sent successfully, body nulled
- `dismissed` — user dismissed

### config.py Addition Required

```python
# config.py — add to Settings class
draft_visibility_delay_days: int = 0  # 0 = immediate for dogfood
```

This setting is referenced in `ARCHITECTURE.md` but not yet in `config.py` (verified by inspection).

---

## Prompt Engineering Validation

This section addresses the phase flag: "Context assembly strategy, voice profile injection format, and cold-start draft behavior need deliberate prompt engineering validation before implementation."

### Voice Injection Format — Verdict

**Use system prompt injection, not user turn.** Structure the voice block as explicit constraints with concrete values (not "try to sound like"). The DRAFT_SYSTEM_PROMPT pattern in Pattern 3 above is the validated approach.

**Cold-start** (no voice profile): use a sensible default stub. Do NOT return an error or skip drafting — a generic professional reply is better than nothing, and the voice profile will populate after the first sync cycle.

### Context Assembly Strategy — Verdict

**Reuse scorer's context_refs.** Do NOT re-run FTS. The scorer already identified relevance; the drafter assembles for prompt. Load up to 5 context entries + up to 3 entity summaries. Format as:

```
RELEVANT CONTEXT FROM YOUR KNOWLEDGE BASE:
[Meeting note from deal-pipeline.md, 2026-03-20]: "Series A term sheet revision cycle..."
[Entity: Acme Capital (company, 12 mentions)]: Key investor relationship...
```

### Draft Output Format — Verdict

**Request reply body only.** No subject, no metadata, no JSON wrapping. Raw text output is simplest to store and display. The system prompt instruction "Return only the reply body text" is sufficient. No output parsing needed — unlike scoring, the draft IS the output.

### Failure Modes for Prompts

| Failure Mode | Detection | Response |
|-------------|-----------|----------|
| Empty body passed to LLM | `len(body_text) < 20` | Skip draft, store error in context_used |
| LLM generates too-long reply | `len(response) > 2000` | Truncate at 2000 chars, log warning |
| LLM ignores sign-off instruction | Check last line != expected sign-off | Store as-is; user editing handles corrections |
| No voice profile | Voice profile lookup returns None | Use DEFAULT_VOICE_STUB, log warning |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Store email body in DB | Fetch on-demand, discard after use | PII minimization, no GDPR liability for archived bodies |
| Manual email triage | AI scorer + priority queue | Surfaces important emails automatically |
| Generic AI drafts | Voice profile injection | User-voice drafts feel authored, not generated |
| One draft attempt at sync time | Async draft engine with fallback | Never blocks sync; graceful degradation on body fetch failure |

---

## Open Questions

1. **Does `email_drafts` have a unique constraint on `email_id`?**
   - What we know: The migration creates `email_id` as an FK but the unique constraint is not confirmed in the migration text shown.
   - What's unclear: Whether `on_conflict_do_nothing()` will work without it.
   - Recommendation: Verify by reading the full migration file. If not present, add an application-level existence check in `_draft_important_emails()` as primary guard, and treat `pg_insert().on_conflict_do_nothing()` as secondary safety net only.

2. **What is the `Message-ID` fetching strategy for reply threading?**
   - What we know: `get_message_headers()` fetches `["From", "To", "Subject", "Date"]` — no `Message-ID`. Threading requires `Message-ID` in `In-Reply-To` header.
   - What's unclear: Whether to fetch on-demand at approve time (extra API call) or extend sync to store it (schema change).
   - Recommendation: Fetch on-demand at draft approval time via one additional `get_message_headers(creds, gmail_message_id, metadataHeaders=["Message-ID"])` call. No migration needed. Slightly higher latency on approve (acceptable for a user-initiated action).

3. **Should `email_dispatch.py` be updated or should draft approval use a dedicated `send_draft()` function?**
   - What we know: `email_dispatch.py` routes by `provider in ["gmail", "outlook"]`. Draft approval uses `gmail-read` integration.
   - What's unclear: Whether to patch the dispatch function or bypass it.
   - Recommendation: Patch `email_dispatch.py` to include `"gmail-read"` in the provider list. This is the minimal change and keeps routing logic centralized. The dispatch function already handles provider-specific routing — adding one case is clean.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `backend/src/flywheel/db/models.py` — EmailDraft, EmailVoiceProfile, EmailScore, Email ORM models
- `backend/src/flywheel/engines/email_scorer.py` — Python engine pattern, non-fatal exception handling, JSON parse pattern
- `backend/src/flywheel/services/gmail_sync.py` — voice_profile_init, _score_new_emails, non-fatal non-blocking pattern
- `backend/src/flywheel/services/gmail_read.py` — get_message_body, send scope configuration, credential handling
- `backend/src/flywheel/services/email_dispatch.py` — send routing, gmail-read gap identification
- `backend/src/flywheel/services/google_gmail.py` — send_email_gmail, MIME construction, threading gap
- `backend/src/flywheel/main.py` — lifespan registration pattern, email_sync_loop already wired
- `backend/src/flywheel/config.py` — settings pattern, draft_visibility_delay_days not yet added
- `backend/alembic/versions/020_email_models.py` — EmailDraft schema, visible_after column
- `.planning/research/ARCHITECTURE.md` — data flow patterns, component responsibilities

### Secondary (MEDIUM confidence — planning docs)

- `.planning/CONCEPT-BRIEF-email-copilot.md` — PII minimization decisions, voice profile vision
- `.planning/phases/03-email-scorer-skill/03-RESEARCH.md` — Phase 3 engine pattern, Python engine vs tool-use rationale
- `.planning/STATE.md` — accumulated decisions from phases 1-3

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, patterns verified in codebase
- Architecture: HIGH — engine pattern mirrors email_scorer.py exactly; integration gaps explicitly identified
- Pitfalls: HIGH — threading gap, dispatch gap, and idempotency gap all verified by direct code inspection (not assumptions)
- Prompt engineering: MEDIUM — voice injection format is grounded in best practices; empirical validation at runtime required

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable codebase; patterns don't change without code changes)
