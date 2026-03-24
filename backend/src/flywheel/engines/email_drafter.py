"""
email_drafter.py - Email reply draft generation engine.

Standalone async module that takes an Email row + EmailScore row + Integration,
fetches the email body on-demand from Gmail, assembles context from the scorer's
context_refs, injects the user's voice profile into a Sonnet system prompt, and
upserts an EmailDraft row.

This engine is invoked directly from the Gmail sync loop (not via execute_run),
using the same subsidy API key pattern as voice_profile_init and email_scorer.

Functions:
  draft_email(db, tenant_id, email, score, integration, api_key=None) -> dict | None
    Main entry point. Orchestrates the full drafting pipeline.

  _load_voice_profile(db, tenant_id, user_id) -> dict
    Load EmailVoiceProfile for the tenant+user, fall back to DEFAULT_VOICE_STUB.

  _assemble_draft_context(db, tenant_id, context_refs) -> str
    Load up to 5 context entries + 3 entities by UUID from scorer's context_refs.

  _fetch_body_with_fallback(integration, email, creds) -> tuple[str, str | None]
    Fetch full message body from Gmail, fall back to snippet on 401/403.

  _build_draft_prompt(email, body_text, voice_profile, context_block) -> tuple[str, str]
    Build (system_prompt, user_message) for the Sonnet drafting call.

  _upsert_email_draft(db, tenant_id, email_id, draft_body, context_used, fetch_error) -> None
    Insert an EmailDraft row with status=pending and optional visibility delay.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import anthropic
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import (
    ContextEntry,
    ContextEntity,
    Email,
    EmailDraft,
    EmailScore,
    EmailVoiceProfile,
)
from flywheel.services.gmail_read import get_message_body, get_valid_credentials

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SONNET_MODEL = "claude-sonnet-4-6"

logger = logging.getLogger(__name__)

DEFAULT_VOICE_STUB = {
    "tone": "professional and direct",
    "avg_length": 80,
    "sign_off": "Best,",
    "phrases": [],
}

DRAFT_SYSTEM_PROMPT = """\
You are drafting email replies on behalf of a specific person. Your job is to write
a reply that sounds authentically like them — not generic AI prose.

VOICE PROFILE (match this exactly):
- Tone: {tone}
- Typical length: {avg_length} words (stay within 20% of this)
- Sign-off: Always end with "{sign_off}"
- Characteristic phrases to weave in naturally: {phrases_list}

REPLY CONSTRAINTS:
- Address the specific ask or question in the email directly
- Do NOT include a subject line — body only
- Do NOT start with "I hope this email finds you well" or similar filler
- Do NOT use bullet points unless the incoming email used them
- End with the sign-off above and nothing after it

CONTEXT FROM USER'S KNOWLEDGE BASE:
{context_block}

