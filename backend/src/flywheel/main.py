"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flywheel.api.auth import router as auth_router
from flywheel.api.context import router as context_router
from flywheel.api.errors import register_error_handlers
from flywheel.api.health import router as health_router
from flywheel.api.integrations import router as integrations_router
from flywheel.api.onboarding import router as onboarding_router
from flywheel.api.skills import router as skills_router
from flywheel.api.tenant import router as tenant_router
from flywheel.api.user import router as user_router
from flywheel.api.work_items import router as work_items_router
from flywheel.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # Startup
    if settings.flywheel_backend == "postgres":
        from flywheel.db.engine import get_engine

        # Verify DB connection
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
    yield
    # Shutdown
    if settings.flywheel_backend == "postgres":
        from flywheel.db.engine import dispose_engine

        await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Flywheel",
        description="Knowledge compounding engine for AI-native teams",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers (after CORS so error responses include CORS headers)
    register_error_handlers(app)

    # Routes
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(onboarding_router, prefix="/api/v1")
    app.include_router(tenant_router, prefix="/api/v1")
    app.include_router(user_router, prefix="/api/v1")
    app.include_router(context_router, prefix="/api/v1")
    app.include_router(work_items_router, prefix="/api/v1")
    app.include_router(integrations_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")

    return app


app = create_app()
