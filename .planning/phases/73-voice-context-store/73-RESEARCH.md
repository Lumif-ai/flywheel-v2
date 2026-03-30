# Phase 73: Voice as Context Store Asset - Research

**Researched:** 2026-03-30
**Domain:** Backend context store integration for voice profile sharing
**Confidence:** HIGH

## Summary

Phase 73 bridges the voice profile (currently stored only in the `email_voice_profiles` DB table) to the context store (the `context_entries` DB table), so any skill can read the user's voice profile via `flywheel_read_context`. The implementation requires writing to `sender-voice.md` in the context store at two existing trigger points: (1) after initial voice extraction in `voice_profile_init()` within `gmail_sync.py`, and (2) after every incremental voice update in `update_from_edit()` within `email_voice_updater.py`.

The context store is DB-backed (not file-based). Entries live in the `context_entries` table, accessed via REST API (`/api/v1/context/files/{file_name}/entries`) and the MCP tool `flywheel_read_context` which calls `GET /api/v1/context/search`. The file-based `context_utils.py` exists but is a separate CLI-side system; the backend uses DB entries. The `sender-voice.md` file_name becomes a virtual file in the `context_entries` table, consistent with how `meetings.md`, `market-signals`, `competitive-intel`, etc. already work.

**Primary recommendation:** Create a single `voice_context_writer.py` module with one function `write_voice_to_context(db, tenant_id, user_id, profile_dict, samples_analyzed)` that upserts a single ContextEntry row with `file_name="sender-voice"`, then call it from both `voice_profile_init()` and `update_from_edit()`. Use upsert-by-source pattern (soft-delete old + insert new) to keep exactly one current entry per tenant.

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy async | current | ContextEntry insert/update | Already used for all DB writes |
| FastAPI | current | Context API already exists | No new endpoints needed |
| Pydantic | current | Entry serialization | Already used for context entry models |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pg_insert (SQLAlchemy) | current | Upsert via ON CONFLICT | Used by meeting_ingest, gmail_sync for atomic upserts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct DB insert in backend | MCP tool `flywheel_write_context` | MCP tool goes through REST API + auth -- unnecessary overhead for backend-to-backend writes. Direct DB is the established pattern (see `meeting_ingest.py`) |
| Single entry upsert | Append new entry each time | Would create duplicate voice entries. Upsert keeps exactly one current snapshot |
| Separate `sender-voice.md` file_name | Reuse existing context file | Dedicated file_name makes it trivially searchable via `flywheel_read_context("sender voice")` |

**Installation:** No new packages needed.

## Architecture Patterns

### Pattern 1: Voice Context Writer Module

**What:** A standalone `voice_context_writer.py` in `backend/src/flywheel/engines/` with one async function that writes/updates the voice profile as a ContextEntry.

**When to use:** Called after both initial extraction and incremental updates.

**Example:**
```python
# backend/src/flywheel/engines/voice_context_writer.py
from flywheel.db.models import ContextEntry, ContextCatalog
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def write_voice_to_context(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    profile_dict: dict,
    samples_analyzed: int,
) -> None:
    """Write/update sender-voice entry in context store.

    Soft-deletes any existing sender-voice entry for this tenant,
    then inserts a fresh one with the current profile snapshot.
    """
    # Soft-delete existing entry (idempotent)
    await db.execute(
        update(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.file_name == "sender-voice",
            ContextEntry.source == "email-voice-engine",
            ContextEntry.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )

    # Format all 10 fields as readable content
    content = _format_voice_content(profile_dict, samples_analyzed)

    # Insert new entry
    entry = ContextEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="sender-voice",
        source="email-voice-engine",
        detail="Voice profile snapshot",
        content=content,
        confidence=_compute_confidence(samples_analyzed),
        evidence_count=samples_analyzed,
        metadata_={},
    )
    db.add(entry)

    # Upsert catalog entry
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=tenant_id,
        file_name="sender-voice",
        description="User's writing voice profile extracted from email patterns",
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await db.execute(catalog_stmt)
```

### Pattern 2: Content Formatting for Context Store

**What:** The voice profile must be stored as human-readable markdown content (matching other context entries), not raw JSON. This allows `flywheel_read_context` to return it in a format any skill can parse naturally.

**Example content format:**
```markdown
Writing Voice Profile (extracted from 47 sent emails)

Tone: professional and direct
Formality: conversational
Greeting style: Hi {name},
Sign-off: Best,
Average length: ~80 words, ~3 sentences
Paragraph pattern: short single-line
Question style: direct
Emoji usage: never
Characteristic phrases: "happy to help", "let me know", "sounds good"
```

### Pattern 3: Confidence Mapping

**What:** Map `samples_analyzed` to context store confidence levels.

**Rules:**
- `samples_analyzed >= 20` -> "high" (strong signal)
- `samples_analyzed >= 5` -> "medium" (reasonable signal)
- `samples_analyzed < 5` -> "low" (limited data)

