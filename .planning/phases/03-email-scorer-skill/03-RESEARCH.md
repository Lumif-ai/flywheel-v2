# Phase 3: Email Scorer Skill - Research

**Researched:** 2026-03-24
**Domain:** LLM scoring prompt engineering + Flywheel Python engine pattern + context store integration
**Confidence:** HIGH (based on direct codebase inspection)

---

## Summary

Phase 3 wires together three systems that already exist: the Email/EmailScore ORM models (Phase 1), the sync loop (Phase 2), and the skill executor (existing production code). The primary implementation work is (1) writing a Python scoring engine in `backend/src/flywheel/engines/email_scorer.py`, (2) creating a SKILL.md for the `email-scorer` skill in `skills/email-scorer/SKILL.md`, (3) adding a dispatch case for `email-scorer` in `skill_executor.py`, and (4) integrating scorer invocation into `gmail_sync.py` after each email upsert.

The highest-risk open question — confirmed as such by the phase flag — is the **multi-signal scoring prompt**. Flywheel scores emails using only sender + subject + snippet (no body), requiring the prompt to reason under information scarcity with aggressive escalation bias (false-negative far worse than false-positive, per SCORE-09). The prompt must output structured JSON and produce traceable context references. Research confirms this calls for a **structured JSON output with chain-of-thought reasoning field**, not free-text reasoning. Claude Haiku is already in use in the codebase (`gmail_sync.py` line 394) for voice profile extraction; the scorer should follow the same model/parse pattern.

The scoring engine is a **Python engine** (like `company_intel.py`), not an LLM tool-use skill (like `meeting-prep`). The reason: the scorer is triggered programmatically by the sync loop for every email — it needs direct DB access, upsert behavior, and cannot be driven by user text input. The `_execute_with_tools` path is for user-interactive skills; the Python engine path (`_execute_company_intel` pattern) is for background automation. The scorer follows the `company_intel.py` pattern exactly: async function registered in `skill_executor.py`, dispatched by skill name.

**Primary recommendation:** Implement `email-scorer` as a Python engine (`engines/email_scorer.py`) dispatched from `skill_executor.py`, called directly from `gmail_sync.py` after upsert, using Haiku for per-email scoring with structured JSON output and a clear scoring rubric covering sender entity weight, urgency signals, thread staleness, and label analysis.

---

## Standard Stack

### Core (all already in backend venv)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic (AsyncAnthropic) | installed | LLM API call for scoring | Already in use; `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` in gmail_sync.py |
| SQLAlchemy async | installed | DB reads (context_entities lookup, EmailScore upsert) | Project ORM |
| PostgreSQL full-text search | n/a | context_entries full-text query (search_vector TSVECTOR column) | Already indexed, used in context_tools.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` stdlib | n/a | Parse structured JSON from Haiku response | Scorer LLM always returns JSON |
| `re` stdlib | n/a | Regex fallback when json.loads fails | Same pattern as voice_profile_init |
| `flywheel.db.session.get_session_factory` | internal | Tenant-scoped DB sessions | Scoring engine needs tenant isolation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python engine (direct DB) | LLM tool-use skill | Tool-use path requires SkillRun record + user_id + API key; scoring is background, system-initiated. Python engine is the right pattern for automated pipeline steps. |
| Haiku for scoring | Sonnet | Haiku is 30x cheaper; scoring 200 emails/day at Haiku cost is negligible. Sonnet overkill for snippet-level scoring. |
| LLM JSON output | Rule-based scoring | Rule-based cannot capture semantic urgency ("Series A closing" isn't a keyword, it's context). LLM is required to leverage context store. |

**Installation:** No new dependencies needed. All required libraries are in the backend venv.

---

## Architecture Patterns

### Pattern 1: Python Engine Registration (canonical codebase pattern)

The `company-intel` and `meeting-prep` skills are Python engines. The dispatcher in `skill_executor.py` (lines 521-548) checks `engine_module` from the DB or uses hardcoded `is_company_intel` / `is_meeting_prep` guards. For the email scorer, add a parallel `is_email_scorer` guard.

**What:** Python async function with signature `(api_key, emails, factory, run_id, tenant_id, user_id) -> (output, token_usage, tool_calls)`. Dispatched from `execute_run()`.

**When to use:** Any background/automated skill that writes to DB directly, is not user-interactive, and doesn't need the tool-use loop.

**Dispatch location:** `skill_executor.py` `execute_run()`, inside the `try:` block around line 521:

```python
# Source: /backend/src/flywheel/services/skill_executor.py lines 521-548
is_email_scorer = run.skill_name == "email-scorer"
if is_email_scorer:
    output, token_usage, tool_calls = await _execute_email_scorer(
        api_key=api_key,
        input_text=run.input_text or "",
        factory=factory,
        run_id=run.id,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
    )
