"""Context store tool handlers for skill execution.

Provides read, write, and query operations on tenant-scoped context
entries via the storage layer. All handlers return strings (never raise).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flywheel.tools.registry import RunContext


async def handle_context_read(tool_input: dict, context: RunContext) -> str:
    """Read all entries from a context file.

    Returns formatted context entries or an informational message
    if the file is empty or missing.
    """
    from flywheel.db.session import get_tenant_session
    from flywheel import storage

    file = tool_input.get("file")
    if not file:
        return "Error: file is required"

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
        )
        content = await storage.read_context(session, file)
        if not content:
            return f"No entries found in {file}"
        return content
    except Exception as e:
        return f"Error reading context: {e}"
    finally:
        if session is not None:
            await session.close()


async def handle_context_write(tool_input: dict, context: RunContext) -> str:
    """Write a new entry to a context file.

    Extracts file, content (list[str]), detail, and confidence from
    tool_input. Calls storage.append_entry with tenant-scoped session.
    """
    from flywheel.db.session import get_tenant_session
    from flywheel import storage

    file = tool_input.get("file")
    if not file:
        return "Error: file is required"

    content = tool_input.get("content")
    if not content:
        return "Error: content is required"

    detail = tool_input.get("detail")
    if not detail:
        return "Error: detail is required"

    confidence = tool_input.get("confidence", "medium")

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
        )
        entry = {
            "content": content,
            "detail": detail,
            "confidence": confidence,
        }
        await storage.append_entry(session, file=file, entry=entry, source="skill-run")
        await session.commit()
        return f"Entry written to {file}"
    except Exception as e:
        return f"Error writing context: {e}"
    finally:
        if session is not None:
            await session.close()


async def handle_context_query(tool_input: dict, context: RunContext) -> str:
    """Search context entries using full-text search.

    Optionally filters by context file. Returns formatted results
    ranked by relevance.
    """
    from flywheel.db.session import get_tenant_session
    from flywheel import storage

    search = tool_input.get("search")
    if not search:
        return "Error: search is required"

    file = tool_input.get("file")

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
        )
        # query_context requires file as positional arg
        # Pass search as keyword arg, file filter via the file positional
        if file:
            results = await storage.query_context(session, file, search=search)
        else:
            # When no file filter, we need to search across all files.
            # query_context requires file -- use a broad approach:
            # list files then query each, or pass empty string.
            # Looking at storage.py, file is a positional arg that filters
            # by file_name. We need to query without file filter.
            # For now, search across all files by listing them first.
            from flywheel.storage import list_context_files
            files = await list_context_files(session)
            results = []
            for f in files:
                file_results = await storage.query_context(session, f, search=search)
                results.extend(file_results)

        if not results:
            return "No matching entries"

        # Format results for readability
        formatted = []
        for r in results:
            lines = [
                f"**{r.get('file_name', r.get('detail', 'Entry'))}**",
                f"Source: {r.get('source', 'unknown')} | "
                f"Date: {r.get('date', 'unknown')} | "
                f"Confidence: {r.get('confidence', 'medium')}",
            ]
            content = r.get("content", "")
            if content:
                # Show first 200 chars of content
                preview = content[:200]
                if len(content) > 200:
                    preview += "..."
                lines.append(preview)
            formatted.append("\n".join(lines))

        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Error querying context: {e}"
    finally:
        if session is not None:
            await session.close()
