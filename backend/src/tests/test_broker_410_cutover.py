"""Phase 150.1 Plan 04 — 410 Gone cutover integration tests.

Every deprecated broker endpoint must return HTTP 410 with the
machine-actionable migration-hint body Claude-in-conversation can
auto-route on to the new Pattern 3a /extract/{op} + /save/{op} pair.

Paths flipped to 410 in Plan 04:
  * POST /api/v1/broker/projects/{project_id}/analyze              — contract-analysis
  * POST /api/v1/broker/quotes/{quote_id}/extract                  — quote-extraction
  * POST /api/v1/broker/projects/{project_id}/draft-solicitations  — solicitation-draft
  * POST /api/v1/broker/projects/{project_id}/draft-recommendation — recommendation-draft

Run: ``cd backend && PYTHONPATH=src ./.venv/bin/pytest \\
        src/tests/test_broker_410_cutover.py -v``
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.main import app


# ---------------------------------------------------------------------------
# Parametrized — each legacy path returns 410 with machine-actionable body
# ---------------------------------------------------------------------------


class TestBrokerEndpointDeprecation:
    """All 4 legacy broker endpoints return HTTP 410 with Plan-04 body shape."""

    @pytest.mark.parametrize(
        "path_template,operation",
        [
            ("/api/v1/broker/projects/{id}/analyze", "contract-analysis"),
            ("/api/v1/broker/quotes/{id}/extract", "quote-extraction"),
            ("/api/v1/broker/projects/{id}/draft-solicitations", "solicitation-draft"),
            (
                "/api/v1/broker/projects/{id}/draft-recommendation",
                "recommendation-draft",
            ),
        ],
    )
    def test_legacy_endpoint_returns_410(
        self, path_template: str, operation: str
    ) -> None:
        """Every deprecated path returns 410 with the full migration-hint body."""
        client = TestClient(app)
        path = path_template.format(id=str(uuid4()))
        response = client.post(path, json={})

        assert response.status_code == 410, (
            f"{path}: expected 410 Gone, got {response.status_code} — "
            f"body: {response.text}"
        )

        body = response.json()
        # Flywheel's global error envelope wraps HTTPException.detail under
        # `message` (stringified) — see backend/src/flywheel/api/errors.py.
        # Either the raw FastAPI `detail` dict shape or the wrapped `message`
        # string shape should contain the migration markers. We accept both.
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else None
        message = body.get("message")

        if detail is not None:
            # Raw FastAPI shape
            assert detail.get("error") == "endpoint_deprecated", body
            assert detail.get("operation") == operation, body
            assert detail.get("migrated_in") == "150.1", body
            replacement = detail.get("replacement", "")
            assert f"/extract/{operation}" in replacement, body
            assert f"/save/{operation}" in replacement, body
        else:
            # Wrapped envelope — assert markers appear in the stringified detail
            assert message is not None, body
            assert "endpoint_deprecated" in message, body
            assert operation in message, body
            assert "150.1" in message, body
            assert f"/extract/{operation}" in message, body
            assert f"/save/{operation}" in message, body

    def test_new_extract_endpoints_still_registered(self) -> None:
        """Sanity: the 10 Pattern 3a replacement endpoints didn't break."""
        paths = app.openapi()["paths"]
        for op in [
            "contract-analysis",
            "policy-extraction",
            "quote-extraction",
            "solicitation-draft",
            "recommendation-draft",
        ]:
            extract_path = f"/api/v1/broker/extract/{op}"
            save_path = f"/api/v1/broker/save/{op}"
            assert extract_path in paths, f"{extract_path} missing from OpenAPI"
            assert save_path in paths, f"{save_path} missing from OpenAPI"

    def test_legacy_endpoints_still_registered(self) -> None:
        """Sanity: the 4 legacy paths are still registered (but return 410)."""
        paths = app.openapi()["paths"]
        for legacy in [
            "/api/v1/broker/projects/{project_id}/analyze",
            "/api/v1/broker/quotes/{quote_id}/extract",
            "/api/v1/broker/projects/{project_id}/draft-solicitations",
            "/api/v1/broker/projects/{project_id}/draft-recommendation",
        ]:
            assert legacy in paths, f"{legacy} missing from OpenAPI"
