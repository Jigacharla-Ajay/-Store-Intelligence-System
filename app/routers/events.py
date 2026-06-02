"""
Event ingest endpoint.

POST /events/ingest — idempotent batch event ingestion.
Accepts up to 500 events. Returns 200 (all accepted), 207 (partial), or error.
Satisfies FR-A01.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.event import IngestRequest
from app.services.ingestion import ingest_events

router = APIRouter(tags=["Events"])


@router.post("/events/ingest")
async def ingest(
    request: Request,
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Idempotent batch event ingestion.

    - Accepts up to 500 events per batch.
    - Duplicate event_id values are silently skipped (counted as 'duplicate').
    - Returns 200 if all events accepted.
    - Returns 207 if some events rejected (partial success).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    result = await ingest_events(db, body.events)
    result["trace_id"] = trace_id

    # 207 Multi-Status if any rejections
    status_code = 207 if result["rejected"] > 0 else 200

    return JSONResponse(content=result, status_code=status_code)
