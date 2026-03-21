"""WebSocket client with auto-reconnect and token refresh for the local agent."""

from __future__ import annotations

import asyncio
import json
import logging
import signal

from flywheel_cli.auth import get_token
from flywheel_cli.config import get_api_url

logger = logging.getLogger(__name__)


def get_ws_url() -> str:
    """Derive the WebSocket URL from the configured API URL."""
    api = get_api_url()
    ws = api.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws}/api/v1/ws/agent"


def get_fresh_token() -> str:
    """Fetch a fresh access token (delegates to auth module)."""
    return get_token()


async def agent_loop(ws_url: str, token: str, console) -> None:
    """Connect to the backend via WebSocket and execute browser commands.

    Automatically reconnects on disconnection. Refreshes the JWT when the
    server closes with code 4001 (token expired).

    Args:
        ws_url: WebSocket endpoint (e.g. ``wss://api.example.com/api/v1/ws/agent``).
        token: Initial JWT access token.
        console: Rich Console instance for terminal output.
    """
    import websockets
    from flywheel_cli.agent.browser import BrowserSession

    current_token = token
    browser = BrowserSession()

    # Graceful shutdown via signals
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _request_shutdown() -> None:
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await browser.start()
        console.print("[dim]Browser ready.[/dim]")

        while not shutdown_event.is_set():
            try:
                async with websockets.connect(
                    f"{ws_url}?token={current_token}",
                    ping_interval=30,
                    ping_timeout=20,
                    close_timeout=5,
                ) as ws:
                    console.print("[green]Connected to Flywheel backend[/green]")
                    console.print(
                        "[dim]Waiting for browser commands... (Ctrl+C to stop)[/dim]"
                    )

                    async for message in ws:
                        if shutdown_event.is_set():
                            break
                        try:
                            command = json.loads(message)
                            result = await browser.execute(command)
                            await ws.send(json.dumps(result))
                        except json.JSONDecodeError:
                            logger.warning("Received non-JSON message, ignoring")
                        except Exception as exc:
                            logger.error("Error executing command: %s", exc)

            except websockets.ConnectionClosed as exc:
                if shutdown_event.is_set():
                    break
                if exc.code == 4001:
                    console.print("[yellow]Token expired, refreshing...[/yellow]")
                    try:
                        current_token = get_fresh_token()
                    except Exception:
                        console.print(
                            "[red]Token refresh failed. Run: flywheel login[/red]"
                        )
                        break
                else:
                    console.print("[yellow]Disconnected, reconnecting...[/yellow]")
                await asyncio.sleep(2)

            except (OSError, websockets.WebSocketException) as exc:
                if shutdown_event.is_set():
                    break
                console.print(
                    f"[yellow]Connection error: {exc}. Retrying in 5s...[/yellow]"
                )
                await asyncio.sleep(5)

    except asyncio.CancelledError:
        pass
    finally:
        await browser.stop()
        console.print("[dim]Browser closed.[/dim]")
