"""Shared Playwright helpers for broker portal automation.

State (user_data_dir, screenshots) lives at a stable per-user path resolved via
Path.home(), never __file__-relative. Phase 149 rewrite for v22.0 — brokers now
log in ONCE and profile persists across runs.

CRITICAL: All portal scripts use headless=False.
The broker logs in manually -- Claude never handles credentials.
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page


async def launch_browser(state_dir: Path, headless: bool = False):
    """Launch a persistent Chromium context rooted at state_dir.

    state_dir MUST be resolved via Path.home() by the caller — NEVER __file__.
    Returns (playwright_context, browser_context). Caller uses context.new_page().
    Browser profile (cookies, localStorage) persists at state_dir across runs.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    p = await async_playwright().__aenter__()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(state_dir),
        headless=headless,
        viewport={"width": 1280, "height": 900},
    )
    return p, ctx


async def wait_for_login(
    page: Page,
    prompt: str = "Please log in manually in the browser window.\nPress Enter here when you are logged in and ready...",
):
    """Pause and wait for broker to log in manually.

    Prints prompt to terminal. Returns when user presses Enter.
    """
    print(f"\n{'='*60}\n{prompt}\n{'='*60}\n")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input)


async def safe_fill(
    page: Page,
    selector: str,
    value: str,
    field_name: str,
    fields_filled: list,
    fields_skipped: list,
):
    """Fill a form field with full error resilience.

    Appends field_name to fields_filled on success, fields_skipped on failure.
    Portal selectors change -- never let one field failure abort the entire fill.
    """
    if not value:
        fields_skipped.append(f"{field_name} (empty value)")
        return
    try:
        await page.fill(selector, str(value))
        fields_filled.append(field_name)
    except Exception as e:
        fields_skipped.append(f"{field_name} ({type(e).__name__})")


async def safe_select(
    page: Page,
    selector: str,
    value: str,
    field_name: str,
    fields_filled: list,
    fields_skipped: list,
):
    """Select an option in a <select> element with error resilience."""
    if not value:
        fields_skipped.append(f"{field_name} (empty value)")
        return
    try:
        await page.select_option(selector, value=str(value))
        fields_filled.append(field_name)
    except Exception as e:
        fields_skipped.append(f"{field_name} ({type(e).__name__})")


async def take_screenshot(page: Page, carrier_name: str, state_dir: Optional[Path] = None) -> str:
    """Take a full-page screenshot.

    If state_dir is provided, writes to state_dir/screenshots/<carrier>_<ts>.png.
    Otherwise falls back to /tmp/portal_screenshot_<carrier>_<ts>.png for backward compat.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if state_dir:
        screenshots = state_dir / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        path = str(screenshots / f"{carrier_name}_{timestamp}.png")
    else:
        path = f"/tmp/portal_screenshot_{carrier_name}_{timestamp}.png"
    await page.screenshot(path=path, full_page=True)
    print(f"\nScreenshot saved: {path}")
    return path


async def wait_for_confirmation(
    message: str = "Review the filled form in the browser.\nPress Enter to confirm or Ctrl+C to abort...",
) -> None:
    """Wait for broker to confirm the filled form looks correct."""
    print(f"\n{message}\n")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input)
