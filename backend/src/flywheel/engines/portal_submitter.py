"""Portal submission engine -- runs LOCALLY on broker's machine.

This module orchestrates Playwright to fill carrier portal forms.
It is NOT imported by the API server. It runs in the broker's
Claude Code instance or as a standalone script.

Usage:
    python -m flywheel.engines.portal_submitter --project-id <uuid> --carrier-config-id <uuid>
"""

import asyncio
import importlib
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

try:
    from playwright.async_api import async_playwright, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

PORTALS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "portals"


def _normalize_carrier_name(carrier_name: str) -> str:
    """Normalize carrier name to a valid Python module filename (without .py)."""
    return carrier_name.lower().replace(" ", "_").replace("-", "_")


def _load_carrier_script(carrier_name: str):
    """Dynamically load a carrier-specific portal script from scripts/portals/.

    Returns the loaded module or raises FileNotFoundError.
    """
    normalized = _normalize_carrier_name(carrier_name)
    script_path = PORTALS_DIR / f"{normalized}.py"

    if not script_path.exists():
        available = [f.stem for f in PORTALS_DIR.glob("*.py") if f.stem != "__init__"]
        raise FileNotFoundError(
            f"No portal script found for carrier '{carrier_name}' "
            f"(looked for {script_path}). "
            f"Available scripts: {available}"
        )

    spec = importlib.util.spec_from_file_location(normalized, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "fill_portal"):
        raise AttributeError(
            f"Portal script '{script_path}' must export an async function 'fill_portal'. "
            f"Found attributes: {dir(module)}"
        )

    return module


async def submit_to_portal(
    project_data: dict,
    carrier_config: dict,
    coverages: list[dict],
    documents: list[dict],
    api_base_url: str = "http://localhost:8000",
    auth_token: str | None = None,
) -> dict:
    """Orchestrate portal submission via Playwright.

    Args:
        project_data: Project dict (name, project_type, contract_value, currency, language)
        carrier_config: Carrier dict (carrier_name, portal_url)
        coverages: List of coverage dicts
        documents: List of document dicts
        api_base_url: Backend API URL for uploading screenshots
        auth_token: Bearer token for API calls

    Returns:
        {"screenshot_path": str, "fields_filled": list[str], "status": "ready_for_review"}
    """
    if not HAS_PLAYWRIGHT:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    carrier_name = carrier_config["carrier_name"]
    portal_url = carrier_config["portal_url"]

    # Load the carrier-specific script
    script_module = _load_carrier_script(carrier_name)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(portal_url)

        # Broker must log in manually -- this runs on their machine with visible browser
        print(
            "\n========================================\n"
            "Browser opened. Please log in to the carrier portal manually.\n"
            "Press Enter when ready to proceed with form filling...\n"
            "========================================"
        )
        await asyncio.get_event_loop().run_in_executor(None, input)

        # Call carrier-specific form filling
        result = await script_module.fill_portal(page, project_data, coverages, documents)

        # Take full-page screenshot for review gate
        screenshot_bytes = await page.screenshot(full_page=True)

        # Save screenshot locally
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        normalized_name = _normalize_carrier_name(carrier_name)
        screenshot_path = f"/tmp/portal_screenshot_{normalized_name}_{timestamp}.png"
        Path(screenshot_path).write_bytes(screenshot_bytes)
        print(f"\nScreenshot saved: {screenshot_path}")

        # Upload screenshot if API credentials provided
        if api_base_url and auth_token:
            try:
                import httpx

                quote_id = carrier_config.get("quote_id")
                if quote_id:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"{api_base_url}/broker/quotes/{quote_id}/portal-screenshot",
                            headers={"Authorization": f"Bearer {auth_token}"},
                            files={"file": (f"portal_{normalized_name}.png", screenshot_bytes, "image/png")},
                        )
                        if resp.status_code == 200:
                            print("Screenshot uploaded to API.")
                        else:
                            print(f"Screenshot upload failed: {resp.status_code}")
            except ImportError:
                print("httpx not installed -- screenshot not uploaded to API.")
            except Exception as e:
                print(f"Screenshot upload error: {e}")

        await browser.close()

    return {
        "screenshot_path": screenshot_path,
        "fields_filled": result.get("fields_filled", []),
        "status": "ready_for_review",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Submit to carrier portal via Playwright")
    parser.add_argument("--project-id", required=True, help="Project UUID")
    parser.add_argument("--carrier-config-id", required=True, help="CarrierConfig UUID")
    parser.add_argument("--api-base-url", default="http://localhost:8000", help="Backend API URL")
    parser.add_argument("--auth-token", default=None, help="Bearer token for API calls")
    args = parser.parse_args()

    # In a real invocation, would fetch project/carrier data from API, then call submit_to_portal
    print(f"Portal submitter CLI")
    print(f"  Project ID: {args.project_id}")
    print(f"  Carrier Config ID: {args.carrier_config_id}")
    print(f"  API Base URL: {args.api_base_url}")
    print("  TODO: Fetch project data from API and invoke submit_to_portal()")
