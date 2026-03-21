"""Web search tool handler using Tavily API.

Returns structured search results for skill execution.
Budget-tracked via RunBudget (max 20 searches per run).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flywheel.tools.registry import RunContext


# TODO: Per-tenant daily search cap (deferred -- per-run budget only for launch)


async def handle_web_search(tool_input: dict, context: RunContext) -> str:
    """Search the web using Tavily API.

    Returns up to 5 results formatted as title + URL + snippet.
    Returns informational error string if Tavily is not configured
    or if the search fails.
    """
    query = tool_input.get("query")
    if not query:
        return "Error: query is required"

    from flywheel.config import settings

    if not settings.tavily_api_key:
        return "Web search is not configured. The Tavily API key is not set."

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=False,
            include_raw_content=False,
        )

        results = response.get("results", [])
        if not results:
            return f"No results found for: {query}"

        formatted = []
        for r in results:
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            snippet = r.get("content", "")
            formatted.append(f"**{title}**\n{url}\n{snippet}")

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search failed: {e}"