```

### Pattern 2: SkillRun Creation from Sync Loop

The sync loop (`gmail_sync.py`) does not currently create SkillRun records. For Phase 3, the scorer integration in `_sync_one_integration` (line 316) should create a SkillRun with `skill_name="email-scorer"` and `input_text` containing the IDs of emails needing scores, then call `execute_run()`.

**Key constraint:** The sync loop uses the subsidy API key (`settings.flywheel_subsidy_api_key`) since there is no user-interactive API key prompt. Precedent: `voice_profile_init` uses `settings.flywheel_subsidy_api_key` directly (line 455).

**Tenant isolation:** The scorer engine must set `app.tenant_id` via `SELECT set_config(...)` before any DB query. Precedent: every tenant-scoped query in `skill_executor.py` does this.

### Pattern 3: Structured JSON Scoring Output

The scorer LLM call returns JSON for reliable parsing. Same pattern as `voice_profile_init` in `gmail_sync.py` (lines 462-471):

```python
# Source: /backend/src/flywheel/services/gmail_sync.py lines 462-471
text = response.content[0].text.strip()
try:
    return json.loads(text)
except json.JSONDecodeError:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise
```

The scorer should return one JSON object per email:
```json
{
  "priority": 4,
  "category": "deal_related",
  "suggested_action": "draft_reply",
  "reasoning": "Sender matches context entity 'Acme Corp' (Series A deal). Subject implies urgency around closing timeline.",
  "context_refs": [
    {"type": "entity", "id": "...", "name": "Acme Corp"},
    {"type": "entry", "file": "deal-pipeline.md", "snippet": "Series A closing..."}
  ]
}
```

### Pattern 4: Sender Entity Lookup (pre-LLM enrichment)

Before calling the LLM, the Python engine should look up `sender_email` in `context_entities`. This gives the LLM concrete entity metadata (name, mention_count, entity_type) to include in the prompt, rather than asking the LLM to guess from the email address alone.

```python
# Query pattern (based on ContextEntity model in models.py lines 507-544)
result = await session.execute(
    select(ContextEntity).where(
        ContextEntity.tenant_id == tenant_id,
        or_(
            ContextEntity.name.ilike(f"%{domain}%"),
            ContextEntity.aliases.contains([sender_email]),
        )
    )
)
entity = result.scalar_one_or_none()
```

The entity's `mention_count`, `entity_type` (person vs company), and `last_seen_at` are signals that directly inform priority.

### Pattern 5: Context Store Full-Text Search for Topic Relevance

For SCORE-03, query `context_entries.search_vector` using PostgreSQL `to_tsquery`. The `search_vector` is a `GENERATED ALWAYS AS` column on `context_entries` (models.py lines 204-211):

```python
# Source: models.py - search_vector is TSVECTOR computed from detail || content
result = await session.execute(
    select(ContextEntry)
    .where(
        ContextEntry.tenant_id == tenant_id,
        ContextEntry.deleted_at.is_(None),
        sa_text("search_vector @@ to_tsquery('english', :q)").bindparams(q=tsquery),
    )
    .order_by(sa_text("ts_rank(search_vector, to_tsquery('english', :q)) DESC").bindparams(q=tsquery))
    .limit(3)
)
```

The tsquery should be built from subject keywords. For subjects like "Re: Series A term sheet", extract "Series A term sheet" and convert to `'series' & 'a' & 'term' & 'sheet'`.

### Anti-Patterns to Avoid

- **Using `_execute_with_tools` for the scorer:** That path requires a SkillRun with `user_id`, uses the tool-use loop, and is designed for interactive skills. The scorer is a background engine.
- **Scoring with body text:** The Email model has no body field (no_body is an explicit architecture decision). The scorer must work only with sender + subject + snippet + labels. Do not call `get_message_body()` during scoring.
- **Thread average scoring:** SCORE-07 mandates thread priority = highest unhandled message score. Never average. Update `thread_priority` on the Thread model (or compute it at read time from the max score in the thread).
- **LLM scoring all emails in one batch prompt:** Batch too large creates hallucination risk and makes per-email context lookups impractical. Score individually or in small batches (5-10) with per-email context pre-fetched.
- **Skipping context lookup when context_entities is empty:** If no entities exist yet, the scorer must still run and produce a score based on heuristics. Empty context is a valid state, not an error.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tenant session management | Custom session factory | `get_session_factory()` + `tenant_session()` from `db/session.py` | RLS, connection pooling |
| JSON parse with fallback | Custom regex parser | `json.loads()` + `re.search(r"\{.*\}")` fallback (gmail_sync.py pattern) | Handles Haiku's rare markdown wrapping |
| Full-text search | Custom keyword match | PostgreSQL `search_vector @@ to_tsquery()` | Already indexed, handles stemming |
| Upsert with conflict | INSERT + UPDATE | `pg_insert(...).on_conflict_do_update(constraint="uq_email_score_email", ...)` | EmailScore has unique constraint on `email_id` |
| Event logging | Direct DB writes | `_append_event_atomic(factory, run_id, {...})` | Atomic JSON array append |
| Subsidy key for background jobs | Env var lookup | `settings.flywheel_subsidy_api_key` | Same pattern as voice_profile_init |

**Key insight:** The email scorer's DB layer is entirely covered by existing patterns. The only genuinely new work is the scoring prompt and the Python engine function signature.

---

## Scorer Prompt Engineering (HIGH-RISK OPEN DESIGN)

This is the flagged uncharted area. The following is the research output on how to structure the scoring prompt.

### The Core Challenge

Scoring inputs are extremely limited: sender address, sender name (optional), subject line, 100-char snippet, and Gmail label list. There is no body. The LLM must produce a defensible 1-5 priority score with reasoning that references specific context store findings. Two failure modes are unacceptable:
- **False negative (missing a critical email):** Explicitly noted as 1000x worse than false positive (SCORE-09)
- **Fabricated context references:** Claiming a context match that doesn't exist destroys trust

### Recommended Prompt Architecture

**Pre-LLM enrichment (Python layer — do before the LLM call):**
1. Look up `sender_email` domain and full address in `context_entities` → get entity name, type, mention_count
2. Run subject keywords through `search_vector` FTS → get top 3 matching `context_entries` with file_name and content snippets
3. Pass both lookups as structured context to the LLM prompt

**System prompt structure:**

```
You are an email priority scorer for a busy professional. Score emails on a 1-5 scale:
5 = CRITICAL — requires same-day action, involves known key contact or active deal
4 = IMPORTANT — requires response within 24h, from known contact or relevant topic
3 = NORMAL — warrants attention, no urgency signal
2 = LOW — FYI, no action needed
1 = NOISE — marketing, auto-notifications, or clearly irrelevant

