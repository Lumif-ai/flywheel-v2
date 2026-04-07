"""CLI entry point with login, status, focus, and logout commands."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
import socket
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from flywheel_cli.agent.commands import agent
from flywheel_cli.auth import (
    clear_credentials,
    get_token,
    is_logged_in,
    load_credentials,
    save_credentials,
)
from flywheel_cli.config import (
    CALLBACK_PORT,
    FLYWHEEL_DIR,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    get_api_url,
)

console = Console()

ACTIVE_FOCUS_FILE = FLYWHEEL_DIR / "active_focus.json"

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_headers() -> dict[str, str]:
    """Return Authorization headers using the stored token."""
    return {"Authorization": f"Bearer {get_token()}"}


def _api_request(method: str, path: str, **kwargs) -> httpx.Response:
    """Make an authenticated API request with standard error handling.

    Args:
        method: HTTP method (GET, POST, PATCH, etc.)
        path: API path starting with / (e.g., /api/v1/focuses)
        **kwargs: Passed through to httpx.request (json, params, etc.)

    Returns:
        httpx.Response on success.

    Raises:
        click.ClickException on HTTP or connection errors.
    """
    url = f"{get_api_url()}{path}"
    kwargs.setdefault("headers", _api_headers())
    kwargs.setdefault("timeout", 10.0)
    try:
        resp = httpx.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            pass
        msg = f"API error ({exc.response.status_code})"
        if detail:
            msg += f": {detail}"
        raise click.ClickException(msg) from exc
    except httpx.RequestError as exc:
        raise click.ClickException(
            f"Cannot reach API at {get_api_url()}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Active focus local state
# ---------------------------------------------------------------------------


def _load_active_focus() -> dict | None:
    """Load the locally persisted active focus ({id, name}). Returns None if unset."""
    if not ACTIVE_FOCUS_FILE.exists():
        return None
    try:
        data = json.loads(ACTIVE_FOCUS_FILE.read_text())
        if "id" in data and "name" in data:
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def _save_active_focus(focus_id: str, focus_name: str) -> None:
    """Persist the active focus locally."""
    FLYWHEEL_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FOCUS_FILE.write_text(json.dumps({"id": focus_id, "name": focus_name}, indent=2))


def _clear_active_focus() -> None:
    """Remove the local active focus file."""
    if ACTIVE_FOCUS_FILE.exists():
        ACTIVE_FOCUS_FILE.unlink()


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="flywheel-cli")
def cli() -> None:
    """Flywheel CLI -- context management from the terminal."""


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth PKCE callback on localhost."""

    auth_code: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        qs = parse_qs(urlparse(self.path).query)
        codes = qs.get("code", [])
        if codes:
            _CallbackHandler.auth_code = codes[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Login successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Missing auth code.</h2></body></html>")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default HTTP server logging."""


def _exchange_pkce_code(code: str, verifier: str) -> dict:
    """Exchange authorization code for tokens via Supabase PKCE endpoint."""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
        json={"auth_code": code, "code_verifier": verifier},
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def _login_headless(email: str, password: str) -> dict:
    """Authenticate with email + password (headless mode)."""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_profile(access_token: str) -> dict:
    """Fetch user profile from the Flywheel API."""
    api_url = get_api_url()
    resp = httpx.get(
        f"{api_url}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def _save_from_token_response(data: dict) -> str:
    """Extract tokens from Supabase response and persist them.

    Returns the access_token.
    """
    import time

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    expires_in = data.get("expires_in", 3600)
    expires_at = time.time() + expires_in
    save_credentials(access_token, refresh_token, expires_at)
    return access_token


@cli.command()
@click.option("--headless", is_flag=True, help="Use email/password instead of browser.")
def login(headless: bool) -> None:
    """Authenticate with Flywheel (browser PKCE or headless)."""
    if not SUPABASE_URL:
        raise click.ClickException(
            "FLYWHEEL_SUPABASE_URL not set. "
            "Export it before running login."
        )
    if not SUPABASE_ANON_KEY:
        raise click.ClickException(
            "FLYWHEEL_SUPABASE_ANON_KEY not set. "
            "Export it before running login."
        )

    if headless:
        email = click.prompt("Email")
        password = click.prompt("Password", hide_input=True)
        with console.status("Authenticating..."):
            try:
                data = _login_headless(email, password)
            except httpx.HTTPStatusError as exc:
                raise click.ClickException(
                    f"Login failed ({exc.response.status_code}). "
                    "Check your credentials."
                ) from exc
        console.print(
            "[dim]Note: password auth must be enabled in Supabase dashboard.[/dim]"
        )
    else:
        # PKCE browser flow
        verifier, challenge = _generate_pkce()
        redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"
        auth_url = (
            f"{SUPABASE_URL}/auth/v1/authorize"
            f"?provider=google"
            f"&code_challenge={challenge}"
            f"&code_challenge_method=S256"
            f"&redirect_to={redirect_uri}"
        )

        # Start local callback server
        _CallbackHandler.auth_code = None
        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
        server.timeout = 60

        console.print(
            Panel(
                "Opening browser for login...\nWaiting for authentication.",
                title="Flywheel Login",
                border_style="cyan",
            )
        )
        webbrowser.open(auth_url)

        # Wait for callback (blocks up to 60s)
        server.handle_request()
        server.server_close()

        code = _CallbackHandler.auth_code
        if not code:
            raise click.ClickException(
                "Authentication timed out or failed. No auth code received."
            )

        with console.status("Exchanging tokens..."):
            try:
                data = _exchange_pkce_code(code, verifier)
            except httpx.HTTPStatusError as exc:
                raise click.ClickException(
                    f"Token exchange failed ({exc.response.status_code})."
                ) from exc

    # Save tokens
    access_token = _save_from_token_response(data)

    # Fetch profile
    try:
        profile = _fetch_profile(access_token)
        email_display = profile.get("email", "unknown")
        tenant = profile.get("active_tenant")
        tenant_name = tenant.get("name", "none") if tenant else "none"
        console.print(
            f"[green]Logged in as {email_display} (tenant: {tenant_name})[/green]"
        )
    except Exception:
        console.print("[green]Logged in successfully.[/green]")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@cli.command()
def status() -> None:
    """Show login state and tenant info."""
    if not is_logged_in():
        console.print("[yellow]Not logged in. Run: flywheel login[/yellow]")
        return

    try:
        token = get_token()
    except click.ClickException:
        console.print("[yellow]Not logged in. Run: flywheel login[/yellow]")
        return

    api_url = get_api_url()
    try:
        resp = httpx.get(
            f"{api_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if resp.status_code == 401:
            clear_credentials()
            console.print("[yellow]Session expired. Run: flywheel login[/yellow]")
            return
        resp.raise_for_status()
        profile = resp.json()
    except httpx.RequestError as exc:
        raise click.ClickException(f"Cannot reach API at {api_url}: {exc}") from exc

    import datetime

    creds = load_credentials()
    expires_at = creds["expires_at"] if creds else 0
    expiry_str = datetime.datetime.fromtimestamp(expires_at).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    email = profile.get("email", "unknown")
    tenant = profile.get("active_tenant")
    tenant_name = tenant.get("name", "none") if tenant else "none"
    role = tenant.get("role", "unknown") if tenant else "n/a"

    # Active focus info
    active_focus = _load_active_focus()
    focus_line = (
        f"[bold]Focus:[/bold]  {active_focus['name']}"
        if active_focus
        else "[bold]Focus:[/bold]  global (no focus)"
    )

    console.print(
        Panel(
            f"[bold]Email:[/bold]  {email}\n"
            f"[bold]Tenant:[/bold] {tenant_name}\n"
            f"[bold]Role:[/bold]   {role}\n"
            f"[bold]Expiry:[/bold] {expiry_str}\n"
            f"{focus_line}",
            title="Flywheel Status",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# Focus management
# ---------------------------------------------------------------------------


@cli.group()
def focus() -> None:
    """Manage focuses (departments, teams, projects)."""


@focus.command("list")
def focus_list() -> None:
    """List all focuses for the current tenant."""
    resp = _api_request("GET", "/api/v1/focuses")
    items = resp.json().get("items", [])

    if not items:
        console.print(
            "[yellow]No focuses yet. Create one: flywheel focus create <name>[/yellow]"
        )
        return

    active = _load_active_focus()
    active_id = active["id"] if active else None

    table = Table(title="Focuses")
    table.add_column("", width=2)  # active marker
    table.add_column("Name", style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Members", justify="right")
    table.add_column("Created", style="dim")

    for item in items:
        marker = "*" if item["id"] == active_id else ""
        created = item.get("created_at", "")
        if created and len(created) >= 10:
            created = created[:10]  # date only
        table.add_row(
            marker,
            item["name"],
            item["id"][:8],
            str(item.get("member_count", 0)),
            created,
        )

    console.print(table)
    if active:
        console.print(f"\n[dim]* = active focus ({active['name']})[/dim]")


@focus.command("create")
@click.argument("name")
@click.option("--description", "-d", default=None, help="Focus description.")
def focus_create(name: str, description: str | None) -> None:
    """Create a new focus."""
    body: dict = {"name": name}
    if description:
        body["description"] = description

    resp = _api_request("POST", "/api/v1/focuses", json=body)
    data = resp.json().get("focus", {})
    focus_id = data.get("id", "unknown")
    focus_name = data.get("name", name)

    console.print(f"[green]Created focus: {focus_name} ({focus_id[:8]})[/green]")

    if click.confirm("Switch to this focus now?", default=True):
        _api_request("POST", f"/api/v1/focuses/{focus_id}/switch")
        _save_active_focus(focus_id, focus_name)
        console.print(f"[green]Switched to focus: {focus_name}[/green]")


@focus.command("switch")
@click.argument("name_or_id")
def focus_switch(name_or_id: str) -> None:
    """Switch active focus by name (partial match) or ID prefix."""
    # Fetch all focuses to find a match
    resp = _api_request("GET", "/api/v1/focuses")
    items = resp.json().get("items", [])

    if not items:
        raise click.ClickException(
            "No focuses found. Create one first: flywheel focus create <name>"
        )

    # Match by ID prefix or case-insensitive name substring
    query = name_or_id.lower()
    matches = [
        item
        for item in items
        if item["id"].lower().startswith(query)
        or query in item["name"].lower()
    ]

    if len(matches) == 0:
        raise click.ClickException(
            f"No focus matching '{name_or_id}'. "
            "Run 'flywheel focus list' to see available focuses."
        )
    if len(matches) > 1:
        console.print(f"[yellow]Multiple focuses match '{name_or_id}':[/yellow]")
        for m in matches:
            console.print(f"  - {m['name']} ({m['id'][:8]})")
        raise click.ClickException("Be more specific or use the full ID.")

    target = matches[0]
    _api_request("POST", f"/api/v1/focuses/{target['id']}/switch")
    _save_active_focus(target["id"], target["name"])
    console.print(f"[green]Switched to focus: {target['name']}[/green]")


@focus.command("current")
def focus_current() -> None:
    """Show the current active focus."""
    active = _load_active_focus()
    if active:
        console.print(
            f"[bold]Active focus:[/bold] {active['name']} ({active['id'][:8]})"
        )
    else:
        console.print("[dim]No active focus (global view)[/dim]")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@cli.command()
def logout() -> None:
    """Remove stored credentials."""
    clear_credentials()
    console.print("[green]Logged out successfully.[/green]")


# ---------------------------------------------------------------------------
# Setup Claude Code (MCP server registration)
# ---------------------------------------------------------------------------


_FLYWHEEL_CLAUDE_MD_MARKER = "# Flywheel Integration"


def _install_claude_md_template() -> bool:
    """Install the Flywheel CLAUDE.md template into ~/.claude/CLAUDE.md.

    If ~/.claude/CLAUDE.md doesn't exist, creates it with the template.
    If it exists but doesn't contain the Flywheel section, appends it.
    Returns True if changes were made.
    """
    from importlib.resources import files as pkg_files
    from pathlib import Path

    claude_dir = Path.home() / ".claude"
    claude_md = claude_dir / "CLAUDE.md"
    template = pkg_files("flywheel_mcp").joinpath("templates/CLAUDE.md").read_text()

    claude_dir.mkdir(parents=True, exist_ok=True)

    if not claude_md.exists():
        claude_md.write_text(template)
        return True

    existing = claude_md.read_text()
    if _FLYWHEEL_CLAUDE_MD_MARKER in existing:
        return False  # already installed

    # Prepend so Flywheel rules take priority over other instructions
    claude_md.write_text(template.rstrip() + "\n\n" + existing)
    return True


@cli.command("setup-claude-code")
def setup_claude_code() -> None:
    """Register Flywheel and Granola MCP servers with Claude Code."""
    # 1. Check flywheel-mcp is on PATH
    mcp_path = shutil.which("flywheel-mcp")
    if not mcp_path:
        console.print(
            "[red]flywheel-mcp not found on PATH. "
            "Install with: uv tool install flywheel-ai[/red]"
        )
        raise SystemExit(1)

    # 2. Check claude CLI is on PATH
    claude_path = shutil.which("claude")
    if not claude_path:
        console.print(
            "[red]Claude Code CLI not found. "
            "Install Claude Code first: https://claude.ai/download[/red]"
        )
        raise SystemExit(1)

    # 3. Register Flywheel MCP server (stdio)
    console.print("[bold]Registering Flywheel MCP server...[/bold]")
    flywheel_result = subprocess.run(
        [
            "claude", "mcp", "add",
            "--transport", "stdio",
            "--scope", "user",
            "flywheel", "--", mcp_path,
        ],
        capture_output=True,
        text=True,
    )
    if flywheel_result.returncode == 0:
        console.print("[green]  Flywheel MCP registered[/green]")
    else:
        console.print(
            f"[red]  Flywheel MCP failed:[/red] {flywheel_result.stderr.strip()}\n"
            f"  [yellow]Try manually:[/yellow] claude mcp add --transport stdio "
            f"--scope user flywheel -- {mcp_path}"
        )

    # 4. Register Granola MCP server (HTTP)
    granola_url = "https://mcp.granola.ai/mcp"
    console.print("[bold]Registering Granola MCP server...[/bold]")
    granola_result = subprocess.run(
        [
            "claude", "mcp", "add",
            "--transport", "http",
            "--scope", "user",
            "granola", "--url", granola_url,
        ],
        capture_output=True,
        text=True,
    )
    if granola_result.returncode == 0:
        console.print("[green]  Granola MCP registered[/green]")
    else:
        console.print(
            f"[red]  Granola MCP failed:[/red] {granola_result.stderr.strip()}\n"
            f"  [yellow]Try manually:[/yellow] claude mcp add --transport http "
            f"--scope user granola --url {granola_url}"
        )

    # 5. Auto-allow Flywheel MCP tool permissions (non-destructive only)
    console.print("[bold]Configuring MCP tool permissions...[/bold]")
    _AUTO_ALLOW_TOOLS = [
        "mcp__flywheel__flywheel_read_context",
        "mcp__flywheel__flywheel_write_context",
        "mcp__flywheel__flywheel_fetch_skills",
        "mcp__flywheel__flywheel_fetch_skill_prompt",
        "mcp__flywheel__flywheel_run_skill",
        "mcp__flywheel__flywheel_fetch_meetings",
        "mcp__flywheel__flywheel_fetch_upcoming",
        "mcp__flywheel__flywheel_fetch_tasks",
        "mcp__flywheel__flywheel_sync_meetings",
        "mcp__flywheel__flywheel_save_document",
        "mcp__flywheel__flywheel_save_meeting_summary",
        "mcp__flywheel__flywheel_update_task",
        "mcp__flywheel__flywheel_fetch_account",
        "mcp__flywheel__flywheel_list_leads",
        "mcp__flywheel__flywheel_upsert_lead",
        "mcp__flywheel__flywheel_add_lead_contact",
        "mcp__flywheel__flywheel_draft_lead_message",
        "mcp__flywheel__flywheel_upsert_pipeline_entry",
        "mcp__flywheel__flywheel_list_pipeline",
        "mcp__flywheel__flywheel_fetch_pipeline_entry",
        "mcp__flywheel__flywheel_add_pipeline_contact",
        "mcp__flywheel__flywheel_draft_pipeline_message",
        "mcp__flywheel__flywheel_list_pipeline_contacts",
        "mcp__flywheel__flywheel_create_outreach_step",
        "mcp__flywheel__flywheel_list_outreach_steps",
        "mcp__flywheel__flywheel_update_outreach_step",
        "mcp__granola__get_meetings",
    ]
    # Destructive tools NOT auto-allowed (require user confirmation):
    #   flywheel_send_lead_message, flywheel_send_pipeline_message,
    #   flywheel_graduate_lead
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}

        allow_list = settings.setdefault("permissions", {}).setdefault("allow", [])
        added = 0
        for tool in _AUTO_ALLOW_TOOLS:
            if tool not in allow_list:
                allow_list.append(tool)
                added += 1

        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        if added:
            console.print(f"[green]  Auto-allowed {added} Flywheel MCP tools[/green]")
            console.print("[dim]  Destructive actions (send message, graduate) still require approval[/dim]")
        else:
            console.print("[dim]  All Flywheel MCP tools already allowed[/dim]")
    except Exception as exc:
        console.print(f"[red]  Failed to configure permissions:[/red] {exc}")

    # 6. Install CLAUDE.md template (Flywheel-first routing rules)
    console.print("[bold]Installing CLAUDE.md template...[/bold]")
    claude_md_ok = False
    try:
        if _install_claude_md_template():
            console.print("[green]  Flywheel rules added to ~/.claude/CLAUDE.md[/green]")
        else:
            console.print("[dim]  Flywheel rules already present in ~/.claude/CLAUDE.md[/dim]")
        claude_md_ok = True
    except Exception as exc:
        console.print(f"[red]  Failed to install CLAUDE.md template:[/red] {exc}")
        console.print(
            "[yellow]  ⚠ Claude Code won't know how to route to Flywheel without this.[/yellow]\n"
            "[yellow]  Run 'flywheel setup-claude-code' again or manually copy the template.[/yellow]"
        )

    # 7. Summary
    if claude_md_ok:
        claude_md_status = (
            "  [bold]CLAUDE.md[/bold] (routing rules)\n"
            "    - Always check Flywheel context store before answering\n"
            "    - Save business intelligence to Flywheel automatically\n"
            "    - Route to Flywheel skills before general Claude\n\n"
        )
        panel_title = "Setup Complete"
        panel_border = "green"
    else:
        claude_md_status = (
            "  [bold red]CLAUDE.md[/bold red] (FAILED — routing rules not installed)\n"
            "    - Run 'flywheel setup-claude-code' again to retry\n\n"
        )
        panel_title = "Setup Incomplete"
        panel_border = "yellow"

    console.print(
        Panel(
            "[bold]MCP servers configured for Claude Code:[/bold]\n\n"
            "  [bold]flywheel[/bold] (stdio)\n"
            "    - flywheel_run_skill: Run meeting-prep, company-intel, etc.\n"
            "    - flywheel_read_context: Search your business knowledge\n"
            "    - flywheel_write_context: Store business intelligence\n\n"
            "  [bold]granola[/bold] (HTTP)\n"
            "    - get_meetings: Access meeting transcripts from Granola\n\n"
            + claude_md_status +
            "[dim]Optional: Enable Apollo MCP plugin in Claude Code settings "
            "for lead enrichment tools.[/dim]\n\n"
            "[dim]Restart Claude Code to activate.[/dim]",
            title=panel_title,
            border_style=panel_border,
        )
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


@cli.command()
def upgrade() -> None:
    """Upgrade Flywheel CLI to the latest version."""
    console.print("[bold]Upgrading flywheel-ai...[/bold]")
    result = subprocess.run(
        ["uv", "tool", "upgrade", "flywheel-ai"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print(f"[green]{result.stdout.strip() or 'flywheel-ai upgraded'}[/green]")
        console.print("[dim]Restart Claude Code to pick up changes.[/dim]")
    else:
        # Fallback to pip if uv not available
        result2 = subprocess.run(
            ["pip", "install", "--upgrade", "flywheel-ai"],
            capture_output=True,
            text=True,
        )
        if result2.returncode == 0:
            console.print("[green]flywheel-ai upgraded via pip[/green]")
        else:
            console.print(f"[red]Upgrade failed:[/red]\n{result.stderr or result2.stderr}")
            console.print(
                "\n[yellow]Try manually:[/yellow]\n"
                "  uv tool upgrade flywheel-ai\n"
                "  # or: pip install --upgrade flywheel-ai"
            )


# ---------------------------------------------------------------------------
# Agent (local browser agent)
# ---------------------------------------------------------------------------

cli.add_command(agent)
