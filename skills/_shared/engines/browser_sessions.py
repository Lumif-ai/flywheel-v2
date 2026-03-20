"""
browser_sessions.py - Browser session management for Flywheel integrations.

Manages per-user, per-service browser login sessions using Playwright's
storage_state. Users log in via headed mode (/fly login {service}); research
tasks run headless with saved sessions.

Public API:
    login_session(user_id, service) -> bool
    get_session_state(user_id, service) -> Optional[Path]
    is_session_valid(user_id, service) -> bool
    delete_session(user_id, service) -> None
    check_session_alive(user_id, service) -> bool
    SERVICE_URLS - Login page URLs per service
    SESSION_EXPIRY_DAYS - Conservative expiry thresholds per service
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try importing playwright -- not required at import time
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.info("Playwright not installed. Browser session features unavailable.")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILES_DIR = Path.home() / ".flywheel" / "browser-profiles"

SERVICE_URLS = {
    "linkedin": "https://linkedin.com/login",
    "google": "https://accounts.google.com",
    "github": "https://github.com/login",
}

# Conservative expiry estimates (days) -- sessions may last longer,
# but we re-check proactively before relying on them.
SESSION_EXPIRY_DAYS = {
    "linkedin": 3,
    "google": 14,
    "github": 30,
}

# Login detection: URLs that indicate the user is still on a login page.
_LOGIN_URL_PATTERNS = {
    "linkedin": ["linkedin.com/login", "linkedin.com/checkpoint"],
    "google": ["accounts.google.com/v3/signin", "accounts.google.com/signin", "accounts.google.com/o/oauth2"],
    "github": ["github.com/login", "github.com/session"],
}

# Probe URLs for session-alive checks (lightweight page that requires auth).
_PROBE_URLS = {
    "linkedin": "https://www.linkedin.com/feed/",
    "google": "https://myaccount.google.com/",
    "github": "https://github.com/settings/profile",
}


# ---------------------------------------------------------------------------
# Session state management
# ---------------------------------------------------------------------------


def _session_dir(user_id: str, service: str) -> Path:
    """Get directory for a user's service session."""
    return PROFILES_DIR / user_id / service


def _session_file(user_id: str, service: str) -> Path:
    """Get path to storage_state.json for a user+service."""
    return _session_dir(user_id, service) / "storage_state.json"


def get_session_state(user_id: str, service: str) -> Optional[Path]:
    """Return path to storage_state.json if it exists, None otherwise.

    Args:
        user_id: User identifier.
        service: Service name (e.g., 'linkedin', 'google').

    Returns:
        Path to storage_state.json if exists, None otherwise.
    """
    path = _session_file(user_id, service)
    if path.exists():
        return path
    return None


def is_session_valid(user_id: str, service: str) -> bool:
    """Check if a saved session exists and is not expired.

    Expiry is based on file modification time vs SESSION_EXPIRY_DAYS.

    Args:
        user_id: User identifier.
        service: Service name.

    Returns:
        True if session file exists and is within expiry window.
    """
    path = _session_file(user_id, service)
    if not path.exists():
        return False

    expiry_days = SESSION_EXPIRY_DAYS.get(service, 7)  # default 7 days
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400

    return age_days < expiry_days


def delete_session(user_id: str, service: str) -> None:
    """Delete a saved session.

    Args:
        user_id: User identifier.
        service: Service name.
    """
    path = _session_file(user_id, service)
    if path.exists():
        path.unlink()
        logger.info("Deleted session for user=%s service=%s", user_id, service)


# ---------------------------------------------------------------------------
# Login flow (headed mode)
# ---------------------------------------------------------------------------


async def login_session(user_id: str, service: str) -> bool:
    """Launch headed browser for user to log in, then save session.

    Opens Playwright chromium in headed mode (headless=False), navigates
    to the service login URL, and waits for the user to complete login.
    After login detected (URL changes away from login page), saves
    context.storage_state() to the user's profile directory.

    Called from Slack /fly login {service} command handler.

    Args:
        user_id: User identifier.
        service: Service name (must be in SERVICE_URLS).

    Returns:
        True if login succeeded and session was saved, False otherwise.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not installed. Cannot launch login session.")
        return False

    if service not in SERVICE_URLS:
        logger.error("Unknown service: %s. Known: %s", service, list(SERVICE_URLS.keys()))
        return False

    login_url = SERVICE_URLS[service]
    login_patterns = _LOGIN_URL_PATTERNS.get(service, [])

    session_dir = _session_dir(user_id, service)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = _session_file(user_id, service)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(login_url, wait_until="domcontentloaded")

            # Poll for login completion: URL should leave the login page
            max_wait_seconds = 120
            poll_interval = 2
            elapsed = 0

            while elapsed < max_wait_seconds:
                await page.wait_for_timeout(poll_interval * 1000)
                elapsed += poll_interval

                current_url = page.url.lower()
                still_on_login = any(pat in current_url for pat in login_patterns)

                if not still_on_login:
                    # User has logged in -- save session
                    state = await context.storage_state()
                    fd = os.open(str(session_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2)
                    logger.info(
                        "Session saved for user=%s service=%s at %s",
                        user_id, service, session_path,
                    )
                    return True

            # Timed out waiting for login
            logger.warning(
                "Login timed out for user=%s service=%s after %ds",
                user_id, service, max_wait_seconds,
            )
            return False

        except Exception as e:
            logger.error("Login session error for %s/%s: %s", user_id, service, e)
            return False
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Expiry probe (headless)
# ---------------------------------------------------------------------------


async def check_session_alive(user_id: str, service: str) -> bool:
    """Probe whether a saved session is still authenticated.

    Launches a headless browser with saved storage_state, navigates to a
    lightweight authenticated page, and checks if it gets redirected to
    a login page.

    Args:
        user_id: User identifier.
        service: Service name.

    Returns:
        True if session is alive (not redirected to login), False if
        expired or no session exists.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not installed. Cannot check session.")
        return False

    session_path = get_session_state(user_id, service)
    if session_path is None:
        return False

    probe_url = _PROBE_URLS.get(service)
    if probe_url is None:
        # No probe URL defined -- fall back to time-based check
        return is_session_valid(user_id, service)

    login_patterns = _LOGIN_URL_PATTERNS.get(service, [])

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(storage_state=str(session_path))
            page = await context.new_page()

            await page.goto(probe_url, wait_until="domcontentloaded", timeout=15000)

            # Check if we got redirected to a login page
            current_url = page.url.lower()
            redirected_to_login = any(pat in current_url for pat in login_patterns)

            if redirected_to_login:
                logger.info(
                    "Session expired for user=%s service=%s (redirected to login)",
                    user_id, service,
                )
                return False

            return True

        except Exception as e:
            logger.warning("Session probe failed for %s/%s: %s", user_id, service, e)
            return False
        finally:
            await browser.close()
