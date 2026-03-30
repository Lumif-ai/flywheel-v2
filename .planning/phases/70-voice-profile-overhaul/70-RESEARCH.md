# Phase 70: Voice Profile Overhaul - Research

**Researched:** 2026-03-30
**Domain:** Alembic migrations, LLM prompt engineering, SQLAlchemy ORM, voice extraction pipeline
**Confidence:** HIGH

## Summary

Phase 70 is a backend-only enhancement to the existing voice profile system. The codebase already has a complete, working pipeline: `voice_profile_init()` in `gmail_sync.py` extracts 4 fields from 20 emails, `email_drafter.py` uses those fields in a system prompt, and `email_voice_updater.py` incrementally learns from draft edits. All three touch-points need expansion to support 10 fields from 50 emails.

The work is straightforward because the architecture is well-established and Phase 69 already upgraded all engines to Sonnet. No new tables, no new API endpoints, no new external dependencies. The three plans map cleanly to: (1) database migration, (2) extraction prompt + parser, (3) draft prompt + incremental updater.

**Primary recommendation:** Follow the existing patterns exactly -- the codebase has consistent conventions for migrations, LLM prompts, JSON parsing, and profile persistence. The main risk is forgetting to update one of the several places that reference the 4-field profile dict.

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Alembic | (project version) | Database migrations | Already used for all 35 migrations |
| SQLAlchemy 2.0 | (project version) | ORM with `Mapped[]` typed columns | All models use this pattern |
| anthropic (Python SDK) | (project version) | Claude API calls | Used by all engines |
| asyncpg | (project version) | Async PostgreSQL driver | All DB access is async |

### No New Dependencies
This phase requires zero new packages. Everything uses existing infrastructure.

## Architecture Patterns

### Relevant File Locations
```
backend/
├── alembic/versions/036_*.py              # NEW: migration for 6 columns
├── src/flywheel/
│   ├── db/models.py                       # MODIFY: EmailVoiceProfile model
│   ├── services/gmail_sync.py             # MODIFY: extraction prompt + sample count
│   ├── engines/email_drafter.py           # MODIFY: system prompt + profile loading
│   └── engines/email_voice_updater.py     # MODIFY: update prompt + merge logic
```

### Pattern 1: Alembic Migration with Raw SQL
**What:** Project uses `op.execute()` with raw SQL for all migrations (not `op.add_column()` with SA types), because tables have RLS policies and custom constraints.
**When to use:** Always in this project.
**Example from 035:**
```python
op.add_column(
    "tasks",
    sa.Column(
        "email_id",
        postgresql.UUID(),
        sa.ForeignKey("emails.id", ondelete="SET NULL"),
        nullable=True,
    ),
)
```
**Note:** Migration 035 actually uses `op.add_column()` -- both patterns exist. For simple column additions, `op.add_column()` is fine. The original table creation (020) used raw SQL because it created RLS policies. Adding columns to an existing RLS-protected table does NOT require new RLS policy changes (existing policies apply to the whole row).

### Pattern 2: Voice Profile Dict Construction
**What:** `_load_voice_profile()` in `email_drafter.py` reads the ORM object and constructs a plain dict. This dict is then passed to `_build_draft_prompt()`.
**Current shape:**
```python
return {
    "tone": profile.tone or DEFAULT_VOICE_STUB["tone"],
    "avg_length": profile.avg_length or DEFAULT_VOICE_STUB["avg_length"],
    "sign_off": profile.sign_off or DEFAULT_VOICE_STUB["sign_off"],
    "phrases": (profile.phrases or [])[:5],
}
```
**Must be expanded to include all 10 fields with defaults.**

### Pattern 3: LLM JSON Extraction with Regex Fallback
**What:** All LLM calls that expect JSON use `json.loads()` first, then fall back to `re.search(r"\{.*\}", text, re.DOTALL)`.
**Used in:** `_extract_voice_profile()`, `email_voice_updater.py`, `email_scorer.py`.
**Continue using this exact pattern for the expanded prompts.**

### Pattern 4: Incremental Update Merge Logic
**What:** `update_from_edit()` in `email_voice_updater.py` does field-by-field merging. Tone/sign_off are direct replacements. avg_length uses a running average. phrases use add/remove with dedup.
**New fields:** formality_level, greeting_style, question_style, paragraph_pattern, emoji_usage should use direct replacement (same as tone). avg_sentences should use running average (same as avg_length).

