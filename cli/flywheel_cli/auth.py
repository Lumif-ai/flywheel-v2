"""Token storage, refresh, and credential management."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import click
import httpx

from flywheel_cli.config import CREDENTIALS_FILE, FLYWHEEL_DIR, get_api_url

# ---------------------------------------------------------------------------
# Credential persistence
# ---------------------------------------------------------------------------


def save_credentials(
    access_token: str,
    refresh_token: str,
    expires_at: float,
) -> Path:
    """Write credentials to disk with 600 permissions.

    Returns the path to the credentials file.
    """
    FLYWHEEL_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(CREDENTIALS_FILE, 0o600)
    return CREDENTIALS_FILE


def load_credentials() -> dict | None:
    """Load stored credentials. Returns None if missing or malformed."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_FILE.read_text())
        # Validate required keys
        if not all(k in data for k in ("access_token", "refresh_token", "expires_at")):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def clear_credentials() -> None:
    """Remove stored credentials file."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


def is_logged_in() -> bool:
    """Check whether valid credentials exist (does not verify expiry)."""
    return load_credentials() is not None


# ---------------------------------------------------------------------------
# Token retrieval with auto-refresh
# ---------------------------------------------------------------------------

_EXPIRY_BUFFER_SECONDS = 60


def get_token() -> str:
    """Return a valid access token, auto-refreshing if near expiry.

    Raises click.ClickException if not logged in or refresh fails.
    """
    creds = load_credentials()
    if creds is None:
        raise click.ClickException("Not logged in. Run: flywheel login")

    # Check if token is still valid (with buffer)
    if creds["expires_at"] - time.time() > _EXPIRY_BUFFER_SECONDS:
        return creds["access_token"]

    # Token expired or near expiry — refresh
    api_url = get_api_url()
    try:
        resp = httpx.post(
            f"{api_url}/api/v1/auth/refresh",
            json={"refresh_token": creds["refresh_token"]},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", creds["refresh_token"])
        new_expires = data.get("expires_at", time.time() + 3600)
        save_credentials(new_access, new_refresh, new_expires)
        return new_access
    except httpx.HTTPStatusError as exc:
        clear_credentials()
        raise click.ClickException(
            f"Token refresh failed ({exc.response.status_code}). Run: flywheel login"
        ) from exc
    except httpx.RequestError as exc:
        raise click.ClickException(
            f"Cannot reach API at {api_url}: {exc}"
        ) from exc