SCORING BIAS: When uncertain, score UP. A false positive (overscoring) is acceptable.
A false negative (underscoring something critical) is a critical product failure.

CATEGORIES: meeting_followup | deal_related | action_required | informational | marketing | personal
SUGGESTED ACTIONS: notify | draft_reply | file | archive

CONTEXT AVAILABLE (pre-fetched from knowledge base):
- Sender entity: {entity_json_or_null}
- Matching context entries: {context_entries_json_or_empty_array}

EMAIL TO SCORE:
From: {sender_name} <{sender_email}>
Subject: {subject}
Snippet: {snippet}
Labels: {labels}

Return ONLY a JSON object with these exact fields:
{
  "priority": <1-5 integer>,
  "category": <one of the categories above>,
  "suggested_action": <one of the actions above>,
  "reasoning": <1-3 sentence explanation citing specific context matches if present>,
  "context_refs": <array of {type, id?, name?, file?, snippet?} objects for each context item cited>
}
```

### Signal Hierarchy (priority rules to embed in prompt)

The following heuristic rules should be embedded as examples in the system prompt to calibrate the model:

| Signal | Score Boost | Evidence |
|--------|-------------|----------|
| Sender in `context_entities` with `mention_count >= 5` | +2 | High-frequency contact = important relationship |
| Sender in `context_entities` with `entity_type="company"` and matching context entries | +2 | Active deal/client |
| Subject keyword matches context entry in `deal-pipeline.md` or similar | +2 | Directly relevant to active work |
| Label includes `IMPORTANT` | +1 | Gmail user-flagged |
| Label does NOT include `UNREAD` (already read) | Consider -1 | User already saw it |
| Label includes `CATEGORY_PROMOTIONS` or `CATEGORY_UPDATES` | -2 baseline | Auto-classified marketing |
| Snippet contains urgency words: "urgent", "deadline", "ASAP", "by [date]", "closing" | +1 | Keyword urgency signal |
| Thread staleness: last message > 7 days, `is_replied=False` | +1 | Unhandled thread |
| Sender domain matches tenant's own company domain | -1 | Internal email, likely lower priority |

### Thread Staleness Signal

The Email model has `is_replied` (boolean). For SCORE-07/SCORE-08, the scorer should:
1. Accept `is_replied` and `received_at` as input fields
2. Compute thread staleness: if the thread has any `is_replied=False` messages older than 7 days, flag as stale
3. Include staleness as a context signal in the prompt

### Prompt Calibration — Few-Shot Examples

The system prompt MUST include 2-3 few-shot examples to anchor scores. Without examples, Haiku tends to cluster scores around 3 (neutral). Examples should demonstrate:
- Score 5: Known entity + subject keyword matches active context entry + urgency word
- Score 2: Marketing/promotions label + unknown sender + generic subject
- Score 4: Known entity + reply requested but no keyword urgency

The few-shot examples should be hardcoded realistic samples, not drawn from the tenant's data (no privacy exposure).

### Context Reference Traceability (SCORE-06)

The `context_refs` field in `EmailScore` (type JSONB, default `[]`) stores the entities and entries the LLM cited. The Python engine should:
1. Pre-fetch entities and entries with their IDs before calling the LLM
2. Pass IDs in the prompt context
3. Validate that cited IDs exist in the pre-fetched set (don't trust IDs the LLM fabricates)
4. Store validated refs in `context_refs`

This prevents hallucinated references while still producing traceable reasoning.

---

## Common Pitfalls

### Pitfall 1: Calling `execute_run()` for the scorer with no `user_id`

**What goes wrong:** `execute_run()` calls `_get_user_api_key(factory, run.user_id)`, which will return None if `user_id` is None. The fallback to subsidy key only applies to `company-intel` and `meeting-prep` (hardcoded in lines 456-457).
**Why it happens:** The sync loop has no interactive user — it's a background process.
**How to avoid:** Either extend the subsidy key fallback to include `email-scorer`, OR call the scoring engine directly (bypassing `execute_run()`) from the sync loop using `settings.flywheel_subsidy_api_key` directly, as `voice_profile_init` does.
**Recommended:** Bypass `execute_run()` for automated scoring; call `score_emails()` (the engine function) directly from `_sync_one_integration`. Create a SkillRun record for observability but don't route through `execute_run()`.

### Pitfall 2: Scoring with the wrong tenant session

**What goes wrong:** If `set_config('app.tenant_id', ...)` is not called before querying `context_entities` or `context_entries`, PostgreSQL RLS will block the query or return rows from other tenants.
**Why it happens:** RLS is enforced at the Postgres level, not the application level.
**How to avoid:** All scorer DB operations must use `async with tenant_session(factory, str(tenant_id), str(user_id)) as db:` or manually call `set_config` via `sa_text`. Reference: every context query in `skill_executor.py`.

### Pitfall 3: `search_vector` tsquery syntax errors

**What goes wrong:** PostgreSQL `to_tsquery()` raises a syntax error if the input contains special characters (email addresses, URLs, commas in subjects).
**Why it happens:** `to_tsquery` is strict — `"hello, world"` fails; `"hello" & "world"` works.
**How to avoid:** Use `plainto_tsquery()` instead of `to_tsquery()` for user-derived input. `plainto_tsquery('english', user_text)` handles arbitrary text safely and converts it to a tsquery. Alternatively, sanitize by keeping only alphanumeric tokens.

### Pitfall 4: EmailScore upsert missing constraint name

**What goes wrong:** `pg_insert(EmailScore).on_conflict_do_update(...)` fails at runtime with "no unique constraint" if the wrong constraint name is passed.
**Why it happens:** The constraint name must match exactly what's in the DB.
**How to avoid:** The constraint is `"uq_email_score_email"` (models.py line 953). Use exactly this string in `on_conflict_do_update(constraint="uq_email_score_email", ...)`.

### Pitfall 5: Thread priority not updated after per-message scoring

**What goes wrong:** SCORE-07 requires thread priority = highest unhandled message score. If the scorer only writes per-message EmailScore rows without updating a thread-level field, the UI in Phase 5 will need to compute this at read time.
**Why it happens:** The Email model has no `thread_priority` column — there is no thread-level table currently.
**How to avoid:** Phase 3 should compute thread priority at READ time (a derived query), not store it. The SQL is: `SELECT MAX(priority) FROM email_scores JOIN emails USING (email_id) WHERE gmail_thread_id = ? AND is_replied = false`. This avoids a new table and keeps the model consistent.
**Warning signs:** If Phase 5 asks for a "thread priority" DB column, it likely doesn't need it.

### Pitfall 6: Daily cap counting email_scores rows vs. a new counter

**What goes wrong:** Per SCORE requirement plan item 03-02, there is a "per-tenant daily cap" on scoring. The Slack monitor (reference pattern) counts `ContextEntry` rows per day. For the scorer, counting `EmailScore` rows inserted today is the natural equivalent.
**Why it happens:** No explicit "scoring runs" counter exists yet.
**How to avoid:** Use `SELECT COUNT(*) FROM email_scores JOIN emails USING (email_id) WHERE tenant_id = ? AND email_scores.scored_at >= today`. Default cap: 500 emails/day (a full inbox backfill scenario). Store cap in `Integration.settings["daily_scoring_cap"]` for the `gmail-read` integration, following the Slack monitor pattern exactly.

---

## Code Examples

### EmailScore Upsert (verified against models.py)

```python
# Source: based on upsert_email() in gmail_sync.py and EmailScore model in models.py
from sqlalchemy.dialects.postgresql import insert as pg_insert
from flywheel.db.models import EmailScore

