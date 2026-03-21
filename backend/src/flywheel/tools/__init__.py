"""Tool system for Flywheel skill execution.

Provides a registry of server-side tools that Claude can use during
skill runs, along with budget tracking and Anthropic API integration.

Public API:
- ToolRegistry: Manages tool registration and execution
- ToolDefinition: Dataclass for tool metadata + handler
- RunContext: Per-run context (tenant, user, budget, session)
- RunBudget: Per-run usage limits for web search/fetch
- TOOL_SCHEMAS: Anthropic-format schema definitions
- create_registry(): Factory that creates a fully-loaded registry
"""

from flywheel.tools.registry import ToolRegistry, ToolDefinition, RunContext
from flywheel.tools.budget import RunBudget
from flywheel.tools.schemas import TOOL_SCHEMAS

__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "RunContext",
    "RunBudget",
    "TOOL_SCHEMAS",
    "create_registry",
]


def create_registry() -> ToolRegistry:
    """Create a ToolRegistry with all available tools registered.

    Imports handlers lazily inside the function to avoid ImportError
    when optional dependencies (e.g., tavily-python) aren't installed.
    """
    registry = ToolRegistry()

    # Context tools (always available)
    from flywheel.tools.context_tools import (
        handle_context_read,
        handle_context_write,
        handle_context_query,
    )

    registry.register(ToolDefinition(
        name="context_read",
        version=1,
        schema=TOOL_SCHEMAS["context_read"],
        handler=handle_context_read,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="context_write",
        version=1,
        schema=TOOL_SCHEMAS["context_write"],
        handler=handle_context_write,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="context_query",
        version=1,
        schema=TOOL_SCHEMAS["context_query"],
        handler=handle_context_query,
        requires_budget=None,
    ))

    # Web tools (budget-tracked, tavily dependency is optional)
    try:
        from flywheel.tools.web_search import handle_web_search

        registry.register(ToolDefinition(
            name="web_search",
            version=1,
            schema=TOOL_SCHEMAS["web_search"],
            handler=handle_web_search,
            requires_budget="web_search",
        ))
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "tavily-python not installed -- web_search tool unavailable"
        )

    from flywheel.tools.web_fetch import handle_web_fetch

    registry.register(ToolDefinition(
        name="web_fetch",
        version=1,
        schema=TOOL_SCHEMAS["web_fetch"],
        handler=handle_web_fetch,
        requires_budget="web_fetch",
    ))

    # File I/O tools (no budget)
    from flywheel.tools.file_tools import handle_file_read, handle_file_write

    registry.register(ToolDefinition(
        name="file_read",
        version=1,
        schema=TOOL_SCHEMAS["file_read"],
        handler=handle_file_read,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="file_write",
        version=1,
        schema=TOOL_SCHEMAS["file_write"],
        handler=handle_file_write,
        requires_budget=None,
    ))

    # Python sandbox (no budget)
    from flywheel.tools.python_execute import handle_python_execute

    registry.register(ToolDefinition(
        name="python_execute",
        version=1,
        schema=TOOL_SCHEMAS["python_execute"],
        handler=handle_python_execute,
        requires_budget=None,
    ))

    # Browser tools (require local agent connection, no budget)
    from flywheel.tools.browser_tools import (
        handle_browser_navigate,
        handle_browser_click,
        handle_browser_type,
        handle_browser_extract,
        handle_browser_screenshot,
    )

    registry.register(ToolDefinition(
        name="browser_navigate",
        version=1,
        schema=TOOL_SCHEMAS["browser_navigate"],
        handler=handle_browser_navigate,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="browser_click",
        version=1,
        schema=TOOL_SCHEMAS["browser_click"],
        handler=handle_browser_click,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="browser_type",
        version=1,
        schema=TOOL_SCHEMAS["browser_type"],
        handler=handle_browser_type,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="browser_extract",
        version=1,
        schema=TOOL_SCHEMAS["browser_extract"],
        handler=handle_browser_extract,
        requires_budget=None,
    ))
    registry.register(ToolDefinition(
        name="browser_screenshot",
        version=1,
        schema=TOOL_SCHEMAS["browser_screenshot"],
        handler=handle_browser_screenshot,
        requires_budget=None,
    ))

    return registry
