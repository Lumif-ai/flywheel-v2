# Phase 74: Email Context Extractor and Shared Writer - Research

**Researched:** 2026-03-30
**Domain:** Email intelligence extraction + context store write infrastructure
**Confidence:** HIGH

## Summary

Phase 74 builds two complementary modules: (1) a shared context store writer (`context_store_writer.py`) that handles dedup, evidence counting, and 4000-char entry caps for any source, and (2) an email context extractor (`email_context_extractor.py`) that uses Claude to extract structured intelligence from email bodies and writes it through the shared writer.

The codebase already has two strong patterns to follow: `meeting_processor_web.py` writes meeting intelligence to ContextEntry rows with dedup by `(file_name, source, detail, tenant_id)`, and `voice_context_writer.py` writes voice profiles using soft-delete-then-insert. The shared writer unifies these patterns into a single reusable module. The email extractor follows the same async engine pattern as `email_scorer.py` and `email_drafter.py` -- fetching body on-demand from Gmail, calling Claude for structured extraction, then writing results.

**Primary recommendation:** Build `context_store_writer.py` as a pure async module with `write_contact()`, `write_insight()`, `write_action_item()`, `write_deal_signal()` functions that all route through a private `_write_entry()` helper handling the dedup/evidence logic. Build `email_context_extractor.py` as an async engine that mirrors the `score_email()` pattern -- single entry point, structured prompt, JSON parsing, writer calls, non-fatal error handling.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (async) | 2.x | DB operations for ContextEntry CRUD | Already used by all engines; ContextEntry model defined |
| anthropic (AsyncAnthropic) | latest | Claude API for extraction LLM calls | Used by email_scorer, email_drafter |
| FastMCP | latest | MCP wrapper for Claude Code skill access | Used by cli/flywheel_mcp/server.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | - | Parse LLM structured output | Extraction response parsing |
| re (stdlib) | - | Strip markdown fencing from LLM output | Same pattern as email_scorer._parse_score_response |
| logging (stdlib) | - | Structured logging (no PII) | All engine modules follow this |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct SQLAlchemy writes | Context API endpoints (POST /context/files/{name}/entries) | API adds HTTP overhead + auth complexity; direct DB is faster for backend engines and matches existing pattern (meeting_processor_web, voice_context_writer) |
| Per-category writer functions | Single generic write_entry() | Per-category functions enforce schema validation at the Python level; generic is more flexible but loses type safety |

## Architecture Patterns

### Recommended Project Structure
```
backend/src/flywheel/engines/
  context_store_writer.py    # NEW - shared writer (Plan 74-01)
  email_context_extractor.py # NEW - email extraction engine (Plan 74-02)
  email_scorer.py            # EXISTING - pattern reference
  voice_context_writer.py    # EXISTING - pattern reference
  meeting_processor_web.py   # EXISTING - pattern reference (write_context_entries)
  model_config.py            # EXISTING - get_engine_model("context_extraction")
```

### Pattern 1: Shared Writer with Dedup + Evidence Increment
**What:** A `_write_entry()` private helper that handles the write-or-increment decision for every context store write.
**When to use:** Every time any source (email, meeting, Slack, manual) writes to the context store.
**Dedup key:** `(file_name, source, detail, tenant_id, date)` where `detail` serves as the "detail_tag" mentioned in requirements.
**Logic:**
```python
async def _write_entry(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    file_name: str,
    source: str,
    detail: str,       # acts as detail_tag for dedup
    content: str,
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write or increment a context entry. Returns "created" or "incremented" or "skipped".

    Dedup: if (file_name, source, detail, tenant_id, date) exists and is not deleted:
      - If content is semantically the same: increment evidence_count, return "incremented"
      - If content differs: append as new entry (different insight, same tag)
    Cap: content truncated to 4000 chars before insert.
    Does NOT call db.commit() -- caller owns the transaction.
    """
```

**Evidence increment query:**
```python
existing = await db.execute(
    select(ContextEntry).where(
        ContextEntry.file_name == file_name,
        ContextEntry.source == source,
        ContextEntry.detail == detail,
        ContextEntry.tenant_id == tenant_id,
        ContextEntry.date == entry_date,
        ContextEntry.deleted_at.is_(None),
    ).limit(1)
)
row = existing.scalar_one_or_none()
if row is not None:
    # Same source+detail+date = corroboration -> increment evidence
    await db.execute(
        update(ContextEntry)
        .where(ContextEntry.id == row.id)
        .values(evidence_count=ContextEntry.evidence_count + 1)
    )
    return "incremented"
```