stmt = (
    pg_insert(EmailScore)
    .values(
        tenant_id=tenant_id,
        email_id=email_id,
        priority=score["priority"],
        category=score["category"],
        suggested_action=score.get("suggested_action"),
        reasoning=score.get("reasoning"),
        context_refs=score.get("context_refs", []),
        sender_entity_id=sender_entity_id,  # UUID or None
    )
    .on_conflict_do_update(
        constraint="uq_email_score_email",
        set_={
            "priority": pg_insert(EmailScore).excluded.priority,
            "category": pg_insert(EmailScore).excluded.category,
            "suggested_action": pg_insert(EmailScore).excluded.suggested_action,
            "reasoning": pg_insert(EmailScore).excluded.reasoning,
            "context_refs": pg_insert(EmailScore).excluded.context_refs,
            "sender_entity_id": pg_insert(EmailScore).excluded.sender_entity_id,
            "scored_at": datetime.now(timezone.utc),
        },
    )
)
await db.execute(stmt)
```

### SKILL.md Frontmatter for email-scorer

```yaml
---
name: email-scorer
version: "1.0"
description: >
  Background email priority scorer. Given a list of email IDs, scores each
  1-5 using sender entity lookup, context store full-text search, and LLM
  reasoning. Writes EmailScore rows. Called by the sync worker after upsert.
