"""CLI entry point with login, status, and logout commands."""

from __future__ import annotations

import base64
import hashlib
import secrets
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import click
import httpx
from rich.console import Console
from rich.panel import Panel

from flywheel_cli.auth import (
    clear_credentials,
    get_token,
    is_logged_in,
    load_credentials,
    save_credentials,
)
from flywheel_cli.config import (
    CALLBACK_PORT,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    get_api_url,
)

console = Console()

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
            f"?provider=email"
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

    console.print(
        Panel(
            f"[bold]Email:[/bold]  {email}\n"
            f"[bold]Tenant:[/bold] {tenant_name}\n"
            f"[bold]Role:[/bold]   {role}\n"
            f"[bold]Expiry:[/bold] {expiry_str}",
            title="Flywheel Status",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@cli.command()
def logout() -> None:
    """Remove stored credentials."""
    clear_credentials()
    console.print("[green]Logged out successfully.[/green]")
