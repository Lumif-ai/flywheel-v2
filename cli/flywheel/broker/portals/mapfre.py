#!/usr/bin/env python3
# flywheel.broker.portals.mapfre — Mapfre carrier portal fill script (moved from skills/broker/portals/ in Phase 152.1).
"""Mapfre carrier portal script.

Usage: Invoked by /broker:fill-portal trigger via SKILL.md router.

Contract:
- fill_portal() fills fields ONLY -- never clicks submit or confirm.
- The broker reviews the filled form and submits manually.
- Selectors in mapfre.yaml are PLACEHOLDERS -- update after live testing.
"""
import asyncio
from pathlib import Path
from typing import Optional

import yaml
from playwright.async_api import Page

# ---- State directory (MIGRATE-03 required). Never __file__-relative. ----
STATE_DIR = Path.home() / ".flywheel" / "broker" / "portals" / "mapfre"
STATE_DIR.mkdir(parents=True, exist_ok=True)

from .base import safe_fill, safe_select, take_screenshot, wait_for_confirmation

# YAML is a CODE ASSET bundled alongside this module (not state) — __file__-relative is correct
# because Phase 150 extracts the bundle to a temp dir where mapfre.py and mapfre.yaml are siblings.
# STATE goes to STATE_DIR above; CONFIG stays next to the code.
_YAML_PATH = Path(__file__).parent / "mapfre.yaml"


def _load_field_map() -> dict:
    """Load Mapfre field selectors from mapfre.yaml."""
    with open(_YAML_PATH) as f:
        return yaml.safe_load(f)


def _resolve_source(source: str, project: dict, coverages: list) -> Optional[str]:
    """Resolve a dotted source path like 'project.name' or 'coverages[0].premium'."""
    try:
        if source.startswith("project."):
            return str(project.get(source[len("project."):], "") or "")
        elif source.startswith("coverages[0]."):
            # Handle coverages[0].field_name correctly
            field = source.split(".")[-1]
            if coverages:
                return str(coverages[0].get(field, "") or "")
        return ""
    except Exception:
        return ""


async def fill_portal(
    page: Page,
    project: dict,
    coverages: list,
    documents: list,
) -> dict:
    """Fill Mapfre portal fields from project + coverage data.

    Args:
        page: Playwright Page (broker already logged in)
        project: Project dict from backend API
        coverages: List of coverage dicts for this project
        documents: List of document dicts (used for upload fields, if any)

    Returns:
        {
            "fields_filled": ["project_name", ...],
            "fields_skipped": ["insured_rfc (PLACEHOLDER)", ...],
            "status": "ready_for_review",
            "screenshot_path": "<STATE_DIR>/screenshots/mapfre_*.png"
        }

    NOTE: Selectors in mapfre.yaml are PLACEHOLDERS until live portal testing.
    Skipped fields (placeholder selectors won't exist) are expected on first run.
    """
    config = _load_field_map()
    fields = config.get("fields", {})

    fields_filled: list = []
    fields_skipped: list = []

    for field_name, field_config in fields.items():
        selector = field_config.get("selector", "")
        field_type = field_config.get("type", "text")
        source = field_config.get("source", "")

        value = _resolve_source(source, project, coverages)

        if field_type == "select":
            await safe_select(page, selector, value, field_name, fields_filled, fields_skipped)
        else:
            await safe_fill(page, selector, value, field_name, fields_filled, fields_skipped)

    # Screenshot after filling -- routed to STATE_DIR/screenshots per MIGRATE-03
    screenshot_path = await take_screenshot(page, "mapfre", state_dir=STATE_DIR)

    print(f"\nFields filled ({len(fields_filled)}): {', '.join(fields_filled) or 'none'}")
    print(f"Fields skipped ({len(fields_skipped)}): {', '.join(fields_skipped) or 'none'}")
    if fields_skipped:
        print("\nNote: Skipped fields are expected if selectors are still PLACEHOLDERS.")
        print(f"Update selectors in: {_YAML_PATH}")

    await wait_for_confirmation(
        "Review the filled form in the browser window above.\n"
        f"Screenshot saved to: {screenshot_path}\n"
        "Press Enter to confirm the fill looks correct, or Ctrl+C to abort."
    )

    return {
        "fields_filled": fields_filled,
        "fields_skipped": fields_skipped,
        "status": "ready_for_review",
        "screenshot_path": screenshot_path,
    }