web_tier: 1
engine: email_scorer
contract_reads:
  - context_entities
  - context_entries
contract_writes:
  - email_scores
tags:
  - email
  - background
token_budget: 10000
---
```

Note: The `engine` frontmatter field maps to `engine_module` in the DB. This signals to `skill_executor.py` that this skill has a dedicated Python engine. The system prompt body of SKILL.md can contain the scoring prompt template (used for documentation; actual prompt lives in `engines/email_scorer.py`).

### Haiku call pattern (verified from gmail_sync.py)

```python
# Source: /backend/src/flywheel/services/gmail_sync.py lines 453-471
import anthropic
from flywheel.config import settings

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
response = await client.messages.create(
    model=_HAIKU_MODEL,
    max_tokens=500,  # Scoring response is compact JSON
    system=SCORE_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": email_context_block}],
)
text = response.content[0].text.strip()
try:
    return json.loads(text)
except json.JSONDecodeError:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise
```

### Context entity lookup for sender

```python
# Source: ContextEntity model, models.py lines 507-544
from sqlalchemy import or_
from flywheel.db.models import ContextEntity

sender_domain = sender_email.split("@")[-1] if "@" in sender_email else None

filters = [ContextEntity.tenant_id == tenant_id]
if sender_domain:
    filters.append(
        or_(
            ContextEntity.name.ilike(f"%{sender_domain}%"),
            ContextEntity.aliases.contains([sender_email]),
        )
    )