### Pattern 2: Email Context Extraction Engine
**What:** Async engine that fetches email body on-demand, calls Claude for structured extraction, writes results via shared writer.
**When to use:** Called from gmail_sync loop for priority >= 3 emails (wiring happens in Phase 75, not this phase).
**Flow:**
1. Fetch email body via `get_message_body(creds, email.gmail_message_id)` -- on-demand, never stored
2. Build extraction prompt with email metadata (sender, subject, date) + body
3. Call Claude (model from `get_engine_model(db, tenant_id, "context_extraction")`)
4. Parse structured JSON response
5. Write each extracted item via context_store_writer functions
6. Return extraction summary dict
7. Body variable goes out of scope -- garbage collected, never persisted

### Pattern 3: Dual Access Path (Backend Direct + MCP Wrapper)
**What:** Backend engines call `context_store_writer` functions directly with an AsyncSession. Claude Code skills call the same logic via `flywheel_write_context` MCP tool which routes through the context API.
**Implementation for Phase 74:**
- Build `context_store_writer.py` with async functions that take `db: AsyncSession` (direct path)
- The MCP path already exists via `flywheel_write_context` -> `POST /context/files/{name}/entries`
- To share dedup logic with MCP, either: (a) call the writer from the API endpoint, or (b) accept that MCP writes go through the simpler API path and only backend engines get full dedup
- **Recommendation:** For Phase 74, focus on the backend direct path. The MCP wrapper can be enhanced later to call the shared writer internally. The current MCP `flywheel_write_context` uses `source="mcp-manual"` which naturally separates from engine writes (`source="email-context-engine"`).

### Anti-Patterns to Avoid
- **Storing email body in DB:** The Email model explicitly has no body column. Body is fetched on-demand and must be discarded after extraction. Never store it in metadata, logs, or temp tables.
- **Committing inside the writer:** Follow the caller-commits pattern from voice_context_writer. The writer should never call `db.commit()`.
- **Logging PII:** Never log email body, subject, sender_email, or extracted contact names. Log only email_id, tenant_id, and counts.
- **Unbounded content:** Enforce the 4000-char cap in `_write_entry()` before insert, not at the caller level.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Model selection | Hardcoded model strings | `get_engine_model(db, tenant_id, "context_extraction")` | Tenant-configurable; already has "context_extraction" key in ENGINE_DEFAULTS |
| JSON parsing from LLM | Naive json.loads only | `_parse_response()` with regex fallback | LLMs occasionally wrap JSON in markdown fencing; email_scorer has this pattern |
| Gmail body fetch | Direct API calls | `get_message_body(creds, message_id)` from gmail_read.py | Already handles base64 decode, MIME tree walking, multipart fallback |
| Credential management | Manual OAuth | `get_valid_credentials(integration)` from gmail_read.py | Handles token refresh, revocation detection |
| Entry dedup | Ad-hoc duplicate checks | Shared `_write_entry()` with standard dedup key | One dedup implementation, not scattered across engines |

**Key insight:** The codebase already solved body fetching, model config, and JSON parsing. The novel work is (1) the extraction prompt design and (2) the shared writer with evidence counting.

## Common Pitfalls

### Pitfall 1: Evidence Count vs Duplicate Detection Confusion
**What goes wrong:** Incrementing evidence on entries that are actually different insights (false dedup), or creating duplicates for the same insight from different emails (missed dedup).
**Why it happens:** The dedup key `(source, detail, date)` is too narrow or too broad. If `detail` is just "contact" then all contacts from one day merge. If `detail` includes the full contact name, evidence never increments.
**How to avoid:** Use `detail` as a semantic tag that captures the specific entity/insight. For contacts: `detail = "contact:John Smith:acme.com"`. For insights: `detail = "insight:Series A timeline"`. For action items: `detail = "action:Send proposal to Acme"`. The tag is specific enough to prevent false merges but stable enough that the same insight from two emails matches.
**Warning signs:** evidence_count staying at 1 for everything (tags too specific) or evidence_count growing rapidly on single entries (tags too broad).

### Pitfall 2: Body Fetch Failures During Extraction
**What goes wrong:** Gmail API returns 401/403 (revoked token) or 429 (rate limit) during body fetch, causing extraction to fail silently.
**Why it happens:** Extraction runs in background sync loop; credentials can expire between scoring and extraction.
**How to avoid:** Follow the same pattern as `email_drafter._fetch_body_with_fallback()` -- try full body, fall back to `email.snippet` if body fetch fails, and record `fetch_error` in return dict. Snippet-based extraction is less rich but better than nothing.
**Warning signs:** Extraction returning None for many emails; "401" or "403" in error logs.