### Pattern 4: Hook Placement

**What:** Insert `write_voice_to_context()` calls at exactly two points.

**Hook 1 -- Initial extraction** (`gmail_sync.py`, after line 941 `await db.execute(stmt)`):
```python
# After voice profile DB insert, write to context store
await write_voice_to_context(db, integration.tenant_id, integration.user_id, profile_data, samples_count)
```

**Hook 2 -- Incremental update** (`email_voice_updater.py`, after line 309 `await db.commit()`):
```python
# After voice profile DB update, refresh context store
updated_profile = {
    "tone": new_tone,
    "avg_length": new_avg_length,
    "sign_off": new_sign_off,
    "phrases": new_phrases,
    "formality_level": new_formality,
    "greeting_style": new_greeting,
    "question_style": new_question,
    "paragraph_pattern": new_paragraph,
    "emoji_usage": new_emoji,
    "avg_sentences": new_avg_sentences,
}
await write_voice_to_context(db, tenant_id, user_id, updated_profile, new_samples)
```

**Hook 3 -- Voice profile reset** (`email.py`, `reset_voice_profile` endpoint):
When the user resets their voice profile, the context store entry should also be soft-deleted. Then `voice_profile_init` re-creates it as part of the re-extraction flow (Hook 1).

### Anti-Patterns to Avoid
- **Multiple context entries per tenant:** The voice profile is a single living document, not an append-only log. Always soft-delete the previous entry before inserting the new one.
- **Writing raw JSON to content field:** Other context entries use readable prose. The voice profile should follow the same convention so that `flywheel_read_context` returns something Claude can use naturally.
- **Skipping the catalog upsert:** The `context_catalog` table tracks which files exist. Without an entry for `sender-voice`, it won't appear in `GET /context/files`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Context entry CRUD | Custom SQL for context writes | Existing ContextEntry model + patterns from `meeting_ingest.py` | Consistent with how all other context writes work |
| Catalog management | Manual catalog tracking | ContextCatalog upsert pattern from `context.py:append_entry` | Already solved with ON CONFLICT DO UPDATE |
| Voice profile serialization | Custom JSON schema | Dict with 10 known fields, same as `_load_voice_profile` return format | Already standardized across drafter and updater |

**Key insight:** The voice profile dict format is already standardized in `email_drafter.py:_load_voice_profile()`. The writer module should accept this same dict shape, making integration trivial.

## Common Pitfalls

### Pitfall 1: Transaction Scope Mismatch
**What goes wrong:** `voice_profile_init()` calls `db.commit()` at line 942. If we add the context store write before that commit, it's in the same transaction (good). But `update_from_edit()` also calls `db.commit()` at line 311. We must ensure the context write happens before that commit.
**Why it happens:** Both functions own their transaction lifecycle.
**How to avoid:** Place `write_voice_to_context()` call BEFORE the existing `db.commit()` in both functions, so the voice profile DB update and context store write are atomic.
**Warning signs:** Voice profile updated but context store stale, or vice versa.

### Pitfall 2: Missing User ID in Background Tasks
**What goes wrong:** `update_from_edit()` receives `tenant_id` and `user_id` directly, which is fine. But `voice_profile_init()` gets them from `integration.tenant_id` and `integration.user_id`. The `ContextEntry` model requires `user_id` as a non-nullable FK to `profiles.id`.
**Why it happens:** Integration-based flows don't always surface user_id explicitly.
**How to avoid:** Use `integration.user_id` for the ContextEntry -- this is already how voice profile init works.

### Pitfall 3: Stale Context on Reset
**What goes wrong:** User clicks "Reset voice profile" in settings. The `email_voice_profiles` row is deleted, but `sender-voice` context entry persists with outdated data.
**Why it happens:** The reset endpoint (`POST /email/voice-profile/reset`) doesn't know about context store.
**How to avoid:** Add a soft-delete of the `sender-voice` ContextEntry in the reset endpoint, before triggering background re-extraction. When re-extraction completes, Hook 1 writes a fresh entry.

### Pitfall 4: RLS Context Not Set
**What goes wrong:** `ContextEntry` inserts fail because RLS is enforced on the `context_entries` table, and the `app.tenant_id` session variable isn't set.
**Why it happens:** Background functions like `voice_profile_init` use `tenant_session()` which sets RLS context. But if the writer is called from a context where RLS isn't set, inserts are silently blocked.
**How to avoid:** Both call sites (`voice_profile_init` and `update_from_edit`) already operate within tenant-scoped sessions. The writer inherits the same session -- no additional RLS setup needed.

### Pitfall 5: Search Vector Not Populated
**What goes wrong:** `flywheel_read_context` uses FTS (`search_vector @@ plainto_tsquery`), but new entries may not have the search vector populated if it's a generated column.
**Why it happens:** The `search_vector` column is a generated tsvector. Need to verify it's auto-computed on insert.
**How to avoid:** Check the migration -- `search_vector` is a `GENERATED ALWAYS AS` column (or trigger-based). If generated, it auto-populates on insert. Verify in existing tests or by inspecting the migration.

