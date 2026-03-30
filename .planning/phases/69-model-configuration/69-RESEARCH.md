# Phase 69: Model Configuration Foundation - Research

**Researched:** 2026-03-29
**Domain:** Backend configuration pattern (FastAPI + SQLAlchemy + PostgreSQL JSONB)
**Confidence:** HIGH

## Summary

This phase replaces hardcoded LLM model constants scattered across 5 email engine files with a single shared helper that reads from tenant-level JSONB settings. The codebase already has a well-established pattern for tenant settings access (`Tenant.settings` JSONB column, `select(Tenant.settings).where(Tenant.id == tenant_id)`) and multiple precedents for reading nested keys from that column (e.g., `entity_aliases`, `member_limit`).

The change is straightforward: create a single async helper function `_get_engine_model(db, tenant_id, engine_key, default)`, place it in a shared location, and update each engine to call it instead of referencing module-level constants. The tenant settings JSONB approach requires no migration (column already exists), no new tables, and no API changes beyond what already exists (PATCH /tenants/current already accepts arbitrary settings).

**Primary recommendation:** Store model config in `Tenant.settings["email_engine_models"]` JSONB, create a shared helper in a new `backend/src/flywheel/engines/model_config.py` module, and update all 5 engine files to use it.

## Standard Stack

### Core (Already In Place)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy 2.0 | async | ORM + JSONB column access | Already used everywhere |
| PostgreSQL | JSONB | Tenant settings storage | Column already exists on `tenants` table |
| Pydantic Settings | - | Env-based app config | Already used for `config.py` |

### No New Dependencies Required
This phase adds zero new packages. Everything needed is already in the stack.

## Architecture Patterns

### Current State: Hardcoded Constants

Five locations have hardcoded model constants that must be replaced:

| File | Constant | Current Value | Engine Key |
|------|----------|---------------|------------|
| `engines/email_scorer.py:51` | `_HAIKU_MODEL` | `claude-haiku-4-5-20251001` | `scoring` |
| `services/gmail_sync.py:759` | `_HAIKU_MODEL` | `claude-haiku-4-5-20251001` | `voice_extraction` |
| `engines/email_voice_updater.py:35` | `_HAIKU_MODEL` | `claude-haiku-4-5-20251001` | `voice_learning` |
| `engines/email_drafter.py:59` | `_SONNET_MODEL` | `claude-sonnet-4-6` | `drafting` |
| *(does not exist yet)* | - | - | `context_extraction` |

### Recommended: Shared Helper Module

Create `backend/src/flywheel/engines/model_config.py`:

```
engines/
  model_config.py          # NEW: _get_engine_model() helper
  email_scorer.py           # MODIFY: use helper
  email_drafter.py          # MODIFY: use helper
  email_voice_updater.py    # MODIFY: use helper
services/
  gmail_sync.py             # MODIFY: use helper for voice_extraction
```

### Pattern: Tenant Settings JSONB Access

The codebase already uses this exact pattern in `entity_normalization.py` and `graph.py`:

```python
# Existing pattern (from entity_normalization.py lines 92-97)
stmt = select(Tenant.settings).where(Tenant.id == tid)
result = await session.execute(stmt)
settings = result.scalar_one_or_none()
if settings and isinstance(settings, dict):
    entity_aliases = settings.get("entity_aliases", {})
```

The new helper follows the same pattern:

```python
# engines/model_config.py
import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from flywheel.db.models import Tenant

logger = logging.getLogger(__name__)

# Default models per engine — matches current hardcoded values
ENGINE_DEFAULTS: dict[str, str] = {
    "scoring": "claude-sonnet-4-6",
    "voice_extraction": "claude-sonnet-4-6",
    "voice_learning": "claude-sonnet-4-6",
    "drafting": "claude-sonnet-4-6",
    "context_extraction": "claude-sonnet-4-6",
}

async def get_engine_model(
    db: AsyncSession,
    tenant_id: UUID,
    engine_key: str,
    default: str = "claude-sonnet-4-6",
) -> str:
    """Return the configured LLM model for a specific email engine.

    Reads from tenant settings JSONB at key path:
      settings["email_engine_models"][engine_key]

    Falls back to the engine-specific default from ENGINE_DEFAULTS,
    then to the provided default parameter.

    If the configured model string is invalid (not in a known set),
    logs a warning and returns the default.
    """
    try:
        stmt = select(Tenant.settings).where(Tenant.id == tenant_id)
        result = await db.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings and isinstance(settings, dict):
            engine_models = settings.get("email_engine_models", {})
            if isinstance(engine_models, dict):
                model = engine_models.get(engine_key)
                if model and isinstance(model, str) and model.strip():
                    # Basic validation: warn on suspicious values but still return
                    if not model.startswith("claude-"):
                        logger.warning(
                            "Suspicious model string for engine=%s tenant_id=%s: %s — using anyway",
                            engine_key, tenant_id, model,
                        )
                    return model.strip()
    except Exception:
        logger.warning(
            "Failed to read model config for engine=%s tenant_id=%s — using default",
            engine_key, tenant_id, exc_info=True,
        )

    return ENGINE_DEFAULTS.get(engine_key, default)
```

