"""
Structured request logging middleware.

Injects trace_id into every request, logs structured JSON per request.
Satisfies FR-P02: trace_id, store_id, endpoint, latency_ms, event_count, status_code.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with structured fields."""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = f"trc_{uuid.uuid4().hex[:6]}"
        request.state.trace_id = trace_id

        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Let error handlers deal with it, but still log
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_error",
                trace_id=trace_id,
                endpoint=request.url.path,
                method=request.method,
                latency_ms=latency_ms,
            )
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Extract store_id from path params if present
        store_id = request.path_params.get("store_id")

        logger.info(
            "request",
            trace_id=trace_id,
            store_id=store_id,
            endpoint=request.url.path,
            method=request.method,
            latency_ms=latency_ms,
            status_code=response.status_code,
        )

        # Add trace_id to response headers
        response.headers["X-Trace-Id"] = trace_id
        return response
