"""SynthesisEngine: AI synthesis service for relationship summaries and Q&A.

Public API:
    SynthesisEngine.enforce_rate_limit(entry) -> None  # raises 429 if within window
    SynthesisEngine.generate(db, entry) -> str | None
    SynthesisEngine.ask(db, entry, question) -> dict

Rate-limit contract:
    Synthesis is rate-limited to once per 5 minutes via DB-level ai_summary_updated_at.
    enforce_rate_limit() MUST be called BEFORE generate() — even when ai_summary is NULL.

Sparse-data contract:
    generate() and ask() both guard against fewer than _MIN_CONTEXT_ENTRIES entries.
    For generate(): returns None, but still updates ai_summary_updated_at so the rate
    limit applies on subsequent calls.
    For ask(): returns a graceful "not enough context" response without calling LLM.

Source attribution contract:
    ask() instructs the LLM to embed [source:{UUID}] markers in the response.
    These are parsed out and returned as structured `sources` list.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import ContextEntry, PipelineEntry
from flywheel.services.circuit_breaker import anthropic_breaker

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_RATE_LIMIT_WINDOW = timedelta(minutes=5)
_MIN_CONTEXT_ENTRIES = 3


# ---------------------------------------------------------------------------
# SynthesisEngine
# ---------------------------------------------------------------------------


class SynthesisEngine:
    """Stateless service for AI synthesis and Q&A on pipeline entries.

    All methods are async static — pass db session and entry explicitly.
    """

    @staticmethod
    async def enforce_rate_limit(entry: PipelineEntry) -> None:
        """Raise HTTP 429 if synthesis was triggered within the rate-limit window.

        Args:
            entry: The PipelineEntry ORM object (must have ai_summary_updated_at).

        Raises:
            HTTPException: 429 if within 5-minute rate-limit window.
        """
        if entry.ai_summary_updated_at is None:
            # Never synthesized — allow unconditionally
            return

        window_start = datetime.now(timezone.utc) - _RATE_LIMIT_WINDOW

        # Ensure ai_summary_updated_at is timezone-aware for comparison
        last_updated = entry.ai_summary_updated_at
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        if last_updated > window_start:
            retry_after_seconds = (
                last_updated + _RATE_LIMIT_WINDOW - datetime.now(timezone.utc)
            ).total_seconds()
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "SynthesisRateLimitExceeded",
                    "message": "AI synthesis is rate-limited to once per 5 minutes.",
                    "code": 429,
                },
                headers={"Retry-After": str(max(int(retry_after_seconds), 1))},
            )

    @staticmethod
    async def generate(db: AsyncSession, entry: PipelineEntry) -> str | None:
        """Generate an AI summary for a pipeline entry.

        Fetches up to 20 recent context entries and calls Haiku.
        Returns None (and still updates ai_summary_updated_at) if fewer than
        _MIN_CONTEXT_ENTRIES entries exist — graceful sparse-data degradation.

        Args:
            db: Async database session.
            entry: The PipelineEntry ORM object to synthesize.

        Returns:
            Generated summary string, or None for sparse data.

        Raises:
            HTTPException: 503 if circuit breaker is open.
        """
        # Fetch up to 20 most recent context entries
        result = await db.execute(
            select(ContextEntry)
            .where(
                ContextEntry.pipeline_entry_id == entry.id,
                ContextEntry.deleted_at.is_(None),
            )
            .order_by(ContextEntry.date.desc())
            .limit(20)
        )
        entries = result.scalars().all()

        now = datetime.now(timezone.utc)

        # Sparse-data guard: update timestamp so rate limit applies, return None
        if len(entries) < _MIN_CONTEXT_ENTRIES:
            entry.ai_summary = None
            entry.ai_summary_updated_at = now
            return None

        # Build system prompt
        system_prompt = (
            "You are an AI assistant summarizing a business relationship. "
            "Provide a concise 2-3 paragraph summary covering: relationship history, "
            "key interactions, current status, and recommended next steps."
        )

        # Build user content from context entries
        entry_lines = []
        for ctx in entries:
            entry_lines.append(
                f"[{ctx.date}] [{ctx.source}] {ctx.content}"
            )
        user_content = "\n\n".join(entry_lines)

        # Call LLM via circuit breaker
        if not anthropic_breaker.can_execute():
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable",
            )

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
            response = await client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            anthropic_breaker.record_success()
            summary = response.content[0].text.strip()
        except Exception:
            anthropic_breaker.record_failure()
            raise

        # Persist results
        entry.ai_summary = summary
        entry.ai_summary_updated_at = now
        entry.updated_at = now

        return summary

    @staticmethod
    async def ask(db: AsyncSession, entry: PipelineEntry, question: str) -> dict:
        """Answer a question about a relationship using context entries.

        Uses all non-deleted context entries (up to 50). Returns a graceful
        "not enough context" response without calling LLM when fewer than
        _MIN_CONTEXT_ENTRIES entries exist.

        Source attribution: LLM is instructed to embed [source:{UUID}] markers.
        These are parsed out and returned as a structured `sources` list.

        Args:
            db: Async database session.
            entry: The PipelineEntry ORM object.
            question: The question to answer (5-1000 characters).

        Returns:
            Dict with keys: answer (str), sources (list[dict]), insufficient_context (bool).

        Raises:
            HTTPException: 503 if circuit breaker is open.
        """
        # Fetch up to 50 non-deleted context entries
        result = await db.execute(
            select(ContextEntry)
            .where(
                ContextEntry.pipeline_entry_id == entry.id,
                ContextEntry.deleted_at.is_(None),
            )
            .order_by(ContextEntry.date.desc())
            .limit(50)
        )
        entries = result.scalars().all()

        # Build a lookup map for source attribution
        entry_map = {str(entry.id): entry for entry in entries}

        # Sparse-data guard — no LLM call
        if len(entries) < _MIN_CONTEXT_ENTRIES:
            return {
                "answer": (
                    "Not enough context to answer questions about this relationship. "
                    "Add more notes or interactions first."
                ),
                "sources": [],
                "insufficient_context": True,
            }

        # Build system prompt with source attribution instructions
        system_prompt = (
            "You are answering questions about a business relationship. "
            "Use ONLY the context provided. "
            "When citing information, include [source:{entry_id}] markers referencing "
            "the context entry UUID that contains the information."
        )

        # Build user content: each entry formatted with its ID
        entry_lines = []
        for entry in entries:
            entry_lines.append(
                f"[ID: {entry.id}] [{entry.date}] [{entry.source}] {entry.content}"
            )
        context_block = "\n\n".join(entry_lines)
        user_content = f"{context_block}\n\nQuestion: {question}"

        # Call LLM via circuit breaker
        if not anthropic_breaker.can_execute():
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable",
            )

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
            response = await client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            anthropic_breaker.record_success()
            response_text = response.content[0].text.strip()
        except Exception:
            anthropic_breaker.record_failure()
            raise

        # Parse [source:UUID] markers from response text
        source_pattern = re.compile(r"\[source:([0-9a-f-]{36})\]", re.IGNORECASE)
        matched_ids = set(source_pattern.findall(response_text))

        # Build structured sources list from matched entry IDs
        sources = []
        for entry_id in matched_ids:
            entry = entry_map.get(entry_id)
            if entry is not None:
                sources.append(
                    {
                        "id": str(entry.id),
                        "source": entry.source,
                        "date": str(entry.date),
                    }
                )

        return {
            "answer": response_text,
            "sources": sources,
            "insufficient_context": False,
        }
