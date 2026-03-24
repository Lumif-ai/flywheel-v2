"""email_voice_updater.py — Incremental voice profile update from draft edits.

Called as a background task from the approve_draft endpoint. Computes a diff
between the AI-generated draft body and the user's edited version, sends it to
Haiku for analysis, and merges the returned changes into the existing voice profile.

Functions:
  _compute_diff_summary(original, edited) -> str
    Produces a capped (50-line) unified diff summary. Returns
    "No changes detected." if texts are identical.

  update_from_edit(db, tenant_id, user_id, original_body, edited_body) -> bool
    Main entry point: loads profile, calls Haiku, merges updates, persists.
    Returns True on success, False on no-op or any error.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import EmailVoiceProfile

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_UPDATE_VOICE_SYSTEM = """\
You are updating a writing voice profile based on how a user edited an AI-generated email draft.
Analyze the diff and return ONLY the fields that should change, as a JSON object.
Omit unchanged fields entirely.

Allowed return fields:
- "tone": string (e.g. "professional", "casual", "warm")
- "avg_length": integer (estimated word count of preferred email body)
- "sign_off": string (e.g. "Thanks,", "Best,")
- "phrases_to_add": list of strings (phrases the user prefers)
- "phrases_to_remove": list of strings (phrases the user removed or replaced)

Only include a field if the edits clearly demonstrate a preference change.
If the edits are trivial (whitespace, punctuation only), return an empty JSON object: {}

Return ONLY a JSON object. No markdown fencing. No explanation.
"""


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def _compute_diff_summary(original: str, edited: str) -> str:
    """Produce a human-readable unified diff summary capped at 50 lines.

    Args:
        original: AI-generated draft body.
        edited: User's edited version.

    Returns:
        Unified diff string, or "No changes detected." if texts are identical.
    """
    if original == edited:
        return "No changes detected."

    original_lines = original.splitlines(keepends=True)
    edited_lines = edited.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            original_lines,
            edited_lines,
            fromfile="original",
            tofile="edited",
            lineterm="",
        )
    )
    if not diff:
        return "No changes detected."

    # Cap at 50 lines to control token usage
    return "\n".join(diff[:50])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def update_from_edit(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    original_body: str,
    edited_body: str,
) -> bool:
    """Incrementally update the voice profile from a single draft edit.

    Loads the existing EmailVoiceProfile for (tenant_id, user_id), computes the
    diff between original_body and edited_body, calls Haiku to interpret what
    changed, merges the returned fields into the profile, and persists the update.

    Fails gracefully: any exception logs tenant_id and user_id only (no PII)
    and returns False. Approve endpoint already succeeded — this is non-fatal.

    Args:
        db: AsyncSession with RLS context already set (caller-owned).
        tenant_id: Tenant UUID.
        user_id: User UUID.
        original_body: AI-generated draft_body (captured before null).
        edited_body: User's user_edits string (captured before null).

    Returns:
        True if profile was updated, False on no-op or error.
    """
    try:
        # Load existing profile — must exist (no upsert; profile created at sync time)
        result = await db.execute(
            select(EmailVoiceProfile).where(
                EmailVoiceProfile.tenant_id == tenant_id,
                EmailVoiceProfile.user_id == user_id,
            )
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            logger.warning(
                "voice_update: no profile found for tenant_id=%s user_id=%s — skipping",
                tenant_id,
                user_id,
            )
            return False

        # Compute diff
        diff_summary = _compute_diff_summary(original_body, edited_body)
        if diff_summary == "No changes detected.":
            logger.debug(
                "voice_update: no diff for tenant_id=%s user_id=%s — skipping",
                tenant_id,
                user_id,
            )
            return False

        # Build current profile JSON for context
        current_profile_json = json.dumps(
            {
                "tone": profile.tone,
                "avg_length": profile.avg_length,
                "sign_off": profile.sign_off,
                "phrases": profile.phrases or [],
            },
            indent=2,
        )

        # Build Haiku prompt
        user_message = f"""\
CURRENT VOICE PROFILE:
{current_profile_json}

AI-GENERATED DRAFT (original):
{original_body}

USER'S EDITED VERSION (what they actually sent):
{edited_body}

DIFF SUMMARY:
{diff_summary}

Analyze what the edits reveal about the user's actual voice preferences.
Return ONLY the fields that should change as a JSON object.
"""

        # Call Haiku
        client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
        response = await client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=300,
            system=_UPDATE_VOICE_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()

        # Parse JSON response — with regex fallback (same pattern as email_scorer)
        try:
            updates = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                updates = json.loads(match.group())
            else:
                logger.warning(
                    "voice_update: could not parse Haiku response for tenant_id=%s user_id=%s",
                    tenant_id,
                    user_id,
                )
                return False

        # Empty response means Haiku found no meaningful changes
        if not updates:
            logger.debug(
                "voice_update: Haiku returned no changes for tenant_id=%s user_id=%s",
                tenant_id,
                user_id,
            )
            return False

        # Merge updates into profile
        new_tone = updates.get("tone", profile.tone)

        new_sign_off = updates.get("sign_off", profile.sign_off)

        # avg_length: running average (new observation weighted equally)
        current_samples = profile.samples_analyzed or 0
        if "avg_length" in updates and isinstance(updates["avg_length"], (int, float)):
            new_avg = updates["avg_length"]
            if profile.avg_length is not None and current_samples > 0:
                new_avg_length = int(
                    (profile.avg_length * current_samples + new_avg)
                    / (current_samples + 1)
                )
            else:
                new_avg_length = int(new_avg)
        else:
            new_avg_length = profile.avg_length

        # phrases: add new, remove deleted, cap at 10, deduplicate (case-insensitive)
        existing_phrases: list[str] = list(profile.phrases or [])
        phrases_to_add: list[str] = updates.get("phrases_to_add", [])
        phrases_to_remove: list[str] = updates.get("phrases_to_remove", [])

        # Build lowercased set for dedup and removal checks
        remove_lower = {p.lower() for p in phrases_to_remove}
        filtered = [p for p in existing_phrases if p.lower() not in remove_lower]

        # Add new phrases, deduplicating case-insensitively
        existing_lower = {p.lower() for p in filtered}
        for phrase in phrases_to_add:
            if phrase.lower() not in existing_lower:
                filtered.append(phrase)
                existing_lower.add(phrase.lower())

        # Cap at 10
        new_phrases = filtered[:10]

        new_samples = current_samples + 1

        # Persist update (UPDATE only — row must exist)
        await db.execute(
            update(EmailVoiceProfile)
            .where(
                EmailVoiceProfile.tenant_id == tenant_id,
                EmailVoiceProfile.user_id == user_id,
            )
            .values(
                tone=new_tone,
                avg_length=new_avg_length,
                sign_off=new_sign_off,
                phrases=new_phrases,
                samples_analyzed=new_samples,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

        logger.info(
            "voice_update: profile updated for tenant_id=%s user_id=%s samples=%d",
            tenant_id,
            user_id,
            new_samples,
        )
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "voice_update: failed for tenant_id=%s user_id=%s: %s: %s",
            tenant_id,
            user_id,
            type(exc).__name__,
            exc,
        )
        return False
