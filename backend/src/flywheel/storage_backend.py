"""Strangler Fig selector: routes API calls to flat-file, Postgres, or remote backend.

The FLYWHEEL_BACKEND env var controls which backend is active:
  - "flatfile" (default): Uses v1 context_utils.py markdown-based storage
  - "postgres": Uses SQLAlchemy/asyncpg with Supabase Postgres
  - "remote": Routes all calls through HTTP to a hosted Flywheel API (requires flywheel-cli package)

All callers import from this module, never directly from context_utils or postgres_backend.
"""

import os

_backend = os.environ.get("FLYWHEEL_BACKEND", "flatfile").lower()

if _backend == "postgres":
    from flywheel.storage import (  # noqa: F401
        append_entry,
        batch_context,
        list_context_files,
        log_event,
        query_context,
        read_context,
    )

    # parse_context_file is backend-independent (parses markdown text)
    from flywheel.context_utils import parse_context_file  # noqa: F401

elif _backend == "flatfile":
    from flywheel.context_utils import (  # noqa: F401
        append_entry,
        batch_context,
        list_context_files,
        log_event,
        parse_context_file,
        query_context,
        read_context,
    )
elif _backend == "remote":
    from flywheel_cli.http_context import (  # noqa: F401
        append_entry,
        batch_context,
        list_context_files,
        log_event,
        parse_context_file,
        query_context,
        read_context,
    )
else:
    raise ValueError(
        f"Unknown FLYWHEEL_BACKEND value: {_backend!r}. "
        "Expected 'flatfile', 'postgres', or 'remote'."
    )

__all__ = [
    "read_context",
    "append_entry",
    "query_context",
    "batch_context",
    "list_context_files",
    "parse_context_file",
    "log_event",
]