## Code Examples

### Voice Profile Dict Shape (source: email_drafter.py)
```python
# This is the dict shape returned by _load_voice_profile()
# and expected by the context writer
voice_profile = {
    "tone": "professional and direct",
    "avg_length": 80,
    "sign_off": "Best,",
    "phrases": ["happy to help", "let me know"],
    "formality_level": "conversational",
    "greeting_style": "Hi {name},",
    "question_style": "direct",
    "paragraph_pattern": "short single-line",
    "emoji_usage": "never",
    "avg_sentences": 3,
}
```

### Context Entry Creation Pattern (source: meeting_ingest.py:246)
```python
ce = ContextEntry(
    tenant_id=tenant_id,
    user_id=user_id,
    file_name="meetings.md",
    source=source,
    detail=title or "Meeting notes",
    content=content,
    confidence="medium",
    metadata_={},
)
db.add(ce)
```

### Catalog Upsert Pattern (source: context.py:311-319)
```python
catalog_stmt = pg_insert(ContextCatalog).values(
    tenant_id=user.tenant_id,
    file_name=file_name,
    status="active",
)
catalog_stmt = catalog_stmt.on_conflict_do_update(
    index_elements=["tenant_id", "file_name"],
    set_={"status": "active"},
)
await db.execute(catalog_stmt)
```

### MCP Read Path (source: cli/flywheel_mcp/server.py + api_client.py)
```python
# MCP tool calls: GET /api/v1/context/search?q=sender+voice
# Returns: [{file_name: "sender-voice", confidence: "high", content: "..."}]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Voice profile only in email_voice_profiles table | Still only in DB table (Phase 70-72) | Phase 70 (current) | Other skills cannot access voice profile |
| N/A | Phase 73 will write to context store | Upcoming | Any skill can read voice via `flywheel_read_context` |

## Open Questions

1. **File naming: `sender-voice` vs `sender-voice.md`**
   - What we know: Some context files use `.md` suffix (e.g., `meetings.md`) while others don't (e.g., `market-signals`, `competitive-intel`, `positioning`). The roadmap says `sender-voice.md`.
   - What's unclear: Whether to include the `.md` suffix.
   - Recommendation: Use `sender-voice` (no suffix) to match the majority pattern (`market-signals`, `competitive-intel`, `icp-profiles`, etc.). The roadmap reference to `sender-voice.md` appears to be conceptual.

2. **Multi-user tenants: one entry per user or per tenant?**
   - What we know: `EmailVoiceProfile` has a unique constraint on `(tenant_id, user_id)`. A tenant can have multiple users, each with their own voice.
   - What's unclear: Should `sender-voice` have one entry per user, or just one per tenant?
   - Recommendation: One entry per user. Use the `detail` field to tag which user (e.g., `detail="Voice profile for user {user_id}"`) and soft-delete by matching `tenant_id + file_name + source + user_id` (ContextEntry has `user_id` column). This preserves per-user voice in multi-user tenants. Current product is single-user-per-tenant, but this future-proofs.

3. **Context store entry for voice profile reset: immediate delete or wait for re-extraction?**
   - What we know: Reset deletes the `email_voice_profiles` row then triggers background re-extraction.
   - Recommendation: Soft-delete the context entry immediately on reset. When re-extraction finishes and calls `voice_profile_init()`, Hook 1 writes a fresh entry. This prevents stale data in the gap.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/db/models.py` -- EmailVoiceProfile model (10 fields), ContextEntry model, ContextCatalog model
- `backend/src/flywheel/engines/email_voice_updater.py` -- Incremental voice update flow (Hook 2 site)
- `backend/src/flywheel/services/gmail_sync.py:845-949` -- Initial voice extraction flow (Hook 1 site)
- `backend/src/flywheel/api/context.py` -- Context CRUD endpoints (append pattern, catalog upsert)
- `backend/src/flywheel/api/email.py` -- Voice profile endpoints (reset flow = Hook 3)
- `backend/src/flywheel/engines/email_drafter.py` -- Voice profile dict shape, `_load_voice_profile()`
- `cli/flywheel_mcp/server.py` -- MCP tool `flywheel_read_context` implementation
- `cli/flywheel_mcp/api_client.py` -- REST client for context search/write
- `backend/src/flywheel/services/meeting_ingest.py` -- ContextEntry creation pattern from backend

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` -- Phase 73 success criteria and requirements
- `.planning/REQUIREMENTS.md` -- CTX-01 definition
- `.planning/SPEC-email-voice-intelligence.md` -- Overall spec context
- `.planning/phases/72-draft-enhancements/72-RESEARCH.md` -- Voice snapshot in context_used (Phase 72 pattern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- patterns directly observed in codebase (meeting_ingest, context.py)
- Pitfalls: HIGH -- derived from actual code analysis of transaction boundaries and RLS

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable domain, internal codebase)
