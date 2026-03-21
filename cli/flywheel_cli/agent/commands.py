"""Click CLI commands for the local agent: setup, start, status."""

from __future__ import annotations

import asyncio
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
def agent() -> None:
    """Local agent for browser-based skills."""


@agent.command()
def setup() -> None:
    """Install browser dependencies for the local agent."""
    from flywheel_cli.agent.browser import BrowserSession

    available, kind = asyncio.run(BrowserSession.check_browser_available())

    if available and kind == "chrome":
        console.print("[green]Chrome detected -- no additional setup needed.[/green]")
        return
    if available and kind == "chromium":
        console.print(
            "[green]Playwright Chromium detected -- ready to use.[/green]"
        )
        return

    console.print("[yellow]No browser found. Installing Playwright Chromium...[/yellow]")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]Chromium installed successfully.[/green]")
    else:
        console.print(f"[red]Installation failed:[/red]\n{result.stderr}")
        raise click.ClickException("Failed to install Chromium. Install manually.")


@agent.command()
def start() -> None:
    """Start the local agent (foreground process)."""
    from flywheel_cli.agent.connection import agent_loop, get_ws_url
    from flywheel_cli.auth import get_token, is_logged_in

    if not is_logged_in():
        raise click.ClickException("Not logged in. Run: flywheel login")

    token = get_token()
    ws_url = get_ws_url()

    console.print(
        Panel(
            "Flywheel Local Agent",
            border_style="cyan",
        )
    )
    console.print(f"[dim]Connecting to {ws_url}...[/dim]")

    try:
        asyncio.run(agent_loop(ws_url, token, console))
    except KeyboardInterrupt:
        pass

    console.print("[yellow]Agent stopped.[/yellow]")


@agent.command()
def status() -> None:
    """Check if the local agent is connected."""
    from flywheel_cli.auth import is_logged_in
    from flywheel_cli.main import _api_request

    if not is_logged_in():
        raise click.ClickException("Not logged in. Run: flywheel login")

    resp = _api_request("GET", "/api/v1/agent/status")
    data = resp.json()

    if data.get("connected"):
        host = data.get("hostname", "unknown")
        since = data.get("connected_since", "unknown")
        console.print(
            f"[green]Agent connected from {host} since {since}[/green]"
        )
    else:
        console.print("[yellow]Agent not connected.[/yellow]")
