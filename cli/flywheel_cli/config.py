"""Configuration constants for the Flywheel CLI."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Flywheel directory (stores credentials, cache, etc.)
# ---------------------------------------------------------------------------

FLYWHEEL_DIR = Path(os.environ.get("FLYWHEEL_DIR", Path.home() / ".flywheel"))

CREDENTIALS_FILE = FLYWHEEL_DIR / "credentials.json"

# ---------------------------------------------------------------------------
# API and Supabase URLs
# ---------------------------------------------------------------------------

API_URL = os.environ.get("FLYWHEEL_API_URL", "http://localhost:8000")

SUPABASE_URL = os.environ.get("FLYWHEEL_SUPABASE_URL", "")

SUPABASE_ANON_KEY = os.environ.get("FLYWHEEL_SUPABASE_ANON_KEY", "")

# ---------------------------------------------------------------------------
# PKCE callback
# ---------------------------------------------------------------------------

CALLBACK_PORT = int(os.environ.get("FLYWHEEL_CALLBACK_PORT", "54321"))


def get_api_url() -> str:
    """Return the configured API base URL (no trailing slash)."""
    return API_URL.rstrip("/")
