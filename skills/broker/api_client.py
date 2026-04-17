#!/usr/bin/env python3
"""Shared HTTP client for broker skills. All API calls go through here.

Auth strategy (in priority order):
1. FLYWHEEL_API_TOKEN env var (explicit override)
2. ~/.flywheel/credentials.json (from `flywheel login` — auto-refreshes)

API URL strategy:
1. FLYWHEEL_API_URL env var (explicit override)
2. Flywheel CLI config default (https://uat-flywheel-backend.lumif.ai)

Functions: post(), get(), patch(), upload_file(), run()
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Auto-discover API URL
# ---------------------------------------------------------------------------
_DEFAULT_API_URL = "https://uat-flywheel-backend.lumif.ai"
_LOCAL_API_URL = "http://localhost:8000"
_BASE = os.environ.get("FLYWHEEL_API_URL", "").strip()

if not _BASE:
    # Prefer local dev server if it's running (fast socket check, no HTTP overhead)
    import socket as _sock
    try:
        _s = _sock.create_connection(("127.0.0.1", 8000), timeout=0.3)
        _s.close()
        _BASE = _LOCAL_API_URL
    except (OSError, _sock.timeout):
        pass

if not _BASE:
    # Fall back to CLI config or production default
    try:
        from flywheel_cli.config import get_api_url
        _BASE = get_api_url()
    except ImportError:
        _BASE = _DEFAULT_API_URL

_BASE = _BASE.rstrip("/")
API_URL = f"{_BASE}/api/v1"

# ---------------------------------------------------------------------------
# Auto-discover token
# ---------------------------------------------------------------------------
_CREDENTIALS_FILE = Path.home() / ".flywheel" / "credentials.json"
_EXPIRY_BUFFER = 60


def _load_token_from_credentials() -> str:
    """Load access token from ~/.flywheel/credentials.json, refresh if expired."""
    if not _CREDENTIALS_FILE.exists():
        return ""

    try:
        data = json.loads(_CREDENTIALS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    expires_at = data.get("expires_at", 0)

    if not access_token:
        return ""

    # Check if still valid
    if expires_at - time.time() > _EXPIRY_BUFFER:
        return access_token

    # Try to refresh
    if not refresh_token:
        return access_token  # Return stale token, let server reject

    try:
        resp = httpx.post(
            f"{_BASE}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10.0,
        )
        resp.raise_for_status()
        new_data = resp.json()
        new_access = new_data["access_token"]
        new_refresh = new_data.get("refresh_token", refresh_token)
        new_expires = new_data.get("expires_at", time.time() + 3600)

        # Save refreshed credentials
        creds = {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_at": new_expires,
        }
        _CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
        os.chmod(_CREDENTIALS_FILE, 0o600)
        return new_access
    except Exception:
        return access_token  # Return stale token on refresh failure


def _get_token() -> str:
    """Get token: env var first, then credentials file."""
    env_token = os.environ.get("FLYWHEEL_API_TOKEN", "").strip()
    if env_token:
        return env_token
    return _load_token_from_credentials()


def _headers() -> dict:
    token = _get_token()
    if not token:
        raise RuntimeError(
            "No Flywheel auth token found.\n"
            "Either run `flywheel login` or set FLYWHEEL_API_TOKEN env var."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def post(path: str, payload: Optional[dict] = None) -> dict:
    """POST to broker API with Bearer auth. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload or {},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get(path: str, params: Optional[dict] = None) -> dict:
    """GET from broker API with Bearer auth. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/broker/{path.lstrip('/')}",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def patch(path: str, payload: Optional[dict] = None) -> dict:
    """PATCH broker API endpoint with Bearer auth. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload or {},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def upload_file(project_id: str, pdf_path: str) -> dict:
    """Upload a PDF file to a broker project. Returns {"files": [...]}."""
    token = _get_token()
    if not token:
        raise RuntimeError(
            "No Flywheel auth token found.\n"
            "Either run `flywheel login` or set FLYWHEEL_API_TOKEN env var."
        )
    url = f"{API_URL}/broker/projects/{project_id}/documents"
    with open(pdf_path, "rb") as fh:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                files={"files": (os.path.basename(pdf_path), fh, "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()


def run(coro):
    """Sync wrapper — call asyncio.run(coro). Use from non-async contexts (hooks, scripts)."""
    return asyncio.run(coro)
