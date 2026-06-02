"""
Heatmap endpoint.

GET /stores/{store_id}/heatmap — zone frequency and dwell heatmap.
Query param: window_minutes (default 60).
Satisfies FR-A04.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.heatmap import compute_heatmap

router = APIRouter(tags=["Heatmap"])


@router.get("/stores/{store_id}/heatmap")
async def get_heatmap(
    request: Request,
    store_id: str,
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get zone heatmap with visit counts and dwell scores (0-100).
    All known zones are included, even with 0 visits.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await compute_heatmap(db=db, store_id=store_id, window_minutes=window_minutes)
    result["trace_id"] = trace_id

    return JSONResponse(content=result, status_code=200)
