"""Async Supabase admin client singleton.

Used ONLY for auth admin operations (magic link, anonymous sign-in,
invite, promote). NOT for data queries -- those go through SQLAlchemy.

Strategy: Use supabase-py's async client (``create_async_client``).
If the async auth surface is incomplete, falls back to the sync client
with ``asyncio.to_thread()`` for auth calls.
"""

from __future__ import annotations

from typing import Any

from flywheel.config import settings

_admin_client: Any = None


async def get_supabase_admin() -> Any:
    """Lazy singleton returning the async Supabase admin client.

    Uses the service_role key for full admin access (bypasses RLS).
    """
    global _admin_client
    if _admin_client is not None:
        return _admin_client

    try:
        from supabase._async.client import create_async_client

        _admin_client = await create_async_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
    except (ImportError, AttributeError):
        # Fallback: sync client -- auth calls wrapped in asyncio.to_thread()
        from supabase import create_client

        _admin_client = create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )

    return _admin_client