### Pattern: How Each Engine Changes

Each engine file changes minimally:

```python
# BEFORE (email_scorer.py)
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
# ... later ...
response = await client.messages.create(model=_HAIKU_MODEL, ...)

# AFTER (email_scorer.py)
from flywheel.engines.model_config import get_engine_model
# ... later, inside score_email() ...
model = await get_engine_model(db, tenant_id, "scoring")
response = await client.messages.create(model=model, ...)
```

### Special Case: gmail_sync.py voice extraction

`_extract_voice_profile()` is a private helper that does NOT receive `db` or `tenant_id`. It's called from `voice_profile_init(db, integration)`. The model lookup must happen in `voice_profile_init` and be passed down:

```python
# In voice_profile_init:
model = await get_engine_model(db, integration.tenant_id, "voice_extraction")
profile = await _extract_voice_profile(bodies, model=model)

# Update _extract_voice_profile signature:
async def _extract_voice_profile(bodies: list[str], model: str = "claude-sonnet-4-6") -> dict:
```

### Settings JSON Structure

Stored in `tenants.settings` JSONB (no migration needed):

```json
{
  "email_engine_models": {
    "scoring": "claude-sonnet-4-6",
    "voice_extraction": "claude-sonnet-4-6",
    "voice_learning": "claude-sonnet-4-6",
    "drafting": "claude-sonnet-4-6",
    "context_extraction": "claude-sonnet-4-6"
  }
}
```

When this key is absent (the default for all existing tenants), the helper returns the defaults from `ENGINE_DEFAULTS`.

### Anti-Patterns to Avoid
- **Separate config table:** Overkill for 5 string values. The `tenants.settings` JSONB column is already the canonical place for per-tenant config.
- **Caching model strings in-memory:** The spec requires changes take effect on the next sync cycle without restart. Reading from DB each time ensures this. The extra query is one scalar select per engine call -- negligible compared to the LLM API call.
- **Validating against a fixed allowlist:** Model strings change frequently. A startswith-"claude-" warning is sufficient. Hard validation would break when new models are released.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-tenant config storage | New table or Redis cache | `Tenant.settings` JSONB | Column already exists, pattern already used for `entity_aliases`, `member_limit` |
| Config read pattern | Custom config service class | Simple async function | One query, one dict lookup. A class adds nothing. |
| Model validation | Strict allowlist | Warning log + passthrough | Model strings are opaque to us; Anthropic SDK will error if truly invalid |

## Common Pitfalls

### Pitfall 1: Breaking the caller-commits pattern
**What goes wrong:** Adding `db.commit()` or `db.refresh()` inside the helper.
**Why it happens:** Instinct to ensure data is fresh.
**How to avoid:** The helper only does a `select()`. No writes, no commits. The engines follow caller-commits and this helper is read-only.
**Warning signs:** Any `commit()` or `flush()` call inside `get_engine_model`.

### Pitfall 2: N+1 queries in batch scoring
**What goes wrong:** If 50 emails are scored in a loop, `get_engine_model` fires 50 identical queries.
**Why it happens:** Each `score_email()` call independently resolves its model.
**How to avoid:** For Phase 69, this is acceptable (50 tiny scalar selects vs 50 LLM calls). If it becomes a concern later, the caller (gmail_sync loop) can resolve the model once and pass it down. The function signature already supports this pattern by accepting a default.
**Warning signs:** Profiling shows >100ms spent on model config queries. (Unlikely -- each is <1ms.)

### Pitfall 3: Forgetting gmail_sync.py's _extract_voice_profile
**What goes wrong:** Updating 4 engines but missing the voice extraction in `gmail_sync.py` because it's in `services/` not `engines/`.
**Why it happens:** The phase says "5 email engine files" but one is in a different directory.
**How to avoid:** Explicit checklist: `email_scorer.py`, `email_drafter.py`, `email_voice_updater.py`, `gmail_sync.py` (voice extraction section), and register `context_extraction` key in defaults.

### Pitfall 4: Overwriting existing tenant settings
**What goes wrong:** Using PATCH `/tenants/current` with `settings: {"email_engine_models": {...}}` replaces the entire settings dict, wiping `entity_aliases`, `member_limit`, etc.
**Why it happens:** The current PATCH endpoint does `values["settings"] = body.settings` -- a full replace, not a merge.
**How to avoid:** This is an existing limitation, not introduced by this phase. Document it but don't fix it here. Admin users setting model config should include the full settings dict. A deep-merge endpoint is a separate concern.