else:
    filters.append(ContextEntity.aliases.contains([sender_email]))

result = await db.execute(select(ContextEntity).where(*filters).limit(1))
entity = result.scalar_one_or_none()
```

### Full-text search for topic relevance

```python
# Source: search_vector column definition, models.py lines 204-211
# Use plainto_tsquery (not to_tsquery) to handle arbitrary subject text safely
from sqlalchemy import text as sa_text
from flywheel.db.models import ContextEntry

# Extract meaningful keywords from subject (strip Re:/Fwd: prefixes)
import re
clean_subject = re.sub(r"^(Re:|Fwd:|Fw:)\s*", "", subject or "", flags=re.IGNORECASE).strip()

if clean_subject:
    result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.deleted_at.is_(None),
            sa_text("search_vector @@ plainto_tsquery('english', :q)").bindparams(q=clean_subject),
        )
        .order_by(
            sa_text("ts_rank(search_vector, plainto_tsquery('english', :q)) DESC").bindparams(q=clean_subject)
        )
        .limit(3)
    )
    matching_entries = result.scalars().all()
else:
    matching_entries = []
```

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 3 |
|--------------|------------------|-------------------|
| Filesystem SKILL.md parsing at runtime | DB-backed skill_definitions (seeded from SKILL.md) | The scorer SKILL.md must exist in `skills/email-scorer/SKILL.md` AND be seeded via `flywheel db seed` |
| Sync gateway for all skills | `_execute_with_tools` for interactive, Python engines for automated | Scorer is a Python engine, not tool-use |
| Single execution path | Engine dispatch in `execute_run()` with `is_company_intel`/`is_meeting_prep` guards | Scorer adds a third guard: `is_email_scorer` |
| `to_tsquery` for search | `plainto_tsquery` for user-derived text | Prevents SQL errors from punctuation in subjects |

---

## Open Questions

1. **Should scoring bypass `execute_run()` entirely?**
   - What we know: `execute_run()` requires a `user_id` for BYOK decryption. The scorer is background. The Slack monitor and voice profile bypass skill_executor entirely.
   - What's unclear: Whether creating a SkillRun record for scoring observability is worth the complexity.
   - Recommendation: Bypass `execute_run()`. Call `_score_emails_for_tenant()` directly from `_sync_one_integration()`. Still create a minimal SkillRun record (status=completed, no events) for audit trail. This is simpler than extending the subsidy key allowlist.

2. **Batch size for scoring API calls**
   - What we know: Haiku is cheap. Scoring one email per API call is simple but slow for initial full sync (200+ emails). Batch scoring (5-10 per call) saves latency but adds prompt complexity.
   - What's unclear: Whether batch scoring degrades reasoning quality when email contexts differ.
   - Recommendation: Score individually for initial implementation. Context lookups are per-email anyway. Revisit batching if latency becomes a problem.

3. **What happens when `context_entities` is empty (new tenant)?**
   - What we know: Sender entity lookup returns None. Context entry FTS returns empty. The scorer must still produce a valid score.
   - What's unclear: Nothing — the prompt handles this (entity=null, context=[]).
   - Recommendation: The system prompt should explicitly say "If no context is available, score conservatively but apply urgency keyword heuristics." This ensures reasonable behavior before onboarding completes.

4. **Thread staleness computation**
   - What we know: There is no thread-level table. Thread priority is derived from per-message scores.
   - What's unclear: Whether Phase 5 (the UI) will need a denormalized thread_priority column for query performance.
   - Recommendation: Defer to Phase 5. For Phase 3, compute thread priority as `MAX(priority) WHERE gmail_thread_id = ? AND is_replied = FALSE`. Document the SQL so Phase 5 can decide if it needs denormalization.

---

## Recommended Project Structure

```
skills/
└── email-scorer/
    └── SKILL.md          # Frontmatter + scoring prompt documentation

