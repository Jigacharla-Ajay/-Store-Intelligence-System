"""
Global error handlers for the Store Intelligence API.

Ensures no raw stack traces ever reach HTTP responses (FR-P04).
All errors return structured JSON: {"error": "...", "detail": "...", "trace_id": "..."}
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError

logger = structlog.get_logger()


def register_error_handlers(app: FastAPI):
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(OperationalError)
    async def db_error_handler(request: Request, exc: OperationalError):
        """Database unavailable → 503 with structured body."""
        trace_id = getattr(request.state, "trace_id", "unknown")
        logger.error("database_unavailable", trace_id=trace_id, error=str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_UNAVAILABLE",
                "detail": "Storage layer is temporarily unavailable. Retry after 30s.",
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Pydantic validation error → 400 with structured body."""
        trace_id = getattr(request.state, "trace_id", "unknown")
        return JSONResponse(
            status_code=400,
            content={
                "error": "VALIDATION_ERROR",
                "detail": str(exc.errors()),
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Catch-all: 500, log full traceback internally, never expose it."""
        trace_id = getattr(request.state, "trace_id", "unknown")
        # Use print instead of structlog to avoid Windows encoding crashes
        import traceback
        print(f"[ERROR] trace_id={trace_id} error={repr(exc)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred.",
                "trace_id": trace_id,
            },
        )
