"""Health check endpoint."""

from fastapi import APIRouter

from flywheel.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok", "backend": settings.flywheel_backend}
