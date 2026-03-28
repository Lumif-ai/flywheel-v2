"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# Configure application logging so worker/engine messages are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from flywheel.api.agent_ws import router as agent_ws_router
from flywheel.api.admin import router as admin_router
from flywheel.api.graph import router as graph_router
from flywheel.api.auth import router as auth_router
from flywheel.api.chat import router as chat_router
from flywheel.api.context import router as context_router
from flywheel.api.files import router as files_router
from flywheel.api.focus import router as focus_router
from flywheel.api.learning import router as learning_router
from flywheel.api.errors import register_error_handlers
from flywheel.api.health import router as health_router
from flywheel.api.integrations import router as integrations_router
from flywheel.api.slack_events import router as slack_events_router
from flywheel.api.onboarding import router as onboarding_router
from flywheel.api.skills import router as skills_router
from flywheel.api.documents import router as documents_router
from flywheel.api.briefing import router as briefing_router
from flywheel.api.email import router as email_router
from flywheel.api.streams import router as streams_router
from flywheel.api.profile import router as profile_router
from flywheel.api.team_onboarding import router as team_onboarding_router
from flywheel.api.tenant import router as tenant_router
from flywheel.api.user import router as user_router
from flywheel.api.work_items import router as work_items_router
from flywheel.api.outreach import router as outreach_router
from flywheel.api.accounts import router as accounts_router
from flywheel.api.timeline import router as timeline_router
from flywheel.api.relationships import router as relationships_router
from flywheel.api.signals import router as signals_router
from flywheel.api.meetings import router as meetings_router
from flywheel.api.tasks import router as tasks_router
from flywheel.config import settings
from flywheel.middleware.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    queue_task = None
    cleaner_task = None
    calendar_sync_task = None
    cleanup_anon_task = None
    gmail_sync_task = None

    # Startup
    if settings.flywheel_backend == "postgres":
        # Validate required config before starting background workers
        missing = []
        if not settings.encryption_key:
            missing.append("ENCRYPTION_KEY")
        if not settings.google_client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not settings.google_client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if missing:
            import logging as _log
            _log.getLogger(__name__).warning(
                "Missing env vars: %s — integration OAuth and sync will not work",
                ", ".join(missing),
            )

        from flywheel.db.engine import get_engine

        # Verify DB connection
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )

        # Start background workers
        from flywheel.services.job_queue import job_queue_loop
        from flywheel.services.stale_job_cleaner import cleanup_stale_jobs

        from flywheel.services.calendar_sync import calendar_sync_loop
        from flywheel.services.anonymous_cleanup import anonymous_cleanup_loop
        from flywheel.services.gmail_sync import email_sync_loop

        queue_task = asyncio.create_task(job_queue_loop())
        cleaner_task = asyncio.create_task(cleanup_stale_jobs())
        calendar_sync_task = asyncio.create_task(calendar_sync_loop())
        cleanup_anon_task = asyncio.create_task(anonymous_cleanup_loop())
        gmail_sync_task = asyncio.create_task(email_sync_loop())

    yield

    # Shutdown
    for task in (queue_task, cleaner_task, calendar_sync_task, cleanup_anon_task, gmail_sync_task):
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    if settings.flywheel_backend == "postgres":
        from flywheel.db.engine import dispose_engine

        await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Initialize Sentry error tracking (conditional on DSN being set)
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )

    app = FastAPI(
        title="Flywheel",
        description="Knowledge compounding engine for AI-native teams",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Response compression — applies to all JSON responses > 500 bytes
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter (slowapi requires app.state.limiter)
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        retry_after = getattr(exc, "retry_after", 60)
        return JSONResponse(
            status_code=429,
            content={
                "error": "RateLimitExceeded",
                "message": str(exc.detail),
                "code": 429,
            },
            headers={"Retry-After": str(retry_after)},
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
    app.include_router(slack_events_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(files_router, prefix="/api/v1")
    app.include_router(learning_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(focus_router, prefix="/api/v1")
    app.include_router(streams_router, prefix="/api/v1")
    app.include_router(briefing_router, prefix="/api/v1")
    app.include_router(email_router, prefix="/api/v1")
    app.include_router(team_onboarding_router, prefix="/api/v1")
    app.include_router(profile_router, prefix="/api/v1")
    app.include_router(agent_ws_router, prefix="/api/v1")
    app.include_router(outreach_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(timeline_router, prefix="/api/v1")
    app.include_router(relationships_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(meetings_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")

    return app


app = create_app()
