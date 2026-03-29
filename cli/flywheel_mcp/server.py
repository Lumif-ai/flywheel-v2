"""Flywheel MCP server -- exposes Flywheel skills and context to Claude Code."""

from __future__ import annotations

import time

from fastmcp import FastMCP

from flywheel_mcp.api_client import FlywheelAPIError, FlywheelClient

mcp = FastMCP("Flywheel")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_run_skill(
    skill_name: str = "meeting-prep",
    input_text: str = "",
) -> str:
    """Run a Flywheel skill like meeting-prep, company-intel, or flywheel.

    Use for business intelligence: preparing for meetings, researching
    companies, analyzing competitors, gathering market signals.
    Use 'flywheel' for the daily operating ritual: syncs meetings,
    processes recordings, preps upcoming meetings, and executes tasks.
    Returns a link to view the full results in the Flywheel web app.
    NOT for coding, file operations, or development tasks.
    """
    try:
        client = FlywheelClient()
        result = client.start_skill_run(skill_name, input_text)
        run_id = result.get("run_id") or result.get("id")
        if not run_id:
            return f"Skill run started but no run_id returned: {result}"

        # Poll with exponential backoff: 3s, 5s, 8s, then 10s intervals
        intervals = [3, 5, 8] + [10] * 27  # ~5 min total
        elapsed = 0
        for wait in intervals:
            time.sleep(wait)
            elapsed += wait
            run = client.get_run(run_id)
            status = run.get("status", "unknown")

            if status == "completed":
                url = f"{client.frontend_url}/library"
                return f"Skill '{skill_name}' completed. View results: {url}"

            if status == "failed":
                error = run.get("error") or run.get("error_message") or "Unknown error"
                return f"Skill '{skill_name}' failed: {error}"

        # Timeout
        url = f"{client.frontend_url}/library"
        return (
            f"Skill '{skill_name}' still running after {elapsed}s. "
            f"Check status: {url}"
        )
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error running skill: {exc}"


@mcp.tool()
def flywheel_read_context(query: str) -> str:
    """Search Flywheel's business knowledge base.

    Use for: company intel, people profiles, market signals, competitive
    intelligence, deal context, meeting history.
    Returns stored business knowledge that compounds over time.
    NOT for code documentation, README files, or project configs.
    """
    try:
        client = FlywheelClient()
        results = client.search_context(query)
        items = results.get("items", [])

        if not items:
            return (
                f"No context found for '{query}'. "
                "Try a different search term, or add context with flywheel_write_context."
            )

        lines = []
        for entry in items[:10]:
            file_name = entry.get("file_name", "unknown")
            confidence = entry.get("confidence", "?")
            content = entry.get("content", "")
            lines.append(f"[{file_name}] ({confidence}) {content}")

        return "\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error reading context: {exc}"


@mcp.tool()
def flywheel_write_context(
    content: str,
    file_name: str = "market-signals",
) -> str:
    """Store business knowledge in Flywheel's context store.

    Use for: facts about people, companies, deals, markets, competitors,
    industry signals, relationship notes, meeting outcomes.
    NOT for coding preferences, tool configs, or project setup.
    Common file names: market-signals, competitive-intel, icp-profiles,
    leadership, company-details, positioning.
    """
    try:
        client = FlywheelClient()
        result = client.write_context(file_name, content)
        entry = result.get("entry", {})
        entry_id = entry.get("id", "unknown")
        return f"Added to {file_name}. Entry ID: {entry_id}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error writing context: {exc}"


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main():
    """Start the Flywheel MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