### Pitfall 3: Prompt Output Instability
**What goes wrong:** Claude returns inconsistent JSON structure across calls -- missing keys, extra keys, wrong types, nested arrays where flat arrays are expected.
**Why it happens:** Extraction prompts that are too loose or don't show examples. The model "knows" many output formats and picks inconsistently.
**How to avoid:** Use a strict system prompt with exact JSON schema, 2-3 few-shot examples, and the "return ONLY a JSON object" instruction. Validate every field with defaults (same as `_parse_score_response` in email_scorer).
**Warning signs:** KeyError or TypeError in writer calls after parsing.

### Pitfall 4: Content Exceeding 4000-Char Cap
**What goes wrong:** Long email threads or detailed extraction produce content strings > 4000 chars, potentially bloating the context store.
**Why it happens:** Requirements specify a 4000-char entry cap, but nothing enforces it without explicit truncation.
**How to avoid:** Truncate `content` to 4000 chars in `_write_entry()` before insert. For list-type content (multiple contacts), split into separate entries rather than one giant entry.
**Warning signs:** Context store reads returning very long entries; FTS performance degradation.

### Pitfall 5: Extracting from Noise Emails
**What goes wrong:** Running extraction on marketing emails, newsletters, or auto-notifications that scored priority 3 by mistake. This pollutes the context store with low-quality data.
**Why it happens:** The priority >= 3 filter catches some borderline emails. Marketing emails that mention a known contact can score 3-4.
**How to avoid:** Add a category filter in addition to priority. Skip extraction for `category in ("marketing", "informational")`. The email scorer already assigns categories.
**Warning signs:** Context store filling with entries sourced from newsletters; many low-confidence extractions.

## Code Examples

### Example 1: Shared Writer - write_contact()
```python
async def write_contact(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str,
    title: str | None,
    company: str | None,
    email_address: str | None,
    notes: str | None,
    source_email_id: UUID,
    confidence: str = "medium",
) -> str:
    """Write a contact to the context store. Returns 'created', 'incremented', or 'skipped'."""
    detail_tag = f"contact:{name.lower().strip()}"
    if company:
        detail_tag += f":{company.lower().strip()}"

    parts = [f"Name: {name}"]
    if title:
        parts.append(f"Title: {title}")
    if company:
        parts.append(f"Company: {company}")
    if email_address:
        parts.append(f"Email: {email_address}")
    if notes:
        parts.append(f"Notes: {notes}")
    content = "\n".join(parts)

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="contacts",
        source="email-context-engine",
        detail=detail_tag,
        content=content,
        confidence=confidence,
    )
```

### Example 2: Extraction Prompt Structure
```python
EXTRACTION_SYSTEM_PROMPT = """\
You are an email intelligence extraction engine. Given an email's metadata and body,
extract structured intelligence into exactly these categories.

Respond ONLY with a valid JSON object using these exact keys:
- contacts: list of {name, title, company, email, role_in_context, notes}
- topics: list of {topic, relevance (high/medium/low), context}
- deal_signals: list of {signal_type, description, confidence, counterparty}
- relationship_signals: list of {signal_type, description, people_involved}
- action_items: list of {action, owner, due_date, urgency (high/medium/low)}

Use empty lists for categories with no data.
Only extract information explicitly stated or strongly implied in the email.
Do not hallucinate contacts or action items not present in the email.
"""
```

