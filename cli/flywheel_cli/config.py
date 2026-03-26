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

# Production defaults — safe to embed (anon key is public, same as frontend bundle)
_DEFAULT_API_URL = "http://localhost:8000"
_DEFAULT_SUPABASE_URL = "https://qudaxjkjzhjqxrmapggi.supabase.co"
_DEFAULT_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF1ZGF4amtqemhqcXhybWFwZ2dpIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzQyMzI2OTUsImV4cCI6MjA4OTgwODY5NX0."
    "O9s-bK56Kb5UyBuoyFNMZf1Pnegk55lnXe_EQxfhHY0"
)

API_URL = os.environ.get("FLYWHEEL_API_URL", _DEFAULT_API_URL)

SUPABASE_URL = os.environ.get("FLYWHEEL_SUPABASE_URL", _DEFAULT_SUPABASE_URL)

SUPABASE_ANON_KEY = os.environ.get("FLYWHEEL_SUPABASE_ANON_KEY", _DEFAULT_SUPABASE_ANON_KEY)

# ---------------------------------------------------------------------------
# PKCE callback
# ---------------------------------------------------------------------------

CALLBACK_PORT = int(os.environ.get("FLYWHEEL_CALLBACK_PORT", "54321"))


def get_api_url() -> str:
    """Return the configured API base URL (no trailing slash)."""
    return API_URL.rstrip("/")
