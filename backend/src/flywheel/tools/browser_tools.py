"""Browser tool handlers for local agent browser automation.

Each handler sends a command to the user's local agent via the AgentManager
and returns the result as a string. Requires the user's local CLI agent
to be connected via WebSocket.

Public API:
    handle_browser_navigate(params, context) -> str
    handle_browser_click(params, context) -> str
    handle_browser_type(params, context) -> str
    handle_browser_extract(params, context) -> str
    handle_browser_screenshot(params, context) -> str
"""

from __future__ import annotations

import logging

from flywheel.services.agent_manager import (
    agent_manager,
    AgentNotConnectedError,
    AgentTimeoutError,
)
from flywheel.tools.registry import RunContext

logger = logging.getLogger(__name__)

_NOT_CONNECTED_MSG = (
    "AGENT_NOT_CONNECTED: Local agent not connected. "
    "Start with: flywheel agent start"
)
_TIMEOUT_MSG = "AGENT_TIMEOUT: Browser command timed out (15s)."


async def handle_browser_navigate(params: dict, context: RunContext) -> str:
    """Navigate to a URL in the local browser agent."""
    command = {"type": "navigate", "url": params["url"]}
    try:
        result = await agent_manager.send_command(
            context.user_id, command, timeout=15.0
        )
        if result.get("status") == "error":
            return f"Browser error: {result.get('error', 'unknown')}"
        return result.get("content", "OK")
    except AgentNotConnectedError:
        return _NOT_CONNECTED_MSG
    except AgentTimeoutError:
        return _TIMEOUT_MSG


async def handle_browser_click(params: dict, context: RunContext) -> str:
    """Click an element by CSS selector in the local browser."""
    selector = params["selector"]
    command = {"type": "click", "selector": selector}
    try:
        result = await agent_manager.send_command(
            context.user_id, command, timeout=15.0
        )
        if result.get("status") == "error":
            return f"Browser error: {result.get('error', 'unknown')}"
        return f"Clicked {selector}"
    except AgentNotConnectedError:
        return _NOT_CONNECTED_MSG
    except AgentTimeoutError:
        return _TIMEOUT_MSG


async def handle_browser_type(params: dict, context: RunContext) -> str:
    """Type text into a form field by CSS selector in the local browser."""
    selector = params["selector"]
    text = params["text"]
    command = {"type": "type", "selector": selector, "text": text}
    try:
        result = await agent_manager.send_command(
            context.user_id, command, timeout=15.0
        )
        if result.get("status") == "error":
            return f"Browser error: {result.get('error', 'unknown')}"
        return f"Typed into {selector}"
    except AgentNotConnectedError:
        return _NOT_CONNECTED_MSG
    except AgentTimeoutError:
        return _TIMEOUT_MSG


async def handle_browser_extract(params: dict, context: RunContext) -> str:
    """Extract text content from a specific element by CSS selector."""
    selector = params["selector"]
    command = {"type": "extract", "selector": selector}
    try:
        result = await agent_manager.send_command(
            context.user_id, command, timeout=15.0
        )
        if result.get("status") == "error":
            return f"Browser error: {result.get('error', 'unknown')}"
        return result.get("content", "")
    except AgentNotConnectedError:
        return _NOT_CONNECTED_MSG
    except AgentTimeoutError:
        return _TIMEOUT_MSG


async def handle_browser_screenshot(params: dict, context: RunContext) -> str:
    """Take a screenshot of the current page in the local browser."""
    command = {"type": "screenshot"}
    try:
        result = await agent_manager.send_command(
            context.user_id, command, timeout=15.0
        )
        if result.get("status") == "error":
            return f"Browser error: {result.get('error', 'unknown')}"
        return result.get("content", "")
    except AgentNotConnectedError:
        return _NOT_CONNECTED_MSG
    except AgentTimeoutError:
        return _TIMEOUT_MSG