### Example 3: Extraction Entry Point (mirrors score_email pattern)
```python
async def extract_email_context(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    integration: Integration,
    api_key: str | None = None,
) -> dict | None:
    """Extract context from a single email and write to context store.

    Non-fatal: logs errors and returns None on failure.
    Does NOT call db.commit() -- caller owns the transaction.
    """
    try:
        # 1. Fetch body on-demand (never stored)
        creds = await get_valid_credentials(integration)
        body = await get_message_body(creds, email.gmail_message_id)
        if not body or len(body.strip()) < 50:
            body = email.snippet or ""
            if len(body.strip()) < 20:
                return None  # Nothing meaningful to extract

        # 2. Build prompt
        model = await get_engine_model(db, tenant_id, "context_extraction")
        system_prompt, user_message = _build_extraction_prompt(email, body)

        # 3. Call Claude
        client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.flywheel_subsidy_api_key
        )
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()

        # 4. Parse (body goes out of scope after this line -- GC'd)
        del body  # Explicit: never retain email body
        extracted = _parse_extraction_response(text)

        # 5. Write via shared writer
        results = await _write_extracted_context(
            db, tenant_id, email.user_id, email.id, extracted
        )

        return results

    except Exception as exc:
        logger.error(
            "extract_email_context failed email_id=%s tenant_id=%s: %s",
            email.id, tenant_id, exc,
        )
        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Meeting processor has its own write_context_entries() | Shared writer used by all sources | Phase 74 (now) | Single dedup/evidence logic; meeting processor can be refactored later (REFACTOR-01) |
| Voice context writer uses soft-delete-then-insert | Shared writer uses dedup-or-increment | Phase 74 (now) | Voice writer stays separate (single-entry pattern differs from multi-entry pattern) |
| No email body extraction | Extract contacts/topics/deals/relationships/actions from email | Phase 74 (now) | Context store enriched from email in addition to meetings |

**Note:** The voice_context_writer should NOT be refactored into the shared writer in this phase. Its pattern (single snapshot, soft-delete all previous) is fundamentally different from the multi-entry pattern (contacts, insights, etc.) used by email and meeting extraction. Keep them separate.

## Open Questions

1. **MCP parity for shared writer**
   - What we know: Success criteria #4 says "both paths use identical write/dedup logic". The MCP tool currently goes through the API endpoint which does simple ContextEntry INSERT without dedup.
   - What's unclear: Should Phase 74 modify the API endpoint to use the shared writer internally, or is it sufficient to have the shared writer available for future MCP enhancement?
   - Recommendation: For this phase, build the shared writer and use it from backend engines only. Add a note in the code that the context API should be refactored to use the shared writer (this is a follow-up, not a blocker). The success criteria says "can invoke the same writer via MCP tool" -- this is satisfied if the MCP tool calls an API endpoint that internally uses the writer. Modify the `append_entry()` API endpoint to optionally route through the shared writer when `source` matches a known engine source.

2. **detail_tag naming convention**
   - What we know: The `detail` field on ContextEntry is a Text column used as a dedup key component. Meeting processor uses `meeting_slug` as the detail value.
   - What's unclear: Should email extraction use a structured format like `contact:name:company` or a natural language detail like "Contact from email thread about Series A"?
   - Recommendation: Use structured tags like `contact:john-smith:acme-corp` for dedup reliability. Natural language tags are too variable to deduplicate consistently.

3. **Confidence assignment for extractions**
   - What we know: Requirements mention "low-confidence extractions routed to review queue" (CTX-04, Phase 75). This phase needs to assign confidence but the review routing happens later.
   - What's unclear: What determines high vs medium vs low confidence for an extracted insight?
   - Recommendation: Use a simple heuristic: if the LLM itself flags a field as uncertain (e.g., "possibly" or "unclear"), mark low. If extracted from explicit text (e.g., "My title is VP Sales"), mark high. Default to medium. Return the confidence per-item from the LLM prompt.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/engines/voice_context_writer.py` -- soft-delete + insert pattern, catalog upsert, caller-commits
- `backend/src/flywheel/engines/meeting_processor_web.py` -- write_context_entries() with dedup by (file_name, source, detail, tenant_id), CONTEXT_FILE_MAP
- `backend/src/flywheel/engines/email_scorer.py` -- async engine pattern, prompt design, JSON parsing with regex fallback, model_config usage
- `backend/src/flywheel/engines/email_drafter.py` -- on-demand body fetch, voice profile loading, credential handling
- `backend/src/flywheel/services/gmail_read.py` -- get_message_body() for on-demand body fetch, _extract_body() MIME handling
- `backend/src/flywheel/engines/model_config.py` -- ENGINE_DEFAULTS includes "context_extraction" key, get_engine_model() pattern
- `backend/src/flywheel/db/models.py` -- ContextEntry model (line 182), ContextCatalog model (line 250), Email model (line 932)
- `cli/flywheel_mcp/server.py` -- flywheel_write_context MCP tool, current simple write path
- `.planning/REQUIREMENTS.md` -- CTX-02 and CTX-03 requirements text

### Secondary (MEDIUM confidence)
- `.planning/phases/73-voice-context-store/73-01-PLAN.md` -- Phase 73 plan showing voice writer implementation decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- two strong existing patterns (meeting_processor_web, voice_context_writer) to follow, plus email_scorer for engine structure
- Pitfalls: HIGH -- based on direct codebase analysis of dedup gaps, PII patterns, and error handling conventions

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- internal codebase, no external dependency drift)
