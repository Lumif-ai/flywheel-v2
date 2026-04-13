# Portal Scripts

Carrier-specific Playwright automation scripts for filling insurance portal forms.

## Purpose

These scripts are used by the portal submission engine (`flywheel.engines.portal_submitter`) to automate form filling on carrier portals. They run **locally** on the broker's machine -- never on the server.

## Standard Interface

Every portal script MUST export the following async function:

```python
async def fill_portal(
    page: Page,
    project: dict,
    coverages: list[dict],
    documents: list[dict],
) -> dict:
```

### Parameters

- **page** (`playwright.async_api.Page`): A Playwright Page object already navigated to the carrier portal and logged in by the broker.
- **project** (`dict`): Project data with keys: `name`, `project_type`, `contract_value`, `currency`, `language`
- **coverages** (`list[dict]`): Coverage requirements with keys: `coverage_type`, `required_limit`, `description`
- **documents** (`list[dict]`): Available documents with keys: `file_id`, `document_type`, `display_name`

### Return Format

```python
{"fields_filled": ["field_name_1", "field_name_2", ...], "status": "ready_for_review"}
```

## Rules

1. Scripts must **NOT** click any submit/confirm/send buttons. Only fill fields.
2. Submission is confirmed separately after the mandatory screenshot review gate.
3. Use try/except around each field fill -- portals change and scripts should be resilient.
4. Report all successfully filled fields in the return value.

## Naming Convention

Scripts are named after the carrier (normalized):
- Lowercase
- Spaces replaced with underscores
- Hyphens replaced with underscores

Examples:
- Mapfre Mexico -> `mapfre_mx.py`
- AXA Seguros -> `axa_seguros.py`
- Zurich Mexico -> `zurich_mexico.py`

## Adding a New Carrier

1. Create `{carrier_name_normalized}.py` in this directory
2. Implement `fill_portal()` following the interface above
3. Use placeholder selectors initially, update after testing with real portal access
4. Test with `portal_submitter.py` in headless=False mode
