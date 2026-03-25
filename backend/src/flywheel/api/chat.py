"""Chat endpoint -- natural language routing via Haiku intent classification.

POST /chat accepts a user message, classifies intent using Haiku, and either:
- Creates a SkillRun and returns run_id + stream_url (action=execute)
- Returns a clarification prompt (action=clarify)
- Returns a no-match message (action=none)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.api.skills import _get_available_skills_db
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import SkillRun
from flywheel.middleware.rate_limit import check_anonymous_run_limit, check_concurrent_run_limit
from flywheel.services.circuit_breaker import anthropic_breaker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None  # [{role: "user"|"assistant", content: str}]
    stream_id: str | None = None
    briefing_id: str | None = None  # When set, injects briefing content as LLM context


class ChatResponse(BaseModel):
    action: str
    run_id: str | None = None
    stream_url: str | None = None
    skill_name: str | None = None
    message: str | None = None
    response: str | None = None  # Direct conversational response
    candidates: list[str] | None = None


@router.post("")
async def chat(
    body: ChatRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ChatResponse:
    """Classify user intent and route to the appropriate skill.

    Uses Haiku (fast, cheap) for classification with the platform's
    subsidized API key. If intent is 'execute', creates a SkillRun
    record and returns run_id + stream_url for SSE streaming.
    """
    # Circuit breaker gate -- if API is down, return graceful error
    if not anthropic_breaker.can_execute():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is temporarily unavailable. Please try again in a minute.",
        )

    # Resolve work stream context if stream_id provided
    stream_context: str | None = None
    if body.stream_id:
        from flywheel.services.stream_context import load_stream_context

        stream_context = await load_stream_context(body.stream_id, user.tenant_id, db)

    # Resolve briefing context if briefing_id provided
    briefing_context: str | None = None
    if body.briefing_id:
        from flywheel.services.briefing_context import load_briefing_context

        briefing_context = await load_briefing_context(body.briefing_id, db)

    # Classify intent via Haiku
    from flywheel.services.chat_orchestrator import classify_intent

    available_skills = await _get_available_skills_db(db, user.tenant_id)
    intent = await classify_intent(
        body.message,
        available_skills,
        history=body.history,
        stream_context=stream_context,
        briefing_context=briefing_context,
    )

    action = intent.get("action", "none")

    if action == "execute":
        # Rate limit checks (same as start_run)
        await check_anonymous_run_limit(user.sub, user.is_anonymous, db)
        await check_concurrent_run_limit(user.sub, db)

        # Validate skill exists
        skill_name = intent.get("skill_name", "")
        available_names = [s["name"] for s in available_skills]
        if skill_name not in available_names:
            return ChatResponse(
                action="none",
                message=f"Skill '{skill_name}' not found. Available: {', '.join(available_names)}",
            )

        input_text = intent.get("input_text", body.message)

        # Create SkillRun record
        run = SkillRun(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            skill_name=skill_name,
            input_text=input_text or None,
            status="pending",
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)
        await db.commit()

        # Store routing decision in events_log for reasoning trace builder.
        # Uses atomic JSONB append (|| operator) per decision [20-01].
        try:
            routing_event = {
                "event": "routing",
                "data": {
                    "action": intent.get("action"),
                    "confidence": intent.get("confidence"),
                    "skill_name": intent.get("skill_name"),
                },
            }
            await db.execute(
                sa_text("""
                    UPDATE skill_runs
                    SET events_log = events_log || CAST(:event AS jsonb)
                    WHERE id = :run_id
                """),
                {"run_id": str(run.id), "event": json.dumps([routing_event])},
            )
            await db.commit()
        except Exception as routing_err:
            logger.warning(
                "Failed to store routing event for run %s: %s", run.id, routing_err
            )

        return ChatResponse(
            action="execute",
            run_id=str(run.id),
            stream_url=f"/api/v1/skills/runs/{run.id}/stream",
            skill_name=skill_name,
        )

    elif action == "conversational":
        return ChatResponse(
            action="conversational",
            response=intent.get("response", "I'm here to help!"),
        )

    elif action == "clarify":
        return ChatResponse(
            action="clarify",
            message=intent.get("message", "Could you be more specific?"),
            candidates=intent.get("candidates", []),
        )

    else:
        # action == "none" or unknown
        return ChatResponse(
            action="none",
            message=intent.get("message", "I can help with skills like research, analysis, and more."),
        )
