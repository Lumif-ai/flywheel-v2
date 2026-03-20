"""Strangler Fig selector: routes API calls to flat-file or Postgres backend.

The FLYWHEEL_BACKEND env var controls which backend is active:
  - "flatfile" (default): Uses v1 context_utils.py markdown-based storage
  - "postgres": Will use SQLAlchemy/asyncpg (Phase 16)

All callers import from this module, never directly from context_utils or postgres_backend.
"""

import os

_backend = os.environ.get("FLYWHEEL_BACKEND", "flatfile").lower()

if _backend == "postgres":
    from flywheel.storage import (  # noqa: F401
        append_entry,
        batch_context,
        query_context,
        read_context,
    )
elif _backend == "flatfile":
    from flywheel.context_utils import (  # noqa: F401
        append_entry,
        batch_context,
        query_context,
        read_context,
    )
else:
    raise ValueError(
        f"Unknown FLYWHEEL_BACKEND value: {_backend!r}. "
        "Expected 'flatfile' or 'postgres'."
    )

__all__ = ["read_context", "append_entry", "query_context", "batch_context"]
