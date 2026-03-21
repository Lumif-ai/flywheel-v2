"""Tests for POST /auth/refresh endpoint.

Uses FastAPI TestClient with httpx mocking -- no real Supabase calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flywheel.main import app


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# TestRefreshToken
# ---------------------------------------------------------------------------


class TestRefreshToken:
    def test_refresh_returns_new_tokens(self, client):
        """POST /auth/refresh with valid refresh_token returns new token set."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_at": 1700000000,
        }

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http):
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid-refresh-token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new-access-token"
        assert data["refresh_token"] == "new-refresh-token"
        assert data["expires_at"] == 1700000000

    def test_refresh_invalid_token_returns_401(self, client):
        """POST /auth/refresh with invalid token returns 401."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400  # Supabase returns 400 for invalid refresh
        mock_resp.json.return_value = {"error": "invalid_grant"}

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http):
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "expired-token"},
            )

        assert resp.status_code == 401
        assert "Invalid or expired" in resp.json()["message"]

    def test_refresh_missing_body_returns_422(self, client):
        """POST /auth/refresh without body returns 422."""
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422

    def test_refresh_network_error_returns_502(self, client):
        """POST /auth/refresh returns 502 when auth provider unreachable."""
        import httpx

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http):
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "some-token"},
            )

        assert resp.status_code == 502
        assert "auth provider" in resp.json()["message"]

    def test_refresh_is_public_no_auth_needed(self, client):
        """POST /auth/refresh does not require authentication header."""
        # This verifies the endpoint is accessible without auth.
        # It will fail at the httpx call level, not auth level.
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_at": 9999999999,
        }

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http):
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "any-token"},
            )

        # Should succeed (200), not 401/403 -- proves no auth dependency
        assert resp.status_code == 200
