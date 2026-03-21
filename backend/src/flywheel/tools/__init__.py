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

    # Web tools (budget-tracked)
    from flywheel.tools.web_search import handle_web_search
    from flywheel.tools.web_fetch import handle_web_fetch

    registry.register(ToolDefinition(
        name="web_search",
        version=1,
        schema=TOOL_SCHEMAS["web_search"],
        handler=handle_web_search,
        requires_budget="web_search",
    ))
    registry.register(ToolDefinition(
        name="web_fetch",
        version=1,
        schema=TOOL_SCHEMAS["web_fetch"],
        handler=handle_web_fetch,
        requires_budget="web_fetch",
    ))

    # File tools and python_execute are registered in Plan 02
    # (handlers not yet implemented)

    return registry