### Anti-Patterns to Avoid
- **Breaking the profile dict contract:** The `_load_voice_profile()` return dict is consumed by `_build_draft_prompt()`. If the dict shape changes, both must update together.
- **Forgetting DEFAULT_VOICE_STUB:** The drafter has a hardcoded fallback dict. Must add 6 new fields to it.
- **Hardcoding the model string:** Phase 69 established `get_engine_model()` for all engine model resolution. Never use a literal model string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Migration rollback | Custom undo logic | Alembic `downgrade()` | Standard, tested |
| JSON parsing from LLM | New parsing strategy | Existing `json.loads` + regex fallback pattern | Already battle-tested in 3 files |
| Profile field defaults | Application-level defaults only | Column-level `DEFAULT` in migration + `DEFAULT_VOICE_STUB` in Python | Defense in depth -- DB defaults protect existing rows, Python defaults protect cold-start |

**Key insight:** Everything needed already exists in the codebase. This phase is about expanding existing patterns, not inventing new ones.

## Common Pitfalls

### Pitfall 1: Not Updating All Four Touch-Points
**What goes wrong:** Adding columns to the model but forgetting to update one of: extraction prompt, drafter prompt, updater prompt, or profile dict construction.
**Why it happens:** The voice profile data flows through 4 files. Easy to miss one.
**How to avoid:** Checklist: (1) models.py, (2) gmail_sync.py VOICE_SYSTEM_PROMPT + `_extract_voice_profile` caller + `voice_profile_init` upsert, (3) email_drafter.py DEFAULT_VOICE_STUB + `_load_voice_profile` + DRAFT_SYSTEM_PROMPT + `_build_draft_prompt`, (4) email_voice_updater.py `_UPDATE_VOICE_SYSTEM` + merge logic + `.values()` in UPDATE statement.
**Warning signs:** New columns are NULL when they should have values from extraction.

### Pitfall 2: Breaking Existing Profiles on Migration
**What goes wrong:** Existing `email_voice_profiles` rows with only 4 fields cause drafting to fail because new fields are NULL.
**Why it happens:** Migration adds columns without defaults, or Python code doesn't handle None for new fields.
**How to avoid:** (1) Migration MUST specify `DEFAULT` for all 6 new columns. (2) `_load_voice_profile()` must use `or` fallback for each new field. (3) `DRAFT_SYSTEM_PROMPT` template must not crash on None values.
**Warning signs:** Existing users' drafts break after deploy.

### Pitfall 3: Token Cost Explosion from 50 Emails
**What goes wrong:** Sending 50 full email bodies to Sonnet instead of 20 significantly increases token usage and cost.
**Why it happens:** Email bodies can be long. 50 bodies could be 50-100K tokens.
**How to avoid:** The current code already fetches up to 200 sent messages and filters to substantive ones. The change is only in the `substantive_bodies[:20]` slice -- change to `[:50]`. Consider whether email bodies should be truncated (e.g., first 500 words each) to control token cost. The spec does not mention truncation, but it is worth considering as a practical measure.
**Warning signs:** API costs spike, LLM calls timeout.

### Pitfall 4: Inconsistent Defaults Between Migration and Python
**What goes wrong:** Migration sets `DEFAULT 'conversational'` but Python DEFAULT_VOICE_STUB uses `'professional and conversational'`. Behavior differs for new-row vs existing-row.
**Why it happens:** Defaults defined in two places.
**How to avoid:** Document the canonical defaults once (spec says: `conversational`, `Hi {name},`, `direct`, `short single-line`, `never`, `3`). Use these exact values in both migration and Python code.
**Warning signs:** New users and existing users get different draft styles for the same profile state.

### Pitfall 5: Forgetting `updated_at` in the Voice Updater
**What goes wrong:** The updater's `.values()` call in the UPDATE statement only sets the original 4 fields + `samples_analyzed` + `updated_at`. New fields must be added to this call.
**Why it happens:** The merge logic at the end of `update_from_edit()` explicitly lists each field.
**How to avoid:** Add all 6 new fields to the UPDATE `.values()` call in the updater, reading from the parsed LLM response with fallback to current profile values.

## Code Examples

### Migration Pattern (036)
```python
# Based on existing project conventions
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column("email_voice_profiles",
        sa.Column("formality_level", sa.Text(), server_default="conversational"))
    op.add_column("email_voice_profiles",
        sa.Column("greeting_style", sa.Text(), server_default="Hi {name},"))
    op.add_column("email_voice_profiles",
        sa.Column("question_style", sa.Text(), server_default="direct"))
    op.add_column("email_voice_profiles",
        sa.Column("paragraph_pattern", sa.Text(), server_default="short single-line"))
    op.add_column("email_voice_profiles",
        sa.Column("emoji_usage", sa.Text(), server_default="never"))
    op.add_column("email_voice_profiles",
        sa.Column("avg_sentences", sa.Integer(), server_default=sa.text("3")))
```

