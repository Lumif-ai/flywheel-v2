"""Granola API adapter.

Abstracts the real Granola REST API shape for use by the Intelligence Flywheel
sync and processing pipelines.

Real API (verified 2026-03-28):
- Base URL: https://public-api.granola.ai/v1
- Auth: Authorization: Bearer <api_key>
- Resources are called "notes" (not "meetings") — key endpoint: GET /v1/notes
- No /v1/me endpoint — key validation via GET /v1/notes?page_size=1
- Transcripts returned inline via GET /v1/notes/{id}?include=transcript
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

GRANOLA_API_BASE = "https://public-api.granola.ai/v1"


@dataclass
class RawMeeting:
    """Lightweight meeting summary from the Granola list endpoint."""

    external_id: str
    title: str
    meeting_date: datetime
    duration_mins: Optional[int]
    attendees: list[dict]
    ai_summary: Optional[str]


@dataclass
class MeetingContent:
    """Full meeting content including transcript from the Granola detail endpoint."""

    external_id: str
    transcript: str
    ai_summary: Optional[str]
    attendees: list[dict]
    metadata: dict = field(default_factory=dict)


async def test_connection(api_key: str) -> tuple[bool, str | None]:
    """Validate a Granola API key by listing one note.

    Returns (True, None) on success, (False, error_message) on failure.
    Uses GET /v1/notes?page_size=1 because Granola has no /v1/me endpoint.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{GRANOLA_API_BASE}/notes",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"page_size": 1},
            )
            if resp.status_code == 200:
                return True, None
            elif resp.status_code == 401:
                return False, "Invalid API key. Check your Granola settings."
            else:
                return False, f"Granola API returned {resp.status_code}"
        except httpx.RequestError as e:
            return False, f"Could not reach Granola API: {e}"


async def list_meetings(
    api_key: str,
    since: datetime | None = None,
    since_override: str | None = None,
) -> list[RawMeeting]:
    """Fetch ALL meetings from Granola, paginating through results.

    Uses created_after for incremental sync (not updated_after — Phase 60
    only ingests new meetings; updated content sync is Phase 61+).

    Args:
        api_key: Granola API key.
        since: Datetime cursor for incremental sync. Ignored if since_override is set.
        since_override: Optional ISO date string override (e.g. '2025-01-01').
            When provided, used instead of `since`.

    Response JSON uses key "notes" (not "meetings").
    Field mapping: item["id"] -> external_id, item["created_at"] -> meeting_date,
    item.get("summary_text") -> ai_summary.
    Duration computed from calendar_event.start_time/end_time; None if absent.
    Attendees extracted from calendar_event.invitees.
    """
    PAGE_SIZE = 100

    # Resolve the effective since datetime
    effective_since: datetime | None = since
    if since_override:
        effective_since = datetime.fromisoformat(since_override).replace(
            tzinfo=timezone.utc
        )

    params: dict = {"page_size": PAGE_SIZE}
    if effective_since:
        params["created_after"] = effective_since.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    all_meetings: list[RawMeeting] = []

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"{GRANOLA_API_BASE}/notes",
                headers={"Authorization": f"Bearer {api_key}"},
                params=params,
            )
            resp.raise_for_status()

            data = resp.json()
            notes = data.get("notes", [])

            for item in notes:
                cal = item.get("calendar_event") or {}

                # Compute duration from calendar_event start/end times if both are present
                start = cal.get("start_time")
                end = cal.get("end_time")
                duration_mins: Optional[int] = None
                if start and end:
                    try:
                        duration_mins = int(
                            (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds // 60
                        )
                    except Exception:
                        pass

                # Attendees from calendar_event.invitees; default to empty list
                attendees = [
                    {"email": a.get("email"), "name": a.get("name"), "is_external": True}
                    for a in cal.get("invitees", [])
                ]

                all_meetings.append(
                    RawMeeting(
                        external_id=item["id"],
                        title=item.get("title") or "Untitled",
                        meeting_date=datetime.fromisoformat(item["created_at"]),
                        duration_mins=duration_mins,
                        attendees=attendees,
                        ai_summary=item.get("summary_text"),
                    )
                )

            # Pagination: check for cursor-based or offset-based next page
            next_cursor = data.get("next_cursor") or data.get("next_page") or data.get("cursor")
            if next_cursor:
                params["cursor"] = next_cursor
            elif len(notes) >= PAGE_SIZE:
                # Offset-based fallback: use created_before set to oldest in batch
                oldest_created_at = min(
                    item["created_at"] for item in notes if item.get("created_at")
                )
                params["created_before"] = oldest_created_at
            else:
                # Fewer results than page size — no more pages
                break

    return all_meetings


async def get_meeting_content(api_key: str, external_id: str) -> MeetingContent:
    """Fetch full note content including transcript.

    Uses a single GET /v1/notes/{id}?include=transcript call.
    Granola returns transcript as an array of {speaker, text, start_time, end_time};
    joined here as "[speaker]: text" lines.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{GRANOLA_API_BASE}/notes/{external_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"include": "transcript"},
        )
        resp.raise_for_status()

    detail = resp.json()

    # Join transcript segments into a readable string
    transcript_parts = detail.get("transcript") or []
    transcript_text = "\n".join(
        f"[{t.get('speaker', 'Unknown')}]: {t.get('text', '')}"
        for t in transcript_parts
    )

    cal = detail.get("calendar_event") or {}
    attendees = [
        {"email": a.get("email"), "name": a.get("name"), "is_external": True}
        for a in cal.get("invitees", [])
    ]

    return MeetingContent(
        external_id=external_id,
        transcript=transcript_text,
        ai_summary=detail.get("summary_text"),
        attendees=attendees,
        metadata={
            "provider": "granola",
            "title": detail.get("title"),
            "date": detail.get("created_at"),
        },
    )
