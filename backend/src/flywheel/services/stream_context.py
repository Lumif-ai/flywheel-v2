"""Work stream context loader for chat orchestration.

Resolves a stream_id to contextual information that helps the orchestrator
make better routing decisions. For example, if the user is in a "Q2 Pipeline"
stream, the orchestrator knows to bias toward sales-related skills.

Phase 32 will implement actual work_streams table queries.
"""

from __future__ import annotations

from uuid import UUID


async def load_stream_context(stream_id: str, tenant_id: UUID) -> str | None:
    """Load work stream context for the orchestrator.

    Phase 32 will implement this with actual work_streams table queries.
    For now, returns None (no stream context available).

    Args:
        stream_id: The work stream identifier from the frontend.
        tenant_id: The tenant UUID for data isolation.

    Returns:
        A context string describing the work stream, or None if not found.
    """
    return None
