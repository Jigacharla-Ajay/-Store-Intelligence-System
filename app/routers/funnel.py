"""
Funnel endpoint.

GET /stores/{store_id}/funnel — 4-stage conversion funnel.
Query param: date (default today, format YYYY-MM-DD).
Satisfies FR-A03.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.funnel import compute_funnel

router = APIRouter(tags=["Funnel"])


@router.get("/stores/{store_id}/funnel")
async def get_funnel(
    request: Request,
    store_id: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (default: today)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get 4-stage conversion funnel for a store.
    Stages: STORE_ENTRY -> ZONE_VISIT -> BILLING_REACH -> PURCHASE.
    Re-entries are deduplicated (visitor counted once).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await compute_funnel(db=db, store_id=store_id, date_str=date)
    result["trace_id"] = trace_id

    return JSONResponse(content=result, status_code=200)
