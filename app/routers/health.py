"""
Health check endpoint.

GET /health — returns service status, DB/Redis connectivity,
per-store last event timestamp, and stale feed warnings.
Satisfies FR-A06.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.health import check_health

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Service health check.
    Returns 200 if healthy, 503 if degraded.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await check_health(db)
    result["trace_id"] = trace_id

    status_code = 200 if result["status"] == "healthy" else 503

    return JSONResponse(content=result, status_code=status_code)
