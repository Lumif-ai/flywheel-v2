"""Synchronous httpx client wrapping the Flywheel REST API."""

from __future__ import annotations

import os

import httpx

from flywheel_cli.auth import get_token, clear_credentials
from flywheel_cli.config import get_api_url


class FlywheelAPIError(Exception):
    """Raised when an API call fails. MCP tools catch this and return the message."""

    pass


class FlywheelClient:
    """Thin REST client for the Flywheel API.

    Each MCP tool creates a fresh instance to ensure a valid token on every call.
    All methods raise ``FlywheelAPIError`` on failure -- never raw httpx exceptions.
    """

    def __init__(self) -> None:
        self._token = get_token()
        self._api_url = get_api_url()
        self.frontend_url = os.environ.get(
            "FLYWHEEL_FRONTEND_URL", "http://localhost:5175"
        )
        self._client = httpx.Client(
            base_url=self._api_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_token(self) -> None:
        """Refresh the token if it changed (auto-refresh via get_token)."""
        fresh = get_token()
        if fresh != self._token:
            self._token = fresh
            self._client.headers["Authorization"] = f"Bearer {fresh}"

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """Execute an HTTP request with standard error handling."""
        self._ensure_token()
        try:
            resp = getattr(self._client, method)(url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                clear_credentials()
                raise FlywheelAPIError(
                    "Authentication expired. Run: flywheel login"
                ) from exc
            body = ""
            try:
                body = exc.response.text[:200]
            except Exception:
                pass
            raise FlywheelAPIError(
                f"API error {exc.response.status_code}: {body}"
            ) from exc
        except httpx.RequestError as exc:
            raise FlywheelAPIError(
                f"Cannot reach Flywheel API at {self._api_url}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_skill_run(self, skill_name: str, input_text: str) -> dict:
        """POST /api/v1/skills/runs -- start a new skill run."""
        return self._request(
            "post",
            "/api/v1/skills/runs",
            json={"skill_name": skill_name, "input_text": input_text},
        )

    def get_run(self, run_id: str) -> dict:
        """GET /api/v1/skills/runs/{run_id} -- poll run status."""
        return self._request("get", f"/api/v1/skills/runs/{run_id}")

    def search_context(self, query: str, limit: int = 10) -> dict:
        """GET /api/v1/context/search -- search context entries."""
        return self._request(
            "get", "/api/v1/context/search", params={"q": query, "limit": limit}
        )

    def read_context_file(self, file_name: str, limit: int = 20) -> dict:
        """GET /api/v1/context/files/{file_name}/entries -- read entries from a file."""
        return self._request(
            "get",
            f"/api/v1/context/files/{file_name}/entries",
            params={"limit": limit},
        )

    def write_context(self, file_name: str, content: str) -> dict:
        """POST /api/v1/context/files/{file_name}/entries -- append a context entry."""
        return self._request(
            "post",
            f"/api/v1/context/files/{file_name}/entries",
            json={
                "content": content,
                "source": "mcp-manual",
                "confidence": "medium",
            },
        )

    def list_context_files(self) -> dict:
        """GET /api/v1/context/files -- list available context files."""
        return self._request("get", "/api/v1/context/files")
