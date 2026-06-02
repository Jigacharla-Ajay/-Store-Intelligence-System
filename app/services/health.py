"""
Health check service.

Checks DB connectivity, Redis connectivity, per-store feed staleness.
Satisfies FR-A06.
"""

import os
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# Track app start time for uptime calculation
APP_START_TIME = datetime.now(timezone.utc)

STALE_FEED_MINUTES = int(os.getenv("STALE_FEED_MINUTES", "10"))


async def check_health(db: AsyncSession, redis_client=None) -> dict:
    """
    Returns full health status.
    200 if healthy, 503 if degraded.
    """
    now = datetime.now(timezone.utc)
    uptime = int((now - APP_START_TIME).total_seconds())

    result = {
        "status": "healthy",
        "checked_at": now.isoformat(),
        "database": "connected",
        "redis": "connected",
        "stores": [],
        "uptime_seconds": uptime,
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        result["status"] = "degraded"
        result["database"] = "disconnected"
        result["error"] = "DATABASE_UNAVAILABLE"
        return result

    # Check Redis
    if redis_client is not None:
        try:
            await redis_client.ping()
        except Exception:
            result["status"] = "degraded"
            result["redis"] = "disconnected"
            result["error"] = "REDIS_UNAVAILABLE"
            return result
    else:
        result["redis"] = "not_configured"

    # Get per-store feed status
    try:
        from app.models.db import Store, Event
        from sqlalchemy import select, func

        # Get all stores
        stores_result = await db.execute(select(Store.store_id))
        store_ids = [row[0] for row in stores_result.fetchall()]

        for store_id in store_ids:
            # Get last event timestamp for this store
            last_event_result = await db.execute(
                select(func.max(Event.timestamp)).where(Event.store_id == store_id)
            )
            last_event_at = last_event_result.scalar_one_or_none()

            if last_event_at is None:
                result["stores"].append({
                    "store_id": store_id,
                    "last_event_at": None,
                    "lag_seconds": 0,
                    "feed_status": "NO_DATA",
                })
            else:
                # Ensure timezone-aware (SQLite returns naive)
                if last_event_at.tzinfo is None:
                    last_event_at = last_event_at.replace(tzinfo=timezone.utc)
                lag = int((now - last_event_at).total_seconds())
                feed_status = "STALE_FEED" if lag > STALE_FEED_MINUTES * 60 else "OK"
                result["stores"].append({
                    "store_id": store_id,
                    "last_event_at": last_event_at.isoformat(),
                    "lag_seconds": lag,
                    "feed_status": feed_status,
                })
    except Exception:
        pass  # Non-critical — health check still returns

    return result
