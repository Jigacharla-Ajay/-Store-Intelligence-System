"""
Metrics endpoint.

GET /stores/{store_id}/metrics — real-time store analytics.
Query params: window_minutes (default 1440), from, to.
Satisfies FR-A02.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.metrics import compute_metrics

router = APIRouter(tags=["Metrics"])


@router.get("/stores/{store_id}/metrics")
async def get_metrics(
    request: Request,
    store_id: str,
    window_minutes: int = Query(1440, ge=1, le=43200, description="Time window in minutes"),
    from_time: Optional[datetime] = Query(None, alias="from", description="Start time (ISO-8601)"),
    to_time: Optional[datetime] = Query(None, alias="to", description="End time (ISO-8601)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get real-time metrics for a store.
    Zero visitors returns 0 counts and rate=0.0 (never null or crash).
    Staff events are excluded from all customer metrics.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await compute_metrics(
        db=db,
        store_id=store_id,
        window_minutes=window_minutes,
        from_time=from_time,
        to_time=to_time,
    )
    result["trace_id"] = trace_id

    return JSONResponse(content=result, status_code=200)
