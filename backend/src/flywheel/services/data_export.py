"""Tenant data export as ZIP of JSON files.

Sync path: estimated size < 100MB -> stream ZIP directly in response.
Large datasets (>= 100MB) are rejected with 413 -- async export pipeline
(Supabase Storage upload + email notification) is deferred to a future phase.

Public API:
    estimate_export_size(tenant_id, db) -> int  (bytes, approximate)
    generate_export_zip(tenant_id, db) -> io.BytesIO
"""

import io
import json
import zipfile
import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextEntry, SkillRun, WorkItem, Integration

SIZE_THRESHOLD = 100_000_000  # 100MB


async def estimate_export_size(tenant_id: UUID, db: AsyncSession) -> int:
    """Estimate export size in bytes based on row counts and average sizes.

    Uses row count heuristic with conservative per-row estimates.
    """
    # Approximate: count rows * average bytes per row
    # Context entries are typically the largest table
    entry_count = await db.scalar(
        select(func.count()).select_from(ContextEntry)
    ) or 0
    run_count = await db.scalar(
        select(func.count()).select_from(SkillRun)
    ) or 0
    item_count = await db.scalar(
        select(func.count()).select_from(WorkItem)
    ) or 0

    # Rough estimates: entries ~2KB avg, runs ~5KB avg (includes output), items ~1KB avg
    estimated = (entry_count * 2048) + (run_count * 5120) + (item_count * 1024)
    return estimated


async def generate_export_zip(tenant_id: UUID, db: AsyncSession) -> io.BytesIO:
    """Generate a ZIP file containing all tenant data as JSON files.

    The db session should be tenant-scoped (RLS filters to tenant_id automatically).
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        now = datetime.datetime.now(datetime.timezone.utc)

        # Metadata
        zf.writestr("export_metadata.json", json.dumps({
            "tenant_id": str(tenant_id),
            "exported_at": now.isoformat(),
            "format_version": "1.0",
        }, indent=2))

        # Context entries
        entries = (await db.execute(select(ContextEntry))).scalars().all()
        zf.writestr("context_entries.json", json.dumps([
            {
                "id": str(e.id),
                "file_name": e.file_name,
                "date": e.date.isoformat() if e.date else None,
                "source": e.source,
                "detail": e.detail,
                "confidence": e.confidence,
                "evidence_count": e.evidence_count,
                "content": e.content,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in entries
        ], indent=2, default=str))

        # Skill runs
        runs = (await db.execute(select(SkillRun))).scalars().all()
        zf.writestr("skill_runs.json", json.dumps([
            {
                "id": str(r.id),
                "skill_name": r.skill_name,
                "status": r.status,
                "input_text": r.input_text,
                "output": r.output,
                "rendered_html": r.rendered_html if hasattr(r, 'rendered_html') else None,
                "tokens_used": r.tokens_used,
                "cost_estimate": float(r.cost_estimate) if hasattr(r, 'cost_estimate') and r.cost_estimate else None,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ], indent=2, default=str))

        # Work items
        items = (await db.execute(select(WorkItem))).scalars().all()
        zf.writestr("work_items.json", json.dumps([
            {
                "id": str(w.id),
                "type": w.type,
                "title": w.title,
                "status": w.status,
                "data": w.data,
                "scheduled_at": w.scheduled_at.isoformat() if w.scheduled_at else None,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in items
        ], indent=2, default=str))

        # Integrations (if any)
        try:
            integrations = (await db.execute(select(Integration))).scalars().all()
            zf.writestr("integrations.json", json.dumps([
                {
                    "id": str(i.id),
                    "provider": i.provider,
                    "status": i.status,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in integrations
            ], indent=2, default=str))
        except Exception:
            # Integration model may not exist yet
            pass

    buf.seek(0)
    return buf