### Expanded Model Columns (models.py)
```python
# Add after existing columns in EmailVoiceProfile
formality_level: Mapped[str | None] = mapped_column(
    Text, server_default=text("'conversational'")
)
greeting_style: Mapped[str | None] = mapped_column(
    Text, server_default=text("'Hi {name},'")
)
question_style: Mapped[str | None] = mapped_column(
    Text, server_default=text("'direct'")
)
paragraph_pattern: Mapped[str | None] = mapped_column(
    Text, server_default=text("'short single-line'")
)
emoji_usage: Mapped[str | None] = mapped_column(
    Text, server_default=text("'never'")
)
avg_sentences: Mapped[int | None] = mapped_column(
    Integer, server_default=text("3")
)
```

### Expanded Extraction Prompt (gmail_sync.py)
```python
VOICE_SYSTEM_PROMPT = """\
You are analyzing email samples to extract a user's writing voice profile.
Return a JSON object with exactly these fields:
- tone: string (e.g., "professional and concise", "warm and conversational")
- avg_length: integer (estimated average email length in words)
- sign_off: string (most common sign-off phrase, e.g., "Best," or "Thanks,")
- phrases: array of strings (3-5 characteristic phrases or expressions the person uses)
- formality_level: string — one of "formal", "conversational", or "casual"
- greeting_style: string (most common greeting, e.g., "Hi {name},", "Hey,", "No greeting")
- question_style: string — one of "direct", "embedded", or "rare"
- paragraph_pattern: string — e.g., "short single-line", "2-3 sentence blocks", "long form"
- emoji_usage: string — one of "never", "occasional", or "frequent"
- avg_sentences: integer (average number of sentences per email)
- samples_analyzed: integer (number of emails you analyzed)

Return only the JSON object, no other text.\
"""
```

### Expanded Draft System Prompt (email_drafter.py)
```python
# From spec A-05
DRAFT_SYSTEM_PROMPT = """\
You are drafting email replies on behalf of a specific person. Your job is to write
a reply that sounds authentically like them — not generic AI prose.

VOICE PROFILE (match this exactly):
- Tone: {tone}
- Formality: {formality_level}
- Greeting style: {greeting_style}
- Typical length: {avg_length} words, ~{avg_sentences} sentences
- Paragraph style: {paragraph_pattern}
- Question style: {question_style}
- Emoji usage: {emoji_usage}
- Sign-off: Always end with "{sign_off}"
- Characteristic phrases to weave in naturally: {phrases_list}

REPLY CONSTRAINTS:
- Address the specific ask or question in the email directly
- Do NOT include a subject line — body only
- Do NOT start with "I hope this email finds you well" or similar filler
- Do NOT use bullet points unless the incoming email used them
- Match the greeting style above for the opening
- Match the formality level — casual means contractions, informal language
- End with the sign-off above and nothing after it

CONTEXT FROM USER'S KNOWLEDGE BASE:
{context_block}

OUTPUT:
Return only the reply body text. No subject, no metadata, no explanation.
"""
```

