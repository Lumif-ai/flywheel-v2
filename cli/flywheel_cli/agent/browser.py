"""BrowserSession — Playwright wrapper for local command execution."""

from __future__ import annotations

import base64
import logging

from flywheel_cli.agent.protocol import COMMAND_TYPES, make_error_response, make_response

logger = logging.getLogger(__name__)


class BrowserSession:
    """Async context manager that wraps a Playwright browser for command execution.

    Prefers the user's installed Chrome (``channel="chrome"``) and falls back
    to bundled Playwright Chromium if Chrome is unavailable.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch a browser and open a blank page."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # Try system Chrome first, fall back to bundled Chromium
        try:
            self._browser = await self._playwright.chromium.launch(
                channel="chrome", headless=True
            )
        except Exception:
            logger.debug("System Chrome not found, falling back to Chromium")
            self._browser = await self._playwright.chromium.launch(headless=True)

        self._page = await self._browser.new_page()
        await self._page.set_viewport_size({"width": 1280, "height": 720})

    async def stop(self) -> None:
        """Gracefully close the browser and Playwright."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        self._browser = None
        self._page = None

    async def __aenter__(self) -> "BrowserSession":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def execute(self, command: dict) -> dict:
        """Dispatch a browser command and return a protocol response dict."""
        request_id: str = command["request_id"]
        cmd_type: str = command.get("type", "")

        if cmd_type not in COMMAND_TYPES:
            return make_error_response(
                request_id, f"Unknown command type: {cmd_type}"
            )

        try:
            if cmd_type == "navigate":
                await self._page.goto(
                    command["url"], wait_until="domcontentloaded", timeout=12000
                )
                content = await self._page.content()
                return make_response(request_id, content=content[:50000])

            if cmd_type == "click":
                await self._page.click(command["selector"], timeout=10000)
                return make_response(
                    request_id, content=f"Clicked {command['selector']}"
                )

            if cmd_type == "type":
                await self._page.fill(
                    command["selector"], command["text"], timeout=10000
                )
                return make_response(
                    request_id, content=f"Typed into {command['selector']}"
                )

            if cmd_type == "extract":
                text = await self._page.inner_text(
                    command["selector"], timeout=10000
                )
                return make_response(request_id, content=text)

            if cmd_type == "screenshot":
                screenshot_bytes = await self._page.screenshot(
                    type="jpeg", quality=50
                )
                encoded = base64.b64encode(screenshot_bytes).decode()
                return make_response(request_id, screenshot=encoded)

        except Exception as exc:
            return make_error_response(request_id, str(exc))

        # Unreachable but satisfies type checkers
        return make_error_response(request_id, f"Unhandled command: {cmd_type}")

    # ------------------------------------------------------------------
    # Browser availability check (for `flywheel agent setup`)
    # ------------------------------------------------------------------

    @staticmethod
    async def check_browser_available() -> tuple[bool, str]:
        """Detect whether Chrome or Chromium is available.

        Returns ``(True, "chrome")``, ``(True, "chromium")``, or
        ``(False, "")`` depending on what can be launched.
        """
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=True)
            await browser.close()
            return (True, "chrome")
        except Exception:
            pass

        try:
            browser = await pw.chromium.launch(headless=True)
            await browser.close()
            return (True, "chromium")
        except Exception:
            pass
        finally:
            await pw.stop()

        return (False, "")
