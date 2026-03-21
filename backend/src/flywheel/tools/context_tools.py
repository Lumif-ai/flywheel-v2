"""Context store tool handlers for skill execution.

Provides read, write, and query operations on tenant-scoped context
entries via the storage layer. All handlers return strings (never raise).

Focus-aware: passes focus_id from RunContext to session and storage,
applies focus-weighted reranking on reads.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flywheel.tools.registry import RunContext


def _focus_id_str(context: RunContext) -> str | None:
    """Extract focus_id as string from RunContext, or None."""
    return str(context.focus_id) if context.focus_id else None


async def handle_context_read(tool_input: dict, context: RunContext) -> str:
    """Read all entries from a context file.

    When context.focus_id is set, applies focus-weighted reranking so
    focus-matched entries appear first in the output. This naturally
    causes the LLM to produce different (more relevant) outputs per focus.
    """
    from flywheel.db.session import get_tenant_session
    from flywheel import storage

    file = tool_input.get("file")
    if not file:
        return "Error: file is required"

    focus_id = _focus_id_str(context)

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
            focus_id=focus_id,
        )

        if focus_id:
            # Focus-weighted reranking: use query_context to get structured
            # entries with focus_id metadata, then rerank by focus relevance.
            entries = await storage.query_context(session, file)
            if not entries:
                return f"No entries found in {file}"

            # Apply focus weighting:
            # - focus_id matches context.focus_id -> weight 1.0
            # - focus_id is None (unfocused) -> weight 0.8
            # - focus_id is different -> weight 0.5
            def _focus_weight(entry_focus_id: str | None) -> float:
                if entry_focus_id == focus_id:
                    return 1.0
                elif entry_focus_id is None:
                    return 0.8
                else:
                    return 0.5

            # Stable-sort by (focus_weight * evidence_count) descending
            sorted_entries = sorted(
                entries,
                key=lambda e: _focus_weight(e.get("focus_id")) * (e.get("evidence_count", 1) or 1),
                reverse=True,
            )

            # Format entries like storage._format_entry
            lines = []
            for e in sorted_entries:
                detail_part = f" | {e['detail']}" if e.get("detail") else ""
                header = (
                    f"[{e['date']} | source: {e['source']}{detail_part}] "
                    f"confidence: {e['confidence']} | evidence: {e['evidence_count']}"
                )
                content = e.get("content", "").strip()
                content_lines = []
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped:
                        if stripped.startswith("- "):
                            content_lines.append(stripped)
                        else:
                            content_lines.append(f"- {stripped}")
                body = "\n".join(content_lines)
                lines.append(f"{header}\n{body}")

            return "\n\n".join(lines)
        else:
            # No focus -- return content as-is (no reranking needed)
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

    Passes focus_id from RunContext to session so entries are auto-tagged
    with the user's active focus.
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
    focus_id = _focus_id_str(context)

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
            focus_id=focus_id,
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
    focus_id = _focus_id_str(context)

    session = None
    try:
        session = await get_tenant_session(
            context.session_factory,
            str(context.tenant_id),
            str(context.user_id),
            focus_id=focus_id,
        )
        # query_context requires file as positional arg
        if file:
            results = await storage.query_context(session, file, search=search)
        else:
            # Search across all files
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
