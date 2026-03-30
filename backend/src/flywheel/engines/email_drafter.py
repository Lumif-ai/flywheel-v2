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
    Integration,
)
from flywheel.engines.model_config import get_engine_model
from flywheel.services.gmail_read import get_message_body, get_valid_credentials

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

DEFAULT_VOICE_STUB = {
    "tone": "professional and direct",
    "avg_length": 80,
    "sign_off": "Best,",
    "phrases": [],
    "formality_level": "conversational",
    "greeting_style": "Hi {name},",
    "question_style": "direct",
    "paragraph_pattern": "short single-line",
    "emoji_usage": "never",
    "avg_sentences": 3,
}

QUICK_ACTION_OVERRIDES = {
    "shorter": {"avg_length": 40, "avg_sentences": 2, "paragraph_pattern": "short single-line responses"},
    "longer": {"avg_length": 150, "avg_sentences": 6, "paragraph_pattern": "2-3 sentence paragraph blocks"},
    "more_casual": {"formality_level": "casual", "tone": "friendly and relaxed", "emoji_usage": "occasional"},
    "more_formal": {"formality_level": "formal", "tone": "professional and polished", "emoji_usage": "never"},
}

VOICE_SNAPSHOT_FIELDS = [
    "tone", "avg_length", "sign_off", "phrases", "formality_level",
    "greeting_style", "question_style", "paragraph_pattern", "emoji_usage", "avg_sentences",
]

