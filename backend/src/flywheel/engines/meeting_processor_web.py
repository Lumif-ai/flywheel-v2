"""Meeting processor web engine — async helpers for the meeting intelligence pipeline.

This module provides the 4 core async helpers used by skill_executor's
_execute_meeting_processor() 7-stage pipeline:

- classify_meeting()  — 3-layer classification returning one of 8 meeting types
- extract_intelligence() — Sonnet extraction into 7 MPP-04 context file types
- upload_transcript()  — Upload transcript text to Supabase Storage
- write_context_entries() — Write extracted intelligence to ContextEntry rows

Important: this is the WEB implementation (async, ORM-based).
Do NOT import from engines/meeting_processor.py (CLI, sync, storage_backend).
The two implementations coexist permanently.

CONTEXT_FILE_MAP keys align exactly with MPP-04 spec:
    competitive-intel, pain-points, icp-profiles, contacts,
    insights, action-items, product-feedback
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from flywheel.db.models import Account, AccountContact, ContextEntry, Tenant

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_SONNET_MODEL = "claude-sonnet-4-20250514"

# 8 recognized meeting types (returned by classify_meeting)
MEETING_TYPES = frozenset({
    "discovery",
    "expert",
    "prospect",
    "advisor",
    "investor-pitch",
    "internal",
    "customer-feedback",
    "team-meeting",
})

# Maps extracted intelligence keys → ContextEntry file_names (MPP-04 aligned)
CONTEXT_FILE_MAP: dict[str, str] = {
    "competitive_intel": "competitive-intel",
    "pain_points": "pain-points",
    "icp_profiles": "icp-profiles",
    "contacts": "contacts",
    "insights": "insights",
    "action_items": "action-items",
    "product_feedback": "product-feedback",
}

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are a meeting intelligence extraction engine. Given a meeting transcript and metadata,
extract structured intelligence into exactly the 7 categories below.

Respond ONLY with a valid JSON object using these exact keys:
- competitive_intel: list of {competitor, mention, pricing_signal, switching_signal, speaker}
- pain_points: list of {problem, severity (low/medium/high), speaker, classification (painkiller/vitamin)}
- icp_profiles: list of {segment, buying_signal, decision_maker_info, budget_signal, champion_indicator}
- contacts: list of {name, title, company, role, notes}
- insights: list of {takeaway, type (strategic/tactical/pattern), quote, next_step}
- action_items: list of {action, owner, due_date, type (internal/external)}
- product_feedback: list of {feedback_type (feature_request/reaction/demo_feedback), description, sentiment}
- tldr: string — 2–3 sentence meeting summary
- key_decisions: list of strings — key decisions made in the meeting

Use empty lists for categories with no data. Do not include any prose outside the JSON object.
"""

EXTRACTION_USER_PROMPT = """\
Meeting type: {meeting_type}

Transcript:
{transcript}

AI summary from provider (if available):
{ai_summary}

Existing account context (if available):
{existing_context}

Extract intelligence from this meeting.
"""


# ---------------------------------------------------------------------------
# 3-Layer Meeting Classification
# ---------------------------------------------------------------------------


