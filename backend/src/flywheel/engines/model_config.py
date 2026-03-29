"""model_config.py - Per-tenant engine model configuration.

Provides a shared helper for resolving which Claude model to use for each
email engine (scoring, drafting, voice extraction, voice learning, context
extraction). Models are configurable per tenant via the
``settings["email_engine_models"]`` JSONB path on the Tenant row.

When no tenant-level override exists, ENGINE_DEFAULTS supplies the fallback.

Functions:
  get_engine_model(db, tenant_id, engine_key, default) -> str
    Async helper that reads tenant settings and returns the configured model
    string, falling back to ENGINE_DEFAULTS on any missing key or error.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Tenant

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults — all engines default to Sonnet for v7.0
# ---------------------------------------------------------------------------

ENGINE_DEFAULTS: dict[str, str] = {
    "scoring": "claude-sonnet-4-6",
    "voice_extraction": "claude-sonnet-4-6",
    "voice_learning": "claude-sonnet-4-6",
    "drafting": "claude-sonnet-4-6",
    "context_extraction": "claude-sonnet-4-6",
}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


async def get_engine_model(
    db: AsyncSession,
    tenant_id: UUID,
    engine_key: str,
    default: str = "claude-sonnet-4-6",
) -> str:
    """Resolve the Claude model for a given engine and tenant.

    Reads ``Tenant.settings["email_engine_models"][engine_key]`` from the
    database. Returns the configured string when present, otherwise falls back
    to ``ENGINE_DEFAULTS[engine_key]`` (or *default* if the key is unknown).

    This is a **read-only** query -- no commits or flushes are issued.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID.
        engine_key: One of the ENGINE_DEFAULTS keys (e.g. ``"scoring"``).
        default: Ultimate fallback if engine_key is not in ENGINE_DEFAULTS.

    Returns:
        Model identifier string (e.g. ``"claude-sonnet-4-6"``).
    """
    try:
        result = await db.execute(
            select(Tenant.settings).where(Tenant.id == tenant_id)
        )
        settings = result.scalar_one_or_none()

        if settings and isinstance(settings, dict):
            engine_models = settings.get("email_engine_models")
            if isinstance(engine_models, dict):
                model = engine_models.get(engine_key)
                if model and isinstance(model, str) and model.strip():
                    if not model.startswith("claude-"):
                        logger.warning(
                            "Tenant %s engine %s configured with non-Claude model: %s",
                            tenant_id,
                            engine_key,
                            model,
                        )
                    return model.strip()

        return ENGINE_DEFAULTS.get(engine_key, default)

    except Exception:
        logger.warning(
            "Failed to read engine model config for tenant_id=%s engine_key=%s; "
            "using default",
            tenant_id,
            engine_key,
            exc_info=True,
        )
        return ENGINE_DEFAULTS.get(engine_key, default)
