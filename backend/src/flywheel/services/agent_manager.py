"""Agent connection manager for local browser agent WebSocket connections.

Tracks one WebSocket connection per user, dispatches browser commands to
the connected agent, and awaits results using asyncio Futures with timeout.

Public API:
    agent_manager: Module-level singleton AgentManager instance
    AgentManager: Connection manager class
    AgentNotConnectedError: Raised when no agent is connected for a user
    AgentTimeoutError: Raised when a command times out waiting for response
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AgentNotConnectedError(Exception):
    """Raised when attempting to send a command but no agent is connected."""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"No agent connected for user {user_id}")


class AgentTimeoutError(Exception):
    """Raised when a command response is not received within the timeout."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        super().__init__(f"Agent command timed out: {request_id}")


class AgentManager:
    """Manages WebSocket connections from local browser agents.

    Enforces single-session per user: if a user connects from a new agent,
    the previous connection is closed with code 4002.

    Commands are dispatched via send_command() which creates an asyncio Future,
    sends the command as JSON over the WebSocket, and waits for the agent to
    respond with a matching request_id.
    """

    def __init__(self) -> None:
        self._agents: dict[UUID, WebSocket] = {}
        self._metadata: dict[UUID, dict] = {}
        self._pending: dict[str, asyncio.Future] = {}
        # Index: user_id -> set of request_ids for cleanup on disconnect
        self._user_requests: dict[UUID, set[str]] = {}

    async def register(
        self, user_id: UUID, websocket: WebSocket, hostname: str = "unknown"
    ) -> None:
        """Register a new agent connection for a user.

        If the user already has an active connection, close the old one
        with code 4002 before registering the new one.
        """
        if user_id in self._agents:
            old_ws = self._agents[user_id]
            try:
                await old_ws.close(
                    code=4002,
                    reason=f"Replaced by new connection from {hostname}",
                )
            except Exception:
                pass  # Old connection may already be dead
            logger.info(
                "Replaced existing agent connection for user %s (new host: %s)",
                user_id,
                hostname,
            )

        self._agents[user_id] = websocket
        self._metadata[user_id] = {
            "hostname": hostname,
            "connect_time": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Agent registered for user %s from %s", user_id, hostname)

    def unregister(self, user_id: UUID) -> None:
        """Remove an agent connection and cancel any pending command Futures."""
        self._agents.pop(user_id, None)
        self._metadata.pop(user_id, None)

        # Cancel all pending Futures for this user
        request_ids = self._user_requests.pop(user_id, set())
        for rid in request_ids:
            future = self._pending.pop(rid, None)
            if future is not None and not future.done():
                future.cancel()

        logger.info("Agent unregistered for user %s", user_id)

    def is_connected(self, user_id: UUID) -> bool:
        """Check whether a user has an active agent connection."""
        return user_id in self._agents

    def get_status(self, user_id: UUID) -> dict | None:
        """Return metadata for the user's agent connection, or None."""
        return self._metadata.get(user_id)

    async def send_command(
        self, user_id: UUID, command: dict, timeout: float = 15.0
    ) -> dict:
        """Send a command to the user's agent and wait for the response.

        Args:
            user_id: The user whose agent should execute the command.
            command: Command dict (will have request_id added automatically).
            timeout: Maximum seconds to wait for a response.

        Returns:
            The result dict from the agent.

        Raises:
            AgentNotConnectedError: If no agent is connected for the user.
            AgentTimeoutError: If the agent does not respond within timeout.
        """
        ws = self._agents.get(user_id)
        if ws is None:
            raise AgentNotConnectedError(user_id)

        request_id = str(uuid4())
        command["request_id"] = request_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        # Track request_id for this user (cleanup on disconnect)
        if user_id not in self._user_requests:
            self._user_requests[user_id] = set()
        self._user_requests[user_id].add(request_id)

        try:
            await ws.send_json(command)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            self._user_requests.get(user_id, set()).discard(request_id)
            raise AgentTimeoutError(request_id)
        except Exception:
            self._pending.pop(request_id, None)
            self._user_requests.get(user_id, set()).discard(request_id)
            raise

    async def handle_message(self, user_id: UUID, message: dict) -> None:
        """Handle an incoming message from an agent.

        Matches the message's request_id to a pending Future and resolves it.
        Ignores messages with unknown request_ids (stale responses after reconnect).
        """
        request_id = message.get("request_id")
        if request_id is None:
            logger.debug("Agent message from user %s has no request_id", user_id)
            return

        future = self._pending.pop(request_id, None)
        if future is None:
            logger.debug(
                "No pending future for request_id %s (stale response)", request_id
            )
            return

        # Clean up user request tracking
        self._user_requests.get(user_id, set()).discard(request_id)

        if not future.done():
            future.set_result(message)


# Module-level singleton
agent_manager = AgentManager()