async def classify_meeting(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    title: str,
    attendees: list[dict],
    transcript: str,
    ai_summary: str | None = None,
    api_key: str | None = None,
) -> str:
    """Classify a meeting into one of 8 types using 3-layer detection.

    Layer 1: Contact match — query AccountContact for attendee emails.
              If found, derive type from parent account's relationship_type.
    Layer 2: Internal check — if all attendees share tenant domain, classify
              as "internal" (<=3 attendees) or "team-meeting" (>3 attendees).
              Skipped if tenant.domain is NULL.
    Layer 3: Haiku LLM call — use title + attendees + first 500 chars of
              transcript to classify meeting type.

    Returns one of the 8 MEETING_TYPES values.
    """
    attendee_emails = [
        a.get("email", "").lower()
        for a in (attendees or [])
        if a.get("email")
    ]

    # -----------------------------------------------------------------------
    # Layer 1: Account contact match
    # -----------------------------------------------------------------------
    if attendee_emails:
        try:
            async with factory() as session:
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
                rows = (await session.execute(
                    select(AccountContact, Account)
                    .join(Account, AccountContact.account_id == Account.id)
                    .where(
                        AccountContact.tenant_id == tenant_id,
                        AccountContact.email.in_(attendee_emails),
                    )
                    .limit(1)
                )).first()

            if rows is not None:
                contact, account = rows
                rel_types = account.relationship_type or []
                # Map relationship_type array to meeting type
                for rel in rel_types:
                    rel_lower = rel.lower()
                    if rel_lower == "advisor":
                        return "advisor"
                    elif rel_lower in ("investor", "investor-pitch"):
                        return "investor-pitch"
                    elif rel_lower in ("prospect", "pipeline"):
                        return "prospect"
                    elif rel_lower == "customer":
                        return "customer-feedback"
                    elif rel_lower == "expert":
                        return "expert"
                # Fallback from relationship type — use discovery if we matched a contact
                return "discovery"
        except Exception as exc:
            logger.warning("classify_meeting Layer 1 failed: %s", exc)

    # -----------------------------------------------------------------------
    # Layer 2: Internal domain check
    # -----------------------------------------------------------------------
    if attendee_emails:
        try:
            async with factory() as session:
                # NOTE: tenants is NOT tenant-scoped, no RLS needed
                tenant_row = (await session.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )).scalar_one_or_none()

            if tenant_row and tenant_row.domain:
                tenant_domain = tenant_row.domain.lower().lstrip("@")
                all_internal = all(
                    email.endswith(f"@{tenant_domain}")
                    for email in attendee_emails
                    if email
                )
                if all_internal:
                    return "team-meeting" if len(attendee_emails) > 3 else "internal"
            elif tenant_row and not tenant_row.domain:
                logger.debug(
                    "classify_meeting Layer 2 skipped: tenant %s has NULL domain", tenant_id
                )
        except Exception as exc:
            logger.warning("classify_meeting Layer 2 failed: %s", exc)

    # -----------------------------------------------------------------------
    # Layer 3: Haiku LLM classification
    # -----------------------------------------------------------------------
    try:
        attendees_str = ", ".join(
            a.get("name") or a.get("email") or "Unknown"
            for a in (attendees or [])
        )
        transcript_preview = (transcript or "")[:500]

        prompt = (
            f"Meeting title: {title}\n"
            f"Attendees: {attendees_str}\n"
            f"Transcript preview: {transcript_preview}\n\n"
            "Classify this meeting. Respond with EXACTLY one of these codes:\n"
            "discovery, expert, prospect, advisor, investor-pitch, internal, "
            "customer-feedback, team-meeting\n"
            "Return only the code, nothing else."
        )

        def _call_haiku() -> str:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            msg = client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip().lower()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _call_haiku)

        if result in MEETING_TYPES:
            return result

        # Fuzzy match in case the model returned something close
        for mtype in MEETING_TYPES:
            if mtype in result:
                return mtype

        logger.warning("classify_meeting Layer 3 returned unexpected value: %r", result)
    except Exception as exc:
        logger.warning("classify_meeting Layer 3 failed: %s", exc)

    # Default fallback
    return "discovery"


# ---------------------------------------------------------------------------
# Sonnet Intelligence Extraction
# ---------------------------------------------------------------------------


