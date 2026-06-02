"""
Anomalies endpoint.

GET /stores/{store_id}/anomalies — active anomaly detection.
Satisfies FR-A05.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.anomalies import detect_anomalies

router = APIRouter(tags=["Anomalies"])


@router.get("/stores/{store_id}/anomalies")
async def get_anomalies(
    request: Request,
    store_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get active anomalies for a store.
    Returns empty array when no anomalies detected.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await detect_anomalies(db=db, store_id=store_id)
    result["trace_id"] = trace_id

    return JSONResponse(content=result, status_code=200)
