"""Synchronous httpx client wrapping the Flywheel REST API."""

from __future__ import annotations

import base64
import logging
import os
import secrets
import sys
import time

import httpx

from flywheel_cli.auth import get_token, clear_credentials
from flywheel_cli.config import get_api_url

logger = logging.getLogger(__name__)


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
        # Frontend may be on a different domain than the API
        self.frontend_url = os.environ.get(
            "FLYWHEEL_FRONTEND_URL", "https://uat-flywheel.lumif.ai"
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

    def read_context_file(self, file_name: str, limit: int = 100, offset: int = 0) -> dict:
        """GET /api/v1/context/files/{file_name}/entries -- read entries from a file.

        The backend supports pagination: pass offset to page through large files.
        Response shape: {"items": [...], "total": N, "offset": N, "limit": N, "has_more": bool}
        Use the pagination helper pattern from context-protocol.md to read all entries.
        """
        return self._request(
            "get",
            f"/api/v1/context/files/{file_name}/entries",
            params={"limit": limit, "offset": offset},
        )

    def write_context(
        self,
        file_name: str,
        content: str,
        source: str = "mcp-manual",
        confidence: str = "medium",
        metadata: dict | None = None,
    ) -> dict:
        """POST /api/v1/context/files/{file_name}/entries -- append a context entry.

        Args:
            file_name: Context file name (e.g., "pain-points.md")
            content: Entry text content (min 10 chars)
            source: Source identifier (default "mcp-manual")
            confidence: "low", "medium", or "high" (default "medium")
            metadata: Optional JSONB metadata dict, e.g.:
                      {"meeting_type": "discovery", "meeting_date": "2026-04-11"}
        """
        body: dict = {
            "content": content,
            "source": source,
            "confidence": confidence,
        }
        if metadata:
            body["metadata"] = metadata
        return self._request(
            "post",
            f"/api/v1/context/files/{file_name}/entries",
            json=body,
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

    @staticmethod
    def _has_any_cache_trace(cache, name: str) -> bool:
        """True if the cache's index knows about ``name`` (even if the
        underlying ``<sha>/`` dir is missing or unreadable).

        Used by the offline-fallback path to distinguish "we had a cached
        bundle that's now unusable" (BundleCacheError) from "we never
        cached this skill" (raw BundleFetchError).
        """
        index = cache._load_index()
        return name in index

    def _fetch_shas_only(
        self, name: str, correlation_id: str
    ) -> dict[str, str] | None:
        """Single lightweight GET to ``/assets/bundle?shas_only=true``.

        Returns a ``{bundle_name: sha256}`` dict on success, or ``None``
        on any failure (network, non-200, empty body). Used by the cache
        layer to answer "is my cached SHA still authoritative" in a single
        round-trip without re-shipping bundle bytes.

        This method deliberately does NOT retry — it's a best-effort
        freshness probe. If it fails, the caller falls through to the full
        fetch retry loop (which has its own 3x backoff).
        """
        path = f"/api/v1/skills/{name}/assets/bundle?shas_only=true"
        headers = {"X-Flywheel-Correlation-ID": correlation_id}
        try:
            resp = self._client.get(path, headers=headers)
        except httpx.RequestError:
            return None
        if resp.status_code != 200:
            return None
        try:
            body = resp.json()
        except Exception:
            return None
        shas = {entry["name"]: entry["sha256"] for entry in body.get("bundles", [])}
        return shas or None

    def fetch_skill_assets_bundle(
        self,
        name: str,
        *,
        bypass_cache: bool = False,
        correlation_id: str | None = None,
    ) -> tuple[dict, list[tuple[str, str, bytes]]]:
        """GET /api/v1/skills/{name}/assets/bundle -- Phase 150 fanout +
        Phase 151 cache + correlation-id integration.

        Walks ``depends_on`` server-side and returns consumer + transitive
        library bundles in topological order (deepest dep first, consumer
        last; consumers with ``assets=[]`` are absent from the bundles list
        but still present in ``deps``).

        Phase 151 cache flow (when ``bypass_cache=False``):
            1. Fresh cache hit -> return immediately (ZERO network calls).
            2. Stale cache hit -> issue ``?shas_only=true`` pre-check.
               If SHAs match server-side, bump TTL + serve cached bytes
               (one network call, no bundle bytes).
            3. Otherwise full fetch (retry loop unchanged) + repopulate
               cache on success.

        Offline fallback:
            - Backend unreachable + fresh cache -> serve cached + stderr
              WARN (Phase 151 SC2).
            - Backend unreachable + stale/absent cache -> raise
              :class:`BundleCacheError`.

        Retry policy (unchanged from Phase 150):
            - 3x exponential backoff (0.5s, 1s, 2s) on network errors
              (:class:`httpx.RequestError`) and 5xx responses.
            - 401: one-shot token refresh; if still-401 after refresh,
              credentials are cleared and :class:`BundleFetchError` is
              raised with a ``flywheel login`` hint.
            - 403/404: raise :class:`BundleFetchError` immediately.

        Args:
            name: Root skill name.
            bypass_cache: If True, skip both cache read AND cache write
                (used by ``flywheel_refresh_skills``). Default False.
            correlation_id: 8-hex-char forensic ID threaded through every
                retry attempt as ``X-Flywheel-Correlation-ID`` header.
                Auto-generated via ``secrets.token_hex(4)`` when None.

        Returns:
            ``(metadata, bundles)`` — same shape as Phase 150.

        Raises:
            BundleFetchError: HTTP/transport failure that exhausts the
                retry budget, or terminal 401/403/404/other-4xx — AND
                no fresh cache available.
            BundleCacheError: Backend unreachable and no fresh/stale
                cache entry to fall back on.
        """
        # Deferred imports — bundle.py imports FlywheelClient lazily from
        # its context manager, so we keep the dep-graph clean.
        from flywheel_mcp.bundle import (
            BundleCacheError,
            BundleFetchError,
            BundleIntegrityError,
        )
        from flywheel_mcp.cache import BundleCache

        correlation_id = correlation_id or secrets.token_hex(4)

        # -----  Cache read path ------------------------------------------------
        cache: BundleCache | None = None
        if not bypass_cache:
            cache = BundleCache()
            try:
                fresh = cache.get_fresh(name)
            except BundleIntegrityError as exc:
                # Tamper found during cache load — dir already auto-deleted.
                logger.warning(
                    "cache_entry_tampered: skill=%s correlation_id=%s — "
                    "falling through to full fetch",
                    name, correlation_id,
                    extra={"correlation_id": correlation_id},
                )
                fresh = None
                # Treat the BundleIntegrityError as handled; refetch will
                # repopulate the cache with authoritative bytes.
                _ = exc
            if fresh is not None:
                return fresh.as_tuple()

            # Stale cache + SHA pre-check: if server confirms our cached
            # SHAs are authoritative, bump TTL and serve cached bytes.
            if cache.has_stale(name):
                server_shas = self._fetch_shas_only(name, correlation_id)
                if server_shas is not None:
                    if cache.extend_ttl_if_sha_match(name, server_shas):
                        stale = cache.get_stale(name)
                        if stale is not None:
                            return stale.as_tuple()
                    # SHAs mismatched — fall through to full fetch.

        # -----  Full fetch with 3x retry + correlation_id header --------------
        path = f"/api/v1/skills/{name}/assets/bundle"
        headers = {"X-Flywheel-Correlation-ID": correlation_id}

        def _do_get() -> httpx.Response:
            """Execute the GET with 3x backoff. Raises BundleFetchError on
            exhausted retries. Threads correlation_id header on every attempt."""
            delays = [0.0, 0.5, 1.0, 2.0]
            last_exc: BundleFetchError | None = None
            for delay in delays:
                if delay > 0:
                    time.sleep(delay)
                try:
                    resp = self._client.get(path, headers=headers)
                except httpx.RequestError as exc:
                    last_exc = BundleFetchError(
                        name, None, f"Network error reaching Flywheel: {exc}"
                    )
                    continue
                if resp.status_code >= 500:
                    last_exc = BundleFetchError(
                        name,
                        resp.status_code,
                        f"Flywheel backend returned {resp.status_code}. "
                        f"Retry in a moment.",
                    )
                    continue
                return resp
            assert last_exc is not None
            raise last_exc

        def _serve_cached_with_warn() -> tuple[dict, list[tuple[str, str, bytes]]] | None:
            """Try to serve a stale cache entry after network failure.

            Returns a ``(metadata, bundles)`` tuple with stderr WARN emitted
            on success, or ``None`` if no stale entry exists.
            """
            if bypass_cache or cache is None:
                return None
            try:
                stale = cache.get_stale(name)
            except BundleIntegrityError:
                # Tamper during offline load — dir auto-deleted. Nothing to serve.
                return None
            if stale is None:
                return None
            sys.stderr.write(
                f"WARN: Backend unreachable. Using cached {name} bundle "
                f"(cached {stale.age_human} ago, {stale.ttl_remaining_human}).\n"
            )
            logger.warning(
                "offline_fallback: skill=%s age=%s ttl=%s correlation_id=%s",
                name, stale.age_human, stale.ttl_remaining_human, correlation_id,
                extra={"correlation_id": correlation_id},
            )
            return stale.as_tuple()

        self._ensure_token()
        try:
            resp = _do_get()
        except BundleFetchError as exc:
            # Network / 5xx exhaustion — try offline fallback.
            fallback = _serve_cached_with_warn()
            if fallback is not None:
                return fallback
            # No usable cache entry. If we have ANY trace of the skill in
            # the cache (index entry OR stale <sha>/ dir) the user-facing
            # signal should be BundleCacheError — the user knows they had
            # a cache that's now unusable. Matches CONTEXT §Error taxonomy.
            if not bypass_cache and cache is not None and self._has_any_cache_trace(
                cache, name
            ):
                raise BundleCacheError(
                    skill_name=name,
                    reason=(
                        "Cached bundle expired (>24h) and backend unreachable. "
                        "Connect to network and retry, or run "
                        "`flywheel refresh-skills` when online."
                    ),
                ) from exc
            raise

        # -----  One-shot 401 refresh (Pitfall 9: no recursion, no loop).
        if resp.status_code == 401:
            self._ensure_token()
            try:
                resp = _do_get()
            except BundleFetchError as exc:
                fallback = _serve_cached_with_warn()
                if fallback is not None:
                    return fallback
                raise exc
            if resp.status_code == 401:
                clear_credentials()
                raise BundleFetchError(
                    name,
                    401,
                    "Session expired. Run `flywheel login` and retry.",
                )

        # -----  Terminal errors — map to BundleFetchError with actionable
        # messages matching Phase 148 + Plan 01 contract.
        if resp.status_code == 403:
            raise BundleFetchError(
                name,
                403,
                "This skill runs server-side only and does not ship assets.",
            )
        if resp.status_code == 404:
            raise BundleFetchError(
                name,
                404,
                f"Skill '{name}' not found. Check the skill name for typos.",
            )
        if resp.status_code >= 400:
            body = ""
            try:
                body = resp.text[:200]
            except Exception:
                pass
            raise BundleFetchError(
                name,
                resp.status_code,
                f"Flywheel API error: {body or 'no body'}",
            )

        # -----  Success: parse per-bundle entries.
        body = resp.json()
        bundles: list[tuple[str, str, bytes]] = []
        for entry in body.get("bundles", []):
            bundles.append(
                (
                    entry["name"],
                    entry["sha256"],
                    base64.b64decode(entry["bundle_b64"]),
                )
            )
        metadata = {
            "skill": body["skill"],
            "deps": body.get("deps", []),
            "rollup_sha": body.get("rollup_sha", ""),
        }

        # -----  Cache write on success (best-effort — never fail user fetch).
        if not bypass_cache and cache is not None and bundles:
            try:
                cache.put(name, metadata, bundles, correlation_id=correlation_id)
            except Exception as exc:  # cache disk full, permission error, etc.
                logger.warning(
                    "cache_write_failed: skill=%s err=%s correlation_id=%s",
                    name, exc, correlation_id,
                    extra={"correlation_id": correlation_id},
                )

        return metadata, bundles

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