DRAFT_SYSTEM_PROMPT = """\
You are drafting email replies on behalf of a specific person. Your job is to write
a reply that sounds authentically like them -- not generic AI prose.

VOICE PROFILE (match this exactly):
- Tone: {tone}
- Formality: {formality_level}
- Greeting style: {greeting_style}
- Typical length: {avg_length} words, ~{avg_sentences} sentences
- Paragraph style: {paragraph_pattern}
- Question style: {question_style}
- Emoji usage: {emoji_usage}
- Sign-off: Always end with "{sign_off}"
- Characteristic phrases to weave in naturally: {phrases_list}

REPLY CONSTRAINTS:
- Address the specific ask or question in the email directly
- Do NOT include a subject line -- body only
- Do NOT start with "I hope this email finds you well" or similar filler
- Do NOT use bullet points unless the incoming email used them
- Match the greeting style above for the opening
- Match the formality level -- casual means contractions, informal language
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
        Dict with keys: tone, avg_length, sign_off, phrases, formality_level,
        greeting_style, question_style, paragraph_pattern, emoji_usage, avg_sentences.
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
        "formality_level": profile.formality_level or DEFAULT_VOICE_STUB["formality_level"],
        "greeting_style": profile.greeting_style or DEFAULT_VOICE_STUB["greeting_style"],
        "question_style": profile.question_style or DEFAULT_VOICE_STUB["question_style"],
        "paragraph_pattern": profile.paragraph_pattern or DEFAULT_VOICE_STUB["paragraph_pattern"],
        "emoji_usage": profile.emoji_usage or DEFAULT_VOICE_STUB["emoji_usage"],
        "avg_sentences": profile.avg_sentences or DEFAULT_VOICE_STUB["avg_sentences"],
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
        voice_profile: Dict with tone, avg_length, sign_off, phrases, formality_level,
            greeting_style, question_style, paragraph_pattern, emoji_usage, avg_sentences.
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
        formality_level=voice_profile.get("formality_level", DEFAULT_VOICE_STUB["formality_level"]),
        greeting_style=voice_profile.get("greeting_style", DEFAULT_VOICE_STUB["greeting_style"]),
        question_style=voice_profile.get("question_style", DEFAULT_VOICE_STUB["question_style"]),
        paragraph_pattern=voice_profile.get("paragraph_pattern", DEFAULT_VOICE_STUB["paragraph_pattern"]),
        emoji_usage=voice_profile.get("emoji_usage", DEFAULT_VOICE_STUB["emoji_usage"]),
        avg_sentences=voice_profile.get("avg_sentences", DEFAULT_VOICE_STUB["avg_sentences"]),
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


async def _generate_draft_body(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    voice_profile_dict: dict,
    context_refs: list,
    integration=None,
    creds=None,
    body_text: "str | None" = None,
    custom_instructions: "str | None" = None,
    api_key: "str | None" = None,
) -> tuple:
    """Generate a draft body using Claude with the given voice profile dict.

    This is the core drafting logic extracted for reuse by both draft_email()
    and regenerate_draft_with_overrides(). Accepts a voice profile as a plain
    dict (not ORM object) so overrides can be merged before calling.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID.
        email: Email ORM instance to draft a reply for.
        voice_profile_dict: Dict with all 10 voice profile fields.
        context_refs: List of context ref dicts from EmailScore.
        integration: Integration ORM object (needed if body_text not provided).
        creds: Google credentials (needed if body_text not provided).
        body_text: Pre-fetched email body. If None, fetches via Gmail.
        custom_instructions: Optional free-form instruction to append.
        api_key: Optional explicit API key for Claude call.

    Returns:
        Tuple of (draft_body_str, fetch_error_or_None).
    """
    fetch_error = None

    # Fetch body if not provided
    if body_text is None:
        if creds is None and integration is not None:
            creds = await get_valid_credentials(integration)
        body_text, fetch_error = await _fetch_body_with_fallback(
            integration, email, creds
        )
        if body_text == "" and fetch_error == "body_too_short":
            return ("", "body_too_short")

    # Assemble context
    context_block = await _assemble_draft_context(db, tenant_id, context_refs)

    # Build prompt
    system_prompt, user_message = _build_draft_prompt(
        email, body_text, voice_profile_dict, context_block
    )

    # Append custom instructions if provided
    if custom_instructions:
        system_prompt += f"\n\nAdditional instructions for this draft: {custom_instructions}"

    # Call Claude
    model = await get_engine_model(db, tenant_id, "drafting")
    effective_api_key = api_key or settings.flywheel_subsidy_api_key
    client = anthropic.AsyncAnthropic(api_key=effective_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    draft_body = response.content[0].text.strip()

    # Truncate if unexpectedly long
    if len(draft_body) > 2000:
        logger.warning(
            "Draft truncated for email_id=%s: length=%d > 2000",
            email.id,
            len(draft_body),
        )
        draft_body = draft_body[:2000]

    return (draft_body, fetch_error)


def _build_voice_snapshot(voice_profile_dict: dict) -> dict:
    """Build a voice_snapshot context entry from a voice profile dict."""
    snapshot = {"type": "voice_snapshot"}
    for field in VOICE_SNAPSHOT_FIELDS:
        snapshot[field] = voice_profile_dict.get(field)
    return snapshot


async def regenerate_draft_with_overrides(
    db: AsyncSession,
    tenant_id: UUID,
    draft_id: UUID,
    overrides: "dict | None" = None,
    custom_instructions: "str | None" = None,
) -> EmailDraft:
    """Regenerate a draft with one-time voice overrides.

    Loads the existing draft, verifies it is pending, merges voice overrides
    into the current voice profile, re-generates the body via Claude, and
    updates the draft row. The persistent EmailVoiceProfile is never modified.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID.
        draft_id: EmailDraft UUID.
        overrides: Dict of voice profile field overrides to merge.
        custom_instructions: Free-form instruction for the LLM.

    Returns:
        Updated EmailDraft ORM instance.

    Raises:
        ValueError: If draft status is not "pending".
        LookupError: If draft not found for this tenant.
    """
    # 1. Load draft with tenant check
    result = await db.execute(
        select(EmailDraft).where(
            EmailDraft.id == draft_id,
            EmailDraft.tenant_id == tenant_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise LookupError(f"Draft {draft_id} not found for tenant {tenant_id}")

    # 2. Verify status is pending
    if draft.status != "pending":
        raise ValueError(f"Cannot regenerate a {draft.status} draft")

    # 3. Load parent email
    email_result = await db.execute(
        select(Email).where(Email.id == draft.email_id)
    )
    email = email_result.scalar_one_or_none()
    if email is None:
        raise LookupError(f"Parent email {draft.email_id} not found")

    # 4. Load current voice profile
    voice_profile = await _load_voice_profile(db, tenant_id, email.user_id)

    # 5. Merge overrides into voice dict
    merged_voice = dict(voice_profile)
    if overrides:
        merged_voice.update(overrides)

    # 6. Get context_refs from EmailScore
    score_result = await db.execute(
        select(EmailScore).where(EmailScore.email_id == email.id)
    )
    score = score_result.scalar_one_or_none()
    context_refs = (score.context_refs or []) if score else []

    # Load integration for body fetching
    intg_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.provider == "gmail-read",
            Integration.status == "connected",
        )
    )
    integration = intg_result.scalars().first()

    # 7. Generate new draft body
    draft_body, _ = await _generate_draft_body(
        db, tenant_id, email, merged_voice, context_refs,
        integration=integration,
        custom_instructions=custom_instructions,
    )

    # 8. Update draft row
    new_snapshot = _build_voice_snapshot(merged_voice)

    # Rebuild context_used: keep non-snapshot entries, replace snapshot
    old_context = draft.context_used or []
    new_context = [entry for entry in old_context if not (isinstance(entry, dict) and entry.get("type") == "voice_snapshot")]
    new_context.append(new_snapshot)

    draft.draft_body = draft_body
    draft.user_edits = None
    draft.context_used = new_context
    draft.updated_at = datetime.now(timezone.utc)

    return draft


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

        # Step 3-8: Generate draft body using extracted helper
        context_refs = score.context_refs or []
        draft_body, fetch_error = await _generate_draft_body(
            db, tenant_id, email, voice_profile, context_refs,
            integration=integration, creds=creds, api_key=api_key,
        )

        # Skip drafting if body is too short (empty body check)
        if draft_body == "" and fetch_error == "body_too_short":
            logger.info(
                "Skipping draft for email_id=%s tenant_id=%s: body_too_short",
                email.id,
                tenant_id,
            )
            return None

        # Step 9: Build context_used with voice snapshot
        voice_snapshot = _build_voice_snapshot(voice_profile)
        context_used = list(context_refs) + [voice_snapshot]

        # Step 10: Insert EmailDraft row (caller commits)
        await _upsert_email_draft(
            db,
            tenant_id,
            email.id,
            draft_body,
            context_used,
            fetch_error,
        )

        # Step 11: Return for caller logging
        logger.info(
            "Drafted reply for email_id=%s tenant_id=%s",
            email.id,
            tenant_id,
        )
        return {"draft_body": draft_body, "context_used": context_used}

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
