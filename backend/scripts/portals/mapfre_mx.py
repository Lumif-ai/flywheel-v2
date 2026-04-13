"""Mapfre Mexico portal automation script.

This script fills the Mapfre Mexico insurance portal form fields.
It does NOT submit the form -- that requires screenshot review and explicit confirmation.

Selectors are placeholders and must be updated when testing against the real portal.
"""

from playwright.async_api import Page


async def fill_portal(
    page: Page,
    project: dict,
    coverages: list[dict],
    documents: list[dict],
) -> dict:
    """Fill Mapfre Mexico portal form fields.

    Args:
        page: Playwright Page, already logged in to Mapfre portal
        project: {"name": str, "project_type": str, "contract_value": float, "currency": str, "language": str}
        coverages: [{"coverage_type": str, "required_limit": float, "description": str}]
        documents: [{"file_id": str, "document_type": str, "display_name": str}]

    Returns:
        {"fields_filled": [...], "status": "ready_for_review"}
    """
    fields_filled = []

    # --- Project Information ---
    # NOTE: These selectors are PLACEHOLDERS. Update with real Mapfre portal selectors
    # after testing with actual portal access.

    try:
        await page.fill("#project-name", project.get("name", ""))
        fields_filled.append("project_name")
    except Exception:
        pass  # Field may not exist on this portal version

    try:
        contract_value = project.get("contract_value")
        if contract_value is not None:
            await page.fill("#contract-value", str(contract_value))
            fields_filled.append("contract_value")
    except Exception:
        pass

    try:
        await page.fill("#project-type", project.get("project_type", ""))
        fields_filled.append("project_type")
    except Exception:
        pass

    # --- Coverage Information ---
    for i, cov in enumerate(coverages):
        try:
            await page.fill(f"#coverage-type-{i}", cov.get("coverage_type", ""))
            fields_filled.append(f"coverage_type_{i}")
        except Exception:
            pass
        try:
            limit = cov.get("required_limit")
            if limit is not None:
                await page.fill(f"#coverage-limit-{i}", str(limit))
                fields_filled.append(f"coverage_limit_{i}")
        except Exception:
            pass

    # --- Document Upload ---
    # NOTE: Document upload fields are portal-specific.
    # For Mapfre, documents may need to be uploaded via file input elements.
    # This is left as a placeholder for real portal testing.

    return {
        "fields_filled": fields_filled,
        "status": "ready_for_review",
    }