### Expanded Voice Updater Allowed Fields
```python
_UPDATE_VOICE_SYSTEM = """\
You are updating a writing voice profile based on how a user edited an AI-generated email draft.
Analyze the diff and return ONLY the fields that should change, as a JSON object.
Omit unchanged fields entirely.

Allowed return fields:
- "tone": string (e.g. "professional", "casual", "warm")
- "avg_length": integer (estimated word count of preferred email body)
- "sign_off": string (e.g. "Thanks,", "Best,")
- "phrases_to_add": list of strings (phrases the user prefers)
- "phrases_to_remove": list of strings (phrases the user removed or replaced)
- "formality_level": string — "formal", "conversational", or "casual"
- "greeting_style": string (e.g. "Hi {name},", "Hey,", "No greeting")
- "question_style": string — "direct", "embedded", or "rare"
- "paragraph_pattern": string (e.g. "short single-line", "2-3 sentence blocks")
- "emoji_usage": string — "never", "occasional", or "frequent"
- "avg_sentences": integer (average sentences per email)

Only include a field if the edits clearly demonstrate a preference change.
If the edits are trivial (whitespace, punctuation only), return an empty JSON object: {}

Return ONLY a JSON object. No markdown fencing. No explanation.
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 4-field voice profile (tone, avg_length, sign_off, phrases) | 10-field profile with formality, greeting, paragraph, question, emoji, sentence count | Phase 70 | Drafts sound more like the user |
| 20 email samples for extraction | 50 email samples | Phase 70 | Better signal for voice patterns |
| Haiku for voice extraction/learning | Sonnet for all engines | Phase 69 | Better quality extraction and learning |

## Critical Implementation Details

### Files That Must Change (Complete List)

**Plan 70-01 (Migration):**
1. `backend/alembic/versions/036_voice_profile_expansion.py` -- NEW: add 6 columns
2. `backend/src/flywheel/db/models.py` -- ADD: 6 new `Mapped[]` columns to `EmailVoiceProfile`

**Plan 70-02 (Extraction):**
1. `backend/src/flywheel/services/gmail_sync.py`:
   - `VOICE_SYSTEM_PROMPT` -- expand to request 10 fields
   - `voice_profile_init()` -- change `substantive_bodies[:20]` to `[:50]`
   - `voice_profile_init()` -- add 6 new fields to `.values()` in the upsert statement
   - `voice_profile_init()` -- add 6 new fields to `.set_()` in the on_conflict_do_update

**Plan 70-03 (Draft Prompt + Updater):**
1. `backend/src/flywheel/engines/email_drafter.py`:
   - `DEFAULT_VOICE_STUB` -- add 6 new field defaults
   - `_load_voice_profile()` -- add 6 new fields to returned dict with `or` fallback
   - `DRAFT_SYSTEM_PROMPT` -- expand with all 10 fields (from spec A-05)
   - `_build_draft_prompt()` -- format 6 new fields into the system prompt
2. `backend/src/flywheel/engines/email_voice_updater.py`:
   - `_UPDATE_VOICE_SYSTEM` -- add 6 new allowed return fields
   - `update_from_edit()` -- add `current_profile_json` expansion (include 6 new fields)
   - `update_from_edit()` -- add merge logic for 6 new fields (direct replacement for 5, running average for avg_sentences)
   - `update_from_edit()` -- add 6 new fields to UPDATE `.values()` call

### Default Values (Canonical, from Spec)
| Field | Default | Type |
|-------|---------|------|
| `formality_level` | `'conversational'` | TEXT |
| `greeting_style` | `'Hi {name},'` | TEXT |
| `question_style` | `'direct'` | TEXT |
| `paragraph_pattern` | `'short single-line'` | TEXT |
| `emoji_usage` | `'never'` | TEXT |
| `avg_sentences` | `3` | INTEGER |

## Open Questions

1. **Token cost of 50 email bodies**
   - What we know: Current code sends up to 20 bodies. Changing to 50 increases cost ~2.5x per extraction.
   - What's unclear: Whether bodies should be truncated to control cost. Spec says "50 substantive sent emails" but doesn't address truncation.
   - Recommendation: Start without truncation (50 full bodies). Monitor token usage. Add truncation (e.g., 500 words per body) in a follow-up if costs are problematic. The extraction is a one-time operation per user.

2. **Migration revision naming**
   - What we know: Latest migration is `035_add_email_task_fields`. Next should be `036_*`.
   - What's unclear: Whether other migrations might be added concurrently.
   - Recommendation: Use `036_voice_profile_expansion` as the revision ID.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** (all findings verified by reading actual source files):
  - `backend/src/flywheel/db/models.py` lines 1050-1083 -- EmailVoiceProfile model (4 fields)
  - `backend/src/flywheel/services/gmail_sync.py` lines 748-919 -- voice extraction pipeline
  - `backend/src/flywheel/engines/email_drafter.py` lines 62-91, 99-139, 280-327 -- draft system prompt and voice loading
  - `backend/src/flywheel/engines/email_voice_updater.py` -- full file, incremental updater
  - `backend/src/flywheel/engines/model_config.py` -- engine model resolution (Phase 69)
  - `backend/alembic/versions/020_email_models.py` -- original table creation with RLS
  - `backend/alembic/versions/035_add_email_task_fields.py` -- latest migration pattern

- **Project specs:**
  - `.planning/SPEC-email-voice-intelligence.md` lines 47-106 -- spec items A-03 through A-06
  - `.planning/REQUIREMENTS.md` -- VOICE-01 through VOICE-04

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all patterns verified in codebase
- Architecture: HIGH -- expanding existing pipeline, no structural changes
- Pitfalls: HIGH -- derived from direct code reading, all touch-points identified

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable codebase, no external dependency changes expected)
