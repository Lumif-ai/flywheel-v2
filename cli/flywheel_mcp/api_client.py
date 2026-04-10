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
        # Frontend is hosted at the same origin as the API
        self.frontend_url = os.environ.get(
            "FLYWHEEL_FRONTEND_URL", self._api_url
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

    def start_skill_run(self, skill_name: str, input_text: str, input_data: dict | None = None) -> dict:
        """POST /api/v1/skills/runs -- start a new skill run."""
        payload: dict = {"skill_name": skill_name, "input_text": input_text}
        if input_data is not None:
            payload["input_data"] = input_data
        return self._request("post", "/api/v1/skills/runs", json=payload)

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

    def fetch_skills(self) -> dict:
        """GET /api/v1/skills/ -- list all available skills."""
        return self._request("get", "/api/v1/skills/")

    def fetch_skill_prompt(self, skill_name: str) -> dict:
        """GET /api/v1/skills/{skill_name}/prompt -- get rendered prompt for a skill."""
        return self._request("get", f"/api/v1/skills/{skill_name}/prompt")

    def fetch_meetings(
        self, time: str | None = None, processing_status: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> dict:
        """GET /api/v1/meetings/ -- list meetings with optional time filter."""
        params: dict = {"limit": limit, "offset": offset}
        if time is not None:
            params["time"] = time
        if processing_status is not None:
            params["processing_status"] = processing_status
        return self._request("get", "/api/v1/meetings/", params=params)

    def get_meeting(self, meeting_id: str) -> dict:
        """GET /api/v1/meetings/{meeting_id} -- get full meeting detail."""
        return self._request("get", f"/api/v1/meetings/{meeting_id}")

    def fetch_upcoming(self, limit: int = 10) -> dict:
        """GET /api/v1/meetings/ -- convenience wrapper for upcoming meetings."""
        return self._request(
            "get", "/api/v1/meetings/", params={"time": "upcoming", "limit": limit}
        )

    def fetch_tasks(self, status: str | None = None, limit: int = 50) -> dict:
        """GET /api/v1/tasks/ -- list tasks with optional status filter."""
        params: dict = {"limit": limit}
        if status is not None:
            params["status"] = status
        return self._request("get", "/api/v1/tasks/", params=params)

    def fetch_account(self, account_id: str) -> dict:
        """GET /api/v1/accounts/{account_id} -- get account details."""
        return self._request("get", f"/api/v1/accounts/{account_id}")

    def search_accounts(self, name: str, limit: int = 5) -> dict:
        """GET /api/v1/accounts/ -- search accounts by name (ILIKE)."""
        return self._request(
            "get", "/api/v1/accounts/", params={"search": name, "limit": limit}
        )

    def sync_meetings(self, since: str = "") -> dict:
        """POST /api/v1/meetings/sync -- trigger calendar sync."""
        params = {}
        if since:
            params["since"] = since
        return self._request("post", "/api/v1/meetings/sync", params=params)

    def save_document(
        self,
        title: str,
        skill_name: str,
        markdown_content: str,
        metadata: dict | None = None,
        account_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """POST /api/v1/documents/from-content -- save a document from raw content."""
        payload: dict = {
            "title": title,
            "skill_name": skill_name,
            "markdown_content": markdown_content,
            "metadata": metadata or {},
        }
        if account_id:
            payload["account_id"] = account_id
        if tags:
            payload["tags"] = tags
        return self._request(
            "post",
            "/api/v1/documents/from-content",
            json=payload,
        )

    def save_meeting_summary(
        self,
        meeting_id: str,
        ai_summary: str,
        processing_status: str = "completed",
    ) -> dict:
        """PATCH /api/v1/meetings/{meeting_id} -- save AI summary for a meeting."""
        return self._request(
            "patch",
            f"/api/v1/meetings/{meeting_id}",
            json={
                "ai_summary": ai_summary,
                "processing_status": processing_status,
            },
        )

    def update_task(self, task_id: str, **fields) -> dict:
        """PATCH /api/v1/tasks/{task_id} -- update task fields."""
        return self._request("patch", f"/api/v1/tasks/{task_id}", json=fields)

    # -- Leads (GTM pipeline) ------------------------------------------------

    def upsert_lead(self, **fields) -> dict:
        """POST /api/v1/leads/ -- create or update a lead by company name."""
        return self._request("post", "/api/v1/leads/", json=fields)

    def list_leads(self, **params) -> dict:
        """GET /api/v1/leads/ -- list leads with filters."""
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("get", "/api/v1/leads/", params=clean)

    def get_lead(self, lead_id: str) -> dict:
        """GET /api/v1/leads/{lead_id} -- full lead detail with contacts."""
        return self._request("get", f"/api/v1/leads/{lead_id}")

    def add_lead_contact(self, lead_id: str, **fields) -> dict:
        """POST /api/v1/leads/{lead_id}/contacts -- add a contact."""
        return self._request("post", f"/api/v1/leads/{lead_id}/contacts", json=fields)

    def create_lead_message(self, contact_id: str, **fields) -> dict:
        """POST /api/v1/leads/contacts/{contact_id}/messages -- create message."""
        return self._request(
            "post", f"/api/v1/leads/contacts/{contact_id}/messages", json=fields
        )

    def update_lead_message(self, message_id: str, **fields) -> dict:
        """PATCH /api/v1/leads/messages/{message_id} -- update message status."""
        return self._request(
            "patch", f"/api/v1/leads/messages/{message_id}", json=fields
        )

    def graduate_lead(self, lead_id: str) -> dict:
        """POST /api/v1/leads/{lead_id}/graduate -- promote to account."""
        return self._request("post", f"/api/v1/leads/{lead_id}/graduate")

    # -- Pipeline (unified CRM) ------------------------------------------------

    def list_pipeline(self, **params) -> dict:
        """GET /api/v1/pipeline/ with filter params."""
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("get", "/api/v1/pipeline/", params=clean)

    def create_pipeline_entry(self, **fields) -> dict:
        """POST /api/v1/pipeline/ -- create with dedup."""
        return self._request("post", "/api/v1/pipeline/", json=fields)

    def fetch_pipeline_entry(self, entry_id: str) -> dict:
        """GET /api/v1/pipeline/{id} -- full detail with contacts, activities."""
        return self._request("get", f"/api/v1/pipeline/{entry_id}")

    def update_pipeline_entry(self, entry_id: str, **fields) -> dict:
        """PATCH /api/v1/pipeline/{id}."""
        return self._request("patch", f"/api/v1/pipeline/{entry_id}", json=fields)

    def add_pipeline_contact(self, entry_id: str, **fields) -> dict:
        """POST /api/v1/pipeline/{id}/contacts."""
        return self._request("post", f"/api/v1/pipeline/{entry_id}/contacts", json=fields)

    def search_pipeline(self, query: str, limit: int = 5) -> dict:
        """GET /api/v1/pipeline/search?q=..."""
        return self._request("get", "/api/v1/pipeline/search", params={"q": query, "limit": limit})

    def create_pipeline_activity(self, entry_id: str, **fields) -> dict:
        """POST /api/v1/pipeline/{id}/activities."""
        return self._request("post", f"/api/v1/pipeline/{entry_id}/activities", json=fields)

    def update_pipeline_activity(self, entry_id: str, activity_id: str, **fields) -> dict:
        """PATCH /api/v1/pipeline/{id}/activities/{activity_id}."""
        return self._request("patch", f"/api/v1/pipeline/{entry_id}/activities/{activity_id}", json=fields)

    def list_pipeline_activities(self, entry_id: str, **params) -> dict:
        """GET /api/v1/pipeline/{id}/activities -- list activities for an entry."""
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("get", f"/api/v1/pipeline/{entry_id}/activities", params=clean)

    def list_pipeline_contacts(self, **params) -> dict:
        """GET /api/v1/pipeline/contacts/ with filter params."""
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("get", "/api/v1/pipeline/contacts/", params=clean)
