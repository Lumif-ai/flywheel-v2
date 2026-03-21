"""WebSocket endpoint for local browser agent connections.

Accepts authenticated WebSocket connections from the local CLI agent,
registers them with the AgentManager, and forwards messages between
the agent and pending command Futures.

Public API:
    router: FastAPI APIRouter with WebSocket and REST endpoints
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from flywheel.api.deps import get_current_user
from flywheel.auth.jwt import TokenPayload, decode_jwt
from flywheel.services.agent_manager import agent_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_ws_token(token: str) -> UUID | None:
    """Verify a JWT token for WebSocket authentication.

    WebSocket connections cannot use HTTP headers for auth, so the token
    is passed as a query parameter. Returns the user UUID on success,
    or None on any JWT error.
    """
    try:
        payload: TokenPayload = decode_jwt(token)
        return payload.sub
    except Exception:
        return None


@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for local browser agent connections.

    Authentication is via JWT token in query parameter. The agent sends
    command responses as JSON messages with matching request_ids.

    Protocol:
    1. Client connects with ?token=<JWT>
    2. Server verifies token, accepts connection
    3. Client optionally sends {"hostname": "..."} as first message
    4. Server registers agent with AgentManager
    5. Server receives JSON messages and routes to handle_message
    6. On disconnect, server unregisters agent
    """
    user_id = await _verify_ws_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    # Read optional hostname from first message
    hostname = "unknown"
    try:
        first_msg = await websocket.receive_json()
        if isinstance(first_msg, dict) and "hostname" in first_msg:
            hostname = first_msg["hostname"]
        else:
            # Not a hostname message -- treat as a regular command response
            await agent_manager.register(user_id, websocket, hostname)
            await agent_manager.handle_message(user_id, first_msg)
            # Continue to receive loop below (skip the register after this block)
            try:
                while True:
                    data = await websocket.receive_json()
                    await agent_manager.handle_message(user_id, data)
            except WebSocketDisconnect:
                pass
            finally:
                agent_manager.unregister(user_id)
            return
    except WebSocketDisconnect:
        return
    except Exception:
        # If first receive fails, just use default hostname
        pass

    await agent_manager.register(user_id, websocket, hostname)

    try:
        while True:
            data = await websocket.receive_json()
            await agent_manager.handle_message(user_id, data)
    except WebSocketDisconnect:
        pass
    finally:
        agent_manager.unregister(user_id)


@router.get("/agent/status")
async def agent_status(user: TokenPayload = Depends(get_current_user)):
    """Check whether the current user's local agent is connected.

    Returns connection status, hostname, and connection time.
    """
    status = agent_manager.get_status(user.sub)
    if status is None:
        return {
            "connected": False,
            "hostname": None,
            "connected_since": None,
        }

    return {
        "connected": True,
        "hostname": status["hostname"],
        "connected_since": status["connect_time"],
    }
