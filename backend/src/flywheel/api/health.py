"""Health check endpoint."""

import httpx
from fastapi import APIRouter

from flywheel.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return service health status with database and storage checks."""
    status = {"status": "ok", "backend": settings.flywheel_backend}

    # Database connectivity check
    if settings.flywheel_backend == "postgres":
        try:
            from sqlalchemy import text

            from flywheel.db.engine import get_engine

            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            status["database"] = "connected"
        except Exception:
            status["status"] = "degraded"
            status["database"] = "disconnected"

    # Supabase Storage reachability check (production only to avoid
    # slowing down dev health checks)
    if settings.environment == "production" and settings.supabase_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.supabase_url}/storage/v1/bucket",
                    headers={
                        "Authorization": f"Bearer {settings.supabase_service_key}",
                        "apikey": settings.supabase_service_key,
                    },
                )
                if resp.status_code == 200:
                    buckets = [b["name"] for b in resp.json()]
                    status["storage"] = "connected"
                    status["storage_buckets"] = buckets
                    if "uploads" not in buckets:
                        status["storage_warning"] = "Required 'uploads' bucket not found"
                else:
                    status["status"] = "degraded"
                    status["storage"] = f"error ({resp.status_code})"
        except Exception:
            status["status"] = "degraded"
            status["storage"] = "unreachable"

    return status
