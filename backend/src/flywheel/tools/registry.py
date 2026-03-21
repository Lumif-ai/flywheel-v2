"""Tool registry for skill execution.

Manages tool definitions, provides Anthropic-format tool lists,
and dispatches tool calls with budget enforcement.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Awaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from flywheel.tools.budget import RunBudget


@dataclass
class RunContext:
    """Context passed to every tool handler during a skill run.

    Carries tenant isolation, run identity, budget tracking,
    and a session factory for database access.
    """

    tenant_id: UUID
    user_id: UUID
    run_id: UUID
    budget: RunBudget
    session_factory: async_sessionmaker[AsyncSession]
    focus_id: UUID | None = None


@dataclass
class ToolDefinition:
    """A registered tool with its schema and handler."""

    name: str
    version: int
    schema: dict
    handler: Callable[..., Awaitable[str]]
    requires_budget: str | None = None


class ToolRegistry:
    """Registry of available tools for skill execution.

    Tools are registered at startup and looked up during execution.
    The registry produces Anthropic-format tool definitions and
    dispatches tool calls with budget checking.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool

    def get_anthropic_tools(self, skill_name: str | None = None) -> list[dict]:
        """Return tool definitions in Anthropic API format.

        Args:
            skill_name: Optional skill filter (not implemented yet --
                        skill-level filtering is Phase 26.1 Plan 03).

        Returns:
            List of dicts with name, description, and input_schema keys.
        """
        # For now, return ALL registered tools regardless of skill_name
        tools = []
        for tool in self._tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.schema.get("description", ""),
                "input_schema": tool.schema.get("input_schema", {}),
            })
        return tools

    async def execute(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: RunContext,
    ) -> str:
        """Execute a tool by name with budget enforcement.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Tool input parameters.
            context: Run context with budget and session factory.

        Returns:
            Tool result string. Never raises -- returns error strings.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return f"Unknown tool: {tool_name}"

        # Budget check
        if tool.requires_budget:
            if not context.budget.can_use(tool.requires_budget):
                return f"{tool.requires_budget} budget exhausted for this run."
            context.budget.use(tool.requires_budget)

        try:
            return await tool.handler(tool_input, context)
        except Exception as e:
            return f"Tool execution error: {e}"

    def snapshot_tools(self, skill_name: str | None = None) -> list[dict]:
        """Return a frozen copy of tool definitions.

        Used for storing in skill_run at start, per version safety
        design decision -- ensures the tool definitions don't change
        mid-run even if registry is modified.
        """
        return copy.deepcopy(self.get_anthropic_tools(skill_name))