### Pitfall 5: Default model mismatch
**What goes wrong:** Using different default model strings in the helper vs what was hardcoded, changing behavior for existing tenants.
**Why it happens:** The spec says default to `claude-sonnet-4-6` but some engines currently use Haiku.
**How to avoid:** This is an intentional upgrade. The spec explicitly says default should be `claude-sonnet-4-6`. The phase is upgrading scoring/voice from Haiku to Sonnet as the new default. Document this clearly in the plan as an intentional behavior change. Cost implications should be noted.

## Code Examples

### Helper function usage in email_scorer.py

```python
# At top of file, replace:
#   _HAIKU_MODEL = "claude-haiku-4-5-20251001"
# With:
from flywheel.engines.model_config import get_engine_model

# Inside score_email(), before the API call:
model = await get_engine_model(db, tenant_id, "scoring")
client = anthropic.AsyncAnthropic(api_key=effective_api_key)
response = await client.messages.create(
    model=model,
    max_tokens=500,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}],
)
```

### Helper function usage in gmail_sync.py (voice extraction)

```python
# At top of file (near other imports):
from flywheel.engines.model_config import get_engine_model

# Modify _extract_voice_profile to accept model parameter:
async def _extract_voice_profile(bodies: list[str], model: str = "claude-sonnet-4-6") -> dict:
    client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
    response = await client.messages.create(
        model=model,  # was _HAIKU_MODEL
        max_tokens=1000,
        system=VOICE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n---\n\n".join(bodies)}],
    )
    # ... rest unchanged

# In voice_profile_init, resolve model and pass it:
async def voice_profile_init(db: AsyncSession, integration: Integration) -> bool:
    # ... existing idempotency check ...
    model = await get_engine_model(db, integration.tenant_id, "voice_extraction")
    # ... later ...
    profile = await _extract_voice_profile(substantive_bodies[:20], model=model)
```

### Setting model config via existing API

```bash
# Admin sets a custom model for the scoring engine
curl -X PATCH /api/v1/tenants/current \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "settings": {
      "email_engine_models": {
        "scoring": "claude-haiku-4-5-20251001"
      },
      "entity_aliases": { ... },  # must include existing settings!
      "member_limit": 5
    }
  }'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Haiku for scoring/voice | Sonnet as default for all engines | This phase | Cost increase, quality increase |
| Hardcoded per-file constants | Tenant-configurable via JSONB | This phase | Per-tenant model selection without code changes |

**Note on model naming:** The codebase currently mixes `claude-sonnet-4-6` (in email_drafter.py) and `claude-sonnet-4-20250514` (in skill_executor.py and cost_tracker.py). The spec uses `claude-sonnet-4-6` as the default. Both are valid Anthropic model strings (one is an alias). Use `claude-sonnet-4-6` as the default per spec.

## Open Questions

1. **Cost impact of defaulting all engines to Sonnet**
   - What we know: Scoring and voice currently use Haiku ($1/$5 per M tokens). Sonnet is $3/$15 per M tokens. This is a 3x cost increase for those engines.
   - What's unclear: Whether the spec intends this cost increase or expects Haiku to remain the default for scoring/voice.
   - Recommendation: Follow the spec as written (default `claude-sonnet-4-6`). Tenants can override back to Haiku via settings if cost is a concern. The model config infrastructure makes this trivial.

2. **Should cost_tracker.py be updated to handle `claude-sonnet-4-6` alias?**
   - What we know: `cost_tracker.py` has pricing for `claude-sonnet-4-20250514` but not `claude-sonnet-4-6`. The drafter already uses `claude-sonnet-4-6`.
   - What's unclear: Whether the SDK normalizes model names in responses.
   - Recommendation: Add `claude-sonnet-4-6` as an alias in cost_tracker pricing. Out of scope for this phase but worth noting.

3. **Full settings replacement on PATCH**
   - What we know: The PATCH endpoint replaces the entire `settings` dict, not deep-merging.
   - Recommendation: Out of scope for this phase. Document the limitation. A future phase could add a deep-merge settings endpoint.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** - Direct reading of all 5 engine files, tenant model, config module, and existing settings access patterns
- `backend/src/flywheel/db/models.py:56` - Tenant.settings JSONB column definition
- `backend/src/flywheel/services/entity_normalization.py:91-98` - Existing tenant settings read pattern
- `backend/src/flywheel/api/tenant.py:208-243` - Existing PATCH settings endpoint
- `backend/src/flywheel/config.py` - App-level settings via Pydantic

### Secondary (MEDIUM confidence)
- Phase description and spec requirements (provided as input)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, existing patterns only
- Architecture: HIGH - follows established codebase patterns exactly
- Pitfalls: HIGH - identified from direct code reading, patterns are simple
- Default model values: MEDIUM - spec says `claude-sonnet-4-6` but this changes behavior for Haiku engines

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain, no external dependency changes expected)