backend/src/flywheel/
├── engines/
│   └── email_scorer.py   # New: async scoring engine
└── services/
    ├── skill_executor.py  # Modified: add is_email_scorer dispatch
    └── gmail_sync.py      # Modified: call scorer after upsert
```

The `SKILL.md` body is documentation/prompt reference. The live scoring prompt lives in `engines/email_scorer.py` (same pattern as `company_intel.py` which hardcodes its LLM prompts, not in the SKILL.md body).

---

## Sources

### Primary (HIGH confidence)
- `/backend/src/flywheel/services/skill_executor.py` — Full read: engine dispatch pattern, `_execute_with_tools`, `execute_run`, company_intel/meeting_prep precedents
- `/backend/src/flywheel/db/models.py` — Full read: Email, EmailScore, ContextEntity, ContextEntry, SkillRun, SkillDefinition ORM definitions
- `/backend/src/flywheel/services/gmail_sync.py` — Full read: sync loop pattern, voice_profile_init Haiku pattern, upsert_email
- `/backend/src/flywheel/tools/context_tools.py` — Full read: context_read/write/query handlers, FTS pattern
- `/backend/src/flywheel/tools/registry.py` — Full read: RunContext, ToolDefinition, ToolRegistry
- `/backend/src/flywheel/db/seed.py` — Full read: SKILL.md parsing and skill_definitions upsert

### Secondary (MEDIUM confidence)
- `/backend/src/flywheel/services/slack_channel_monitor.py` — Daily cap pattern reference (lines 113-157)
- `/backend/src/flywheel/tools/budget.py` — RunBudget pattern
- `/backend/src/flywheel/engines/company_intel.py` — Python engine structure reference

---

## Metadata

**Confidence breakdown:**
- Skill executor dispatch pattern: HIGH — read from source code directly
- EmailScore/Email ORM: HIGH — read from models.py directly
- Scoring prompt engineering: MEDIUM — based on codebase patterns + LLM prompting principles; actual prompt quality must be validated empirically during implementation
- FTS query pattern: HIGH — search_vector column definition verified in models.py
- Daily cap pattern: HIGH — slack_channel_monitor.py reference verified
- Thread priority computation: HIGH — derived from Email/EmailScore column definitions

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable architecture; the scoring prompt will need empirical tuning during implementation)
