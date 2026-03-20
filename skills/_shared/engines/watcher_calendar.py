"""
watcher_calendar.py - Google Calendar integration for Flywheel.

Polls Google Calendar every 15 minutes for upcoming external meetings and
auto-triggers meeting-prep skill. Uses OAuth 2.0 via InstalledAppFlow with
localhost redirect for local-first setup (no public HTTPS endpoint needed).

External meetings are detected by comparing attendee email domains against
the user's company domain. When an external meeting is found within the next
60 minutes, meeting-prep is auto-triggered via execute_skill().

Public API:
    CalendarWatcher - WatcherBase subclass for Google Calendar polling
    connect_calendar(user_id) -> bool - OAuth consent flow
    get_calendar_service(user_id) - Build authenticated Calendar API service
    register_calendar_watcher(manager, user_id, company_domain) - Register watcher
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from integration_framework import (
    IntegrationManager,
    WatcherBase,
    is_integration_enabled,
)
from oauth_store import has_credentials, load_credentials, save_credentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]

CLIENT_SECRET_PATH = Path.home() / ".flywheel" / "oauth" / "client_secret.json"

# Polling window: check events in next 60 minutes
POLL_WINDOW_MINUTES = 60

# Registration interval: 15-minute polling cycle
POLL_INTERVAL_MINUTES = 15

# Service name for oauth_store
SERVICE_NAME = "calendar"

# ---------------------------------------------------------------------------
# Google API imports (graceful fallback)
# ---------------------------------------------------------------------------

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False
    logger.info(
        "Google API libraries not installed. Calendar integration unavailable. "
        "Install with: pip3 install google-api-python-client google-auth-oauthlib google-auth"
    )


# ---------------------------------------------------------------------------
# OAuth handling
# ---------------------------------------------------------------------------


def connect_calendar(user_id: str) -> bool:
    """Run OAuth consent flow for Google Calendar.

    Uses InstalledAppFlow with localhost redirect. Opens browser for
    user consent, then saves credentials via oauth_store.

    This is the /fly connect calendar flow.

    Args:
        user_id: User identifier.

    Returns:
        True if credentials were successfully obtained and saved.

    Raises:
        RuntimeError: If Google API libraries are not installed.
        FileNotFoundError: If client_secret.json is not found.
    """
    if not _GOOGLE_AVAILABLE:
        raise RuntimeError(
            "Google API libraries not installed. "
            "Install with: pip3 install google-api-python-client google-auth-oauthlib google-auth"
        )

    if not CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"OAuth client secret not found at {CLIENT_SECRET_PATH}. "
            "Download from Google Cloud Console > APIs & Services > Credentials."
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_PATH), SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save credentials via oauth_store
        creds_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        }
        save_credentials(user_id, SERVICE_NAME, creds_data)
        logger.info("Calendar OAuth completed for user %s", user_id)
        return True

    except Exception as e:
        logger.error("Calendar OAuth failed for user %s: %s", user_id, e)
        return False


def get_calendar_service(user_id: str):
    """Build an authenticated Google Calendar API service.

    Loads credentials from oauth_store, refreshes if expired,
    and builds the Calendar v3 service.

    Args:
        user_id: User identifier.

    Returns:
        Google Calendar API service object.

    Raises:
        ValueError: If no credentials are saved for this user.
        RuntimeError: If Google API libraries are not installed.
    """
    if not _GOOGLE_AVAILABLE:
        raise RuntimeError(
            "Google API libraries not installed. "
            "Install with: pip3 install google-api-python-client google-auth-oauthlib google-auth"
        )

    creds_data = load_credentials(user_id, SERVICE_NAME)
    if creds_data is None:
        raise ValueError(
            f"No calendar credentials for user {user_id}. "
            "Run /fly connect calendar first."
        )

    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes", SCOPES),
    )

    # Refresh if expired
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed credentials
            updated_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes) if creds.scopes else SCOPES,
            }
            save_credentials(user_id, SERVICE_NAME, updated_data)
            logger.info("Refreshed calendar credentials for user %s", user_id)
        else:
            raise ValueError(
                f"Calendar credentials for user {user_id} are invalid and cannot be refreshed. "
                "Run /fly connect calendar to re-authenticate."
            )

    return build("calendar", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# CalendarWatcher
# ---------------------------------------------------------------------------


class CalendarWatcher(WatcherBase):
    """Watches Google Calendar for upcoming external meetings.

    Polls every 15 minutes for events in the next 60-minute window.
    External meetings (attendees from different domains) auto-trigger
    meeting-prep skill via execute_skill().
    """

    def __init__(self, user_id: str, company_domain: str = None):
        """Initialize CalendarWatcher.

        Args:
            user_id: User identifier.
            company_domain: Company email domain (e.g., 'myco.com').
                If None, all meetings with 2+ attendees are treated as external.
        """
        super().__init__(name="calendar", user_id=user_id)
        self.company_domain = company_domain

    def check(self) -> list:
        """Poll Google Calendar for events in the next 60 minutes.

        Returns:
            List of event dicts that have external attendees.
            Uses event ID for deduplication.
        """
        try:
            service = get_calendar_service(self.user_id)
        except (ValueError, RuntimeError) as e:
            logger.error("Cannot check calendar for user %s: %s", self.user_id, e)
            return []

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(minutes=POLL_WINDOW_MINUTES)

        try:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as e:
            logger.error("Calendar API call failed for user %s: %s", self.user_id, e)
            return []

        events = events_result.get("items", [])

        # Filter to external meetings only
        external_events = []
        for event in events:
            event_id = event.get("id", "")
            if not event_id:
                continue

            # Set id field for WatcherBase deduplication
            event["id"] = event_id

            if self._has_external_attendee(event):
                external_events.append(event)

        return external_events

    def process(self, event) -> dict:
        """Process an external meeting by triggering meeting-prep.

        Args:
            event: Google Calendar event dict.

        Returns:
            Result dict from execute_skill().
        """
        from execution_gateway import execute_skill

        title = event.get("summary", "Untitled Meeting")
        attendees = event.get("attendees", [])
        attendee_list = [
            a.get("email", "unknown") for a in attendees
        ]

        formatted_info = self._format_meeting_info(event)

        result = execute_skill(
            "meeting-prep",
            input_text=formatted_info,
            user_id=self.user_id,
            params={
                "source": "auto-calendar",
                "meeting_title": title,
                "attendees": attendee_list,
            },
        )

        logger.info(
            "Auto-triggered meeting-prep for '%s' (user %s)",
            title,
            self.user_id,
        )

        return {
            "status": "triggered",
            "skill": "meeting-prep",
            "meeting_title": title,
            "attendees": attendee_list,
            "execution_result": result,
        }

    def _has_external_attendee(self, event: dict) -> bool:
        """Check if an event has external attendees.

        Args:
            event: Google Calendar event dict.

        Returns:
            True if the event has at least one attendee from a different
            domain than company_domain. If company_domain is None,
            returns True for events with 2+ attendees.
            Returns False for events with no attendees (focus time, etc.).
        """
        attendees = event.get("attendees", [])

        if not attendees:
            return False

        if self.company_domain is None:
            # No company domain set: treat all multi-attendee meetings as external
            return len(attendees) >= 2

        for attendee in attendees:
            email = attendee.get("email", "")
            if "@" in email:
                domain = email.split("@", 1)[1].lower()
                if domain != self.company_domain.lower():
                    return True

        return False

    def _format_meeting_info(self, event: dict) -> str:
        """Format event details for meeting-prep skill input.

        Args:
            event: Google Calendar event dict.

        Returns:
            Formatted string with meeting title, time, and attendee list.
        """
        title = event.get("summary", "Untitled Meeting")

        # Parse start time
        start = event.get("start", {})
        start_time = start.get("dateTime", start.get("date", "Unknown"))

        # Build attendee list
        attendees = event.get("attendees", [])
        attendee_lines = []
        for a in attendees:
            email = a.get("email", "unknown")
            display_name = a.get("displayName", "")
            if display_name:
                attendee_lines.append(f"  - {display_name} ({email})")
            else:
                attendee_lines.append(f"  - {email}")

        attendee_section = "\n".join(attendee_lines) if attendee_lines else "  (no attendees listed)"

        return (
            f"Meeting: {title}\n"
            f"Time: {start_time}\n"
            f"Attendees:\n{attendee_section}"
        )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_calendar_watcher(
    manager: IntegrationManager,
    user_id: str,
    company_domain: str = None,
) -> bool:
    """Create and register a CalendarWatcher with an IntegrationManager.

    Only registers if the calendar integration is enabled for the user
    and they have saved credentials.

    Args:
        manager: IntegrationManager instance.
        user_id: User identifier.
        company_domain: Company email domain for external detection.

    Returns:
        True if watcher was registered, False if conditions not met.
    """
    if not is_integration_enabled(user_id, "calendar"):
        logger.info(
            "Calendar integration not enabled for user %s, skipping registration",
            user_id,
        )
        return False

    if not has_credentials(user_id, SERVICE_NAME):
        logger.info(
            "No calendar credentials for user %s, skipping registration",
            user_id,
        )
        return False

    watcher = CalendarWatcher(user_id=user_id, company_domain=company_domain)
    manager.register_watcher(watcher, interval_minutes=POLL_INTERVAL_MINUTES)

    logger.info(
        "Registered calendar watcher for user %s (domain=%s, interval=%dmin)",
        user_id,
        company_domain,
        POLL_INTERVAL_MINUTES,
    )
    return True