OUTPUT:
Return only the reply body text. No subject, no metadata, no explanation.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_voice_profile(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> dict:
    """Load EmailVoiceProfile for the tenant+user, fall back to DEFAULT_VOICE_STUB.

    Queries email_voice_profiles by tenant_id + user_id. If found, returns a
    dict with tone, avg_length, sign_off, and phrases (capped at 5 items).
    If not found, logs a warning and returns DEFAULT_VOICE_STUB.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID for row-level filtering.
        user_id: User UUID for profile lookup.

    Returns:
        Dict with keys: tone, avg_length, sign_off, phrases.
    """
    result = await db.execute(
        select(EmailVoiceProfile).where(
            EmailVoiceProfile.tenant_id == tenant_id,
            EmailVoiceProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        logger.warning(
            "No voice profile found for user_id=%s tenant_id=%s; using DEFAULT_VOICE_STUB",
            user_id,
            tenant_id,
        )
        return DEFAULT_VOICE_STUB

    return {
        "tone": profile.tone or DEFAULT_VOICE_STUB["tone"],
        "avg_length": profile.avg_length or DEFAULT_VOICE_STUB["avg_length"],
        "sign_off": profile.sign_off or DEFAULT_VOICE_STUB["sign_off"],
        "phrases": (profile.phrases or [])[:5],
    }


async def _assemble_draft_context(
    db: AsyncSession,
    tenant_id: UUID,
    context_refs: list,
) -> str:
    """Load referenced context entries and entities from scorer's context_refs.

    Takes the context_refs list from EmailScore.context_refs (already populated
    by scorer). Extracts entry UUIDs (type="entry") and entity UUIDs (type="entity").
    Loads up to 5 ContextEntry rows and up to 3 ContextEntity rows by UUID.
    No FTS re-run — reuses the scorer's already-identified references.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID for row-level filtering.
        context_refs: List of {type, id, ...} dicts from EmailScore.context_refs.

    Returns:
        Formatted context text block for system prompt injection.
    """
    if not context_refs:
        return "No relevant context available."

    # Extract entry and entity IDs from scorer's context_refs
    entry_ids = []
    entity_ids = []
    for ref in context_refs:
        if not isinstance(ref, dict):
            continue
        ref_type = ref.get("type")
        ref_id = ref.get("id")
        if not ref_id:
            continue
        if ref_type == "entry":
            entry_ids.append(ref_id)
        elif ref_type == "entity":
            entity_ids.append(ref_id)

    lines = []

    # Load context entries (cap at 5)
    if entry_ids:
        result = await db.execute(
            select(ContextEntry).where(
                ContextEntry.id.in_(entry_ids[:5]),
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.deleted_at.is_(None),
            )
        )
        entries = list(result.scalars().all())
        for entry in entries:
            file_name = getattr(entry, "file_name", None) or getattr(
                entry, "source", "unknown"
            )
            date_str = (
                entry.created_at.strftime("%Y-%m-%d")
                if hasattr(entry, "created_at") and entry.created_at
                else "unknown date"
            )
            content_snippet = (entry.content or "")[:300]
            lines.append(
                f'[Meeting note from {file_name}, {date_str}]: "{content_snippet}"'
            )

    # Load context entities (cap at 3)
    if entity_ids:
        result = await db.execute(
            select(ContextEntity).where(
                ContextEntity.id.in_(entity_ids[:3]),
                ContextEntity.tenant_id == tenant_id,
            )
        )
        entities = list(result.scalars().all())
        for entity in entities:
            detail = entity.detail or ""
            aliases = entity.aliases or []
            aliases_str = (
                f"; also known as: {', '.join(aliases[:3])}" if aliases else ""
            )
            summary = (detail[:200] + aliases_str) if detail else aliases_str or ""
            lines.append(
                f"[Entity: {entity.name} ({entity.entity_type}, "
                f"{entity.mention_count} mentions)]: {summary}"
            )

    if not lines:
        return "No relevant context available."

    return "\n".join(lines)


async def _fetch_body_with_fallback(
    integration,
    email: Email,
    creds,
) -> tuple:
    """Fetch email body from Gmail, fall back to snippet on 401/403.

    Calls get_message_body() with the provided credentials. If Gmail returns
    401 or 403, falls back to email.snippet and records a structured error.
    Returns a tuple of (body_text, fetch_error) where fetch_error is None on
    success or a string like "body_fetch_failed:401" on auth error.

    Also checks for empty body: if both body_text and snippet are too short
    (< 20 chars and < 10 chars respectively), returns ("", "body_too_short")
    to signal that drafting should be skipped for this email.

    Args:
        integration: Integration ORM object with provider="gmail-read".
        email: Email ORM instance with gmail_message_id and snippet.
        creds: Valid Google OAuth2 Credentials from get_valid_credentials().

    Returns:
        Tuple of (body_text, fetch_error). fetch_error is None on success.
    """
    try:
        body_text = await get_message_body(creds, email.gmail_message_id)
    except HttpError as exc:
        status = exc.resp.status if hasattr(exc, "resp") and exc.resp else 0
        if status in (401, 403):
            # Fallback: use snippet + structured error
            snippet = email.snippet or ""
            logger.warning(
                "Gmail body fetch returned %s for email_id=%s; falling back to snippet",
                status,
                email.id,
            )
            return (snippet, f"body_fetch_failed:{status}")
        # Re-raise non-auth errors for the caller's error boundary
        raise

    # Check for effectively empty body
    if len(body_text.strip()) < 20 and len((email.snippet or "").strip()) < 10:
        return ("", "body_too_short")

    return (body_text, None)


def _build_draft_prompt(
    email: Email,
    body_text: str,
    voice_profile: dict,
    context_block: str,
) -> tuple:
    """Build (system_prompt, user_message) for the Sonnet drafting call.

    Formats DRAFT_SYSTEM_PROMPT with voice profile fields and the assembled
    context block. Builds user message with From, Subject, and email body.

    Args:
        email: Email ORM instance (sender_email, sender_name, subject used).
        body_text: Full email body text (or snippet on 401/403 fallback).
        voice_profile: Dict with tone, avg_length, sign_off, phrases.
        context_block: Formatted context text from _assemble_draft_context.

    Returns:
        Tuple of (system_prompt_str, user_message_str).
    """
    phrases = voice_profile.get("phrases", [])
    phrases_list = (
        ", ".join(f'"{p}"' for p in phrases) if phrases else "none specified"
    )

    system_prompt = DRAFT_SYSTEM_PROMPT.format(
        tone=voice_profile.get("tone", DEFAULT_VOICE_STUB["tone"]),
        avg_length=voice_profile.get("avg_length", DEFAULT_VOICE_STUB["avg_length"]),
        sign_off=voice_profile.get("sign_off", DEFAULT_VOICE_STUB["sign_off"]),
        phrases_list=phrases_list,
        context_block=context_block,
    )

    sender_line = email.sender_name or ""
    if sender_line:
        sender_line = f"{sender_line} <{email.sender_email}>"
    else:
        sender_line = email.sender_email

    user_message = f"""\
EMAIL TO REPLY TO:
From: {sender_line}
Subject: {email.subject or "(no subject)"}

{body_text}
"""

    return system_prompt, user_message


async def _upsert_email_draft(
    db: AsyncSession,
    tenant_id: UUID,
    email_id: UUID,
    draft_body: str,
    context_used: list,
    fetch_error: "str | None",
) -> None:
    """Insert an EmailDraft row with status=pending.

    Uses simple INSERT (not on_conflict — no unique constraint on email_id
    exists in the migration). The caller already guards against duplicates
    via a LEFT JOIN IS NULL check. Sets visible_after based on
    settings.draft_visibility_delay_days (0 = immediately visible).

    Stores context_used as JSONB list. If fetch_error is not None,
    appends {"fetch_error": fetch_error} to the context_used list.

    Does NOT commit — caller-commits pattern consistent with Phase 2 and 3.

    Args:
        db: Async SQLAlchemy session (caller-owned).
        tenant_id: Tenant UUID.
        email_id: Email UUID (FK to emails.id).
        draft_body: Generated reply text.
        context_used: List of context refs used in draft generation.
        fetch_error: Structured error string if body fetch failed, or None.
    """
    now = datetime.now(timezone.utc)

    # Build full context_used list, appending error if present
    full_context = list(context_used)
    if fetch_error is not None:
        full_context.append({"fetch_error": fetch_error})

    # Compute visibility timestamp
    delay_days = getattr(settings, "draft_visibility_delay_days", 0)
    visible_after = (now + timedelta(days=delay_days)) if delay_days > 0 else None

    stmt = pg_insert(EmailDraft).values(
        tenant_id=tenant_id,
        email_id=email_id,
        draft_body=draft_body,
        status="pending",
        context_used=full_context,
        visible_after=visible_after,
    )
    await db.execute(stmt)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def draft_email(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    score: EmailScore,
    integration,
    api_key: "str | None" = None,
) -> "dict | None":
    """Draft a reply for a single email and insert an EmailDraft row.

    Main entry point for the drafting engine. Orchestrates the full pipeline:
    1. Load EmailVoiceProfile (tenant+user) or DEFAULT_VOICE_STUB for cold-start
    2. Get valid credentials from gmail-read integration
    3. Fetch email body on-demand with 401/403 fallback to snippet
    4. Skip drafting if body is empty (calendar invites, empty messages)
    5. Assemble context from scorer's context_refs (no FTS re-run)
    6. Build draft prompt with voice profile + context injection
    7. Call Claude Sonnet for draft generation (raw text, no JSON parsing)
    8. Truncate if >2000 chars
    9. Insert EmailDraft row (caller commits)
    10. Return dict with draft_body and context_used for caller logging

    On any exception, logs the error (email ID only, no PII) and returns None.
    Failure is non-fatal — the sync loop always continues regardless of draft
    outcome (same pattern as score_email and voice_profile_init).

    Args:
        db: Async SQLAlchemy session. Caller sets RLS context (set_config) and
            commits. This function does not commit.
        tenant_id: Tenant UUID.
        email: Email ORM instance to draft a reply for.
        score: EmailScore ORM instance with context_refs from scoring.
        integration: Integration ORM object with provider="gmail-read".
        api_key: Optional explicit API key. If None, uses
                 settings.flywheel_subsidy_api_key (background job default).

    Returns:
        Dict with keys: draft_body, context_used. Or None on any error.
    """
    try:
        # Step 1: Load voice profile (falls back to DEFAULT_VOICE_STUB)
        voice_profile = await _load_voice_profile(db, tenant_id, email.user_id)

        # Step 2: Get valid credentials from integration
        creds = await get_valid_credentials(integration)

        # Step 3: Fetch body with 401/403 fallback
        body_text, fetch_error = await _fetch_body_with_fallback(
            integration, email, creds
        )

        # Step 4: Skip drafting if body is too short (empty body check)
        if body_text == "" and fetch_error == "body_too_short":
            logger.info(
                "Skipping draft for email_id=%s tenant_id=%s: body_too_short",
                email.id,
                tenant_id,
            )
            return None

        # Step 5: Assemble context from scorer's context_refs
        context_refs = score.context_refs or []
        context_block = await _assemble_draft_context(db, tenant_id, context_refs)

        # Step 6: Build prompt
        system_prompt, user_message = _build_draft_prompt(
            email, body_text, voice_profile, context_block
        )

        # Step 7: Call Sonnet for draft generation
        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)
        response = await client.messages.create(
            model=_SONNET_MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        # Step 8: Extract response text — raw text, no JSON parsing needed
        draft_body = response.content[0].text.strip()

        # Truncate if unexpectedly long
        if len(draft_body) > 2000:
            logger.warning(
                "Draft truncated for email_id=%s: length=%d > 2000",
                email.id,
                len(draft_body),
            )
            draft_body = draft_body[:2000]

        # Step 9: Insert EmailDraft row (caller commits)
        await _upsert_email_draft(
            db,
            tenant_id,
            email.id,
            draft_body,
            context_refs,
            fetch_error,
        )

        # Step 10: Return for caller logging
        logger.info(
            "Drafted reply for email_id=%s tenant_id=%s",
            email.id,
            tenant_id,
        )
        return {"draft_body": draft_body, "context_used": context_refs}

    except Exception as exc:
        # Non-fatal: log email ID only (no PII — no subject/sender/body in log)
        logger.error(
            "draft_email failed for email_id=%s tenant_id=%s: %s: %s",
            email.id,
            tenant_id,
            type(exc).__name__,
            exc,
        )
        return None
