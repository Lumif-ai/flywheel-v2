"""Global exception handlers for consistent error response format.

All error responses return: {"error": str, "message": str, "code": int}

Registered AFTER CORSMiddleware so error responses also include CORS headers.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": type(exc).__name__,
                "message": str(exc.detail),
                "code": exc.status_code,
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "message": str(exc.errors()),
                "code": 422,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalError",
                "message": f"{type(exc).__name__}: {exc}",
                "code": 500,
            },
        )