async def extract_intelligence(
    transcript: str,
    ai_summary: str | None,
    meeting_type: str,
    existing_context_str: str = "",
    api_key: str | None = None,
) -> dict:
    """Extract structured intelligence from a meeting transcript using Sonnet.

    Extracts 7 MPP-04 context file categories plus tldr and key_decisions
    as top-level summary fields.

    Returns a dict with all keys (empty lists/strings for missing data):
    - competitive_intel, pain_points, icp_profiles, contacts, insights,
      action_items, product_feedback  (map to CONTEXT_FILE_MAP)
    - tldr, key_decisions  (summary-only, NOT written as context entries)
    """
    user_prompt = EXTRACTION_USER_PROMPT.format(
        meeting_type=meeting_type,
        transcript=(transcript or "")[:12000],  # Avoid context window overflow
        ai_summary=ai_summary or "(none)",
        existing_context=existing_context_str or "(none)",
    )

    def _call_sonnet() -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        msg = client.messages.create(
            model=_SONNET_MODEL,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("extract_intelligence: JSON parse error: %s — raw: %.200s", e, raw)
            return {}

    loop = asyncio.get_event_loop()
    extracted = await loop.run_in_executor(None, _call_sonnet)

    # Ensure all expected keys exist with empty defaults
    defaults: dict = {
        "competitive_intel": [],
        "pain_points": [],
        "icp_profiles": [],
        "contacts": [],
        "insights": [],
        "action_items": [],
        "product_feedback": [],
        "tldr": "",
        "key_decisions": [],
    }
    for key, default in defaults.items():
        extracted.setdefault(key, default)

    return extracted


# ---------------------------------------------------------------------------
# Supabase Storage Upload
# ---------------------------------------------------------------------------


async def upload_transcript(
    tenant_id: UUID,
    meeting_id: UUID,
    transcript_text: str,
) -> str:
    """Upload a meeting transcript to Supabase Storage.

    Stores at: uploads/transcripts/{tenant_id}/{meeting_id}.txt
    Returns the storage path string.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    storage_path = f"transcripts/{tenant_id}/{meeting_id}.txt"
    upload_url = f"{supabase_url}/storage/v1/object/uploads/{storage_path}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "text/plain",
            },
            content=transcript_text.encode("utf-8"),
        )
        # 200 = created, 409 = already exists (upsert on conflict)
        if resp.status_code not in (200, 201, 409):
            logger.warning(
                "upload_transcript: unexpected status %s for %s",
                resp.status_code, storage_path,
            )

    return storage_path


# ---------------------------------------------------------------------------
# Context Entry Writer
# ---------------------------------------------------------------------------


def _make_meeting_slug(meeting_date: date | datetime, title: str) -> str:
    """Generate a stable slug for a meeting context entry detail field.

    Format: meeting-{YYYY-MM-DD}-{title_slug}
    title_slug = first 20 chars of title, lowercased, non-alphanumeric → hyphens.
    """
    if isinstance(meeting_date, datetime):
        date_str = meeting_date.date().isoformat()
    else:
        date_str = meeting_date.isoformat()

    title_slug = re.sub(r"[^a-z0-9]+", "-", (title or "untitled")[:20].lower()).strip("-")
    return f"meeting-{date_str}-{title_slug}"


async def write_context_entries(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    user_id: UUID,
    account_id: UUID | None,
    meeting_date: date | datetime,
    meeting_slug: str,
    extracted: dict,
) -> int:
    """Write extracted meeting intelligence to ContextEntry rows.

    - Maps extracted keys to ContextEntry file_names via CONTEXT_FILE_MAP.
    - Skips tldr and key_decisions (summary-only, not written as entries).
    - Deduplicates: skips if a row with (file_name, source, detail, tenant_id)
      already exists.
    - Sets RLS context (app.tenant_id and app.user_id) before writes.
    - Returns the count of new entries written.

    account_id may be None — set directly on ORM object when provided.
    """
    if isinstance(meeting_date, datetime):
        entry_date = meeting_date.date()
    else:
        entry_date = meeting_date

    written = 0

    async with factory() as session:
        # Set RLS context
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            sa_text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        for extract_key, file_name in CONTEXT_FILE_MAP.items():
            value = extracted.get(extract_key)
            if not value:
                continue  # Skip empty / falsy values

            # Serialize list/dict values to JSON string for content field
            if isinstance(value, (list, dict)):
                if not value:
                    continue
                content_str = json.dumps(value, indent=2)
            else:
                content_str = str(value)

            # Dedup check: (file_name, source, detail, tenant_id)
            existing = (await session.execute(
                select(ContextEntry.id).where(
                    ContextEntry.file_name == file_name,
                    ContextEntry.source == "ctx-meeting-processor",
                    ContextEntry.detail == meeting_slug,
                    ContextEntry.tenant_id == tenant_id,
                ).limit(1)
            )).scalar_one_or_none()

            if existing is not None:
                logger.debug(
                    "write_context_entries: skipping duplicate %s/%s for %s",
                    file_name, meeting_slug, tenant_id,
                )
                continue

            entry = ContextEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                file_name=file_name,
                source="ctx-meeting-processor",
                detail=meeting_slug,
                confidence="medium",
                date=entry_date,
                content=content_str,
            )
            if account_id is not None:
                entry.account_id = account_id

            session.add(entry)
            written += 1

        await session.commit()

    logger.info(
        "write_context_entries: wrote %d new entries for meeting %s (tenant=%s)",
        written, meeting_slug, tenant_id,
    )
    return written
