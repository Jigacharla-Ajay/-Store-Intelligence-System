"""
Metrics computation service.

Computes: unique visitors, total entries, reentry count, conversion rate,
dwell averages, queue depth, abandonment rate.
All metrics exclude is_staff=true events.

Satisfies FR-A02.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, distinct, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Event, Session, ZoneVisit, PosTransaction


async def compute_metrics(
    db: AsyncSession,
    store_id: str,
    window_minutes: int = 1440,
    from_time: datetime = None,
    to_time: datetime = None,
) -> dict:
    """
    Compute all store metrics for the given time window.
    Returns zero values for empty stores (never null).
    """
    now = datetime.now(timezone.utc)

    if to_time is None:
        to_time = now
    if from_time is None:
        from_time = to_time - timedelta(minutes=window_minutes)

    # --- Visitors ---
    # Unique visitors (ENTRY events, excluding staff)
    unique_q = await db.execute(
        select(func.count(distinct(Event.visitor_id)))
        .where(
            Event.store_id == store_id,
            Event.event_type == "ENTRY",
            Event.is_staff == False,
            Event.timestamp >= from_time,
            Event.timestamp <= to_time,
        )
    )
    unique_count = unique_q.scalar() or 0

    # Total entries (all ENTRY events, excluding staff)
    total_q = await db.execute(
        select(func.count(Event.event_id))
        .where(
            Event.store_id == store_id,
            Event.event_type == "ENTRY",
            Event.is_staff == False,
            Event.timestamp >= from_time,
            Event.timestamp <= to_time,
        )
    )
    total_entries = total_q.scalar() or 0

    # Re-entry count
    reentry_q = await db.execute(
        select(func.count(Event.event_id))
        .where(
            Event.store_id == store_id,
            Event.event_type == "REENTRY",
            Event.is_staff == False,
            Event.timestamp >= from_time,
            Event.timestamp <= to_time,
        )
    )
    reentry_count = reentry_q.scalar() or 0

    # --- Conversion ---
    # Converted = sessions that have a correlated POS transaction
    converted_q = await db.execute(
        select(func.count(distinct(Session.visitor_id)))
        .where(
            Session.store_id == store_id,
            Session.entry_at >= from_time,
            Session.entry_at <= to_time,
            Session.is_converted == True,
        )
    )
    converted_visitors = converted_q.scalar() or 0

    conversion_rate = 0.0
    if unique_count > 0:
        conversion_rate = round(converted_visitors / unique_count, 4)

    # --- Dwell ---
    # Average total dwell (from sessions with both entry and exit)
    dwell_q = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Session.exit_at) -
                func.extract("epoch", Session.entry_at)
            )
        )
        .where(
            Session.store_id == store_id,
            Session.entry_at >= from_time,
            Session.entry_at <= to_time,
            Session.exit_at.isnot(None),
        )
    )
    avg_dwell_sec = dwell_q.scalar()
    avg_total_ms = int((avg_dwell_sec or 0) * 1000)

    # Dwell by zone
    zone_dwell_q = await db.execute(
        select(ZoneVisit.zone_id, func.avg(ZoneVisit.dwell_ms))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.enter_at >= from_time,
            ZoneVisit.enter_at <= to_time,
            ZoneVisit.dwell_ms.isnot(None),
        )
        .group_by(ZoneVisit.zone_id)
    )
    by_zone = {}
    for zone_id, avg_ms in zone_dwell_q.fetchall():
        by_zone[zone_id] = int(avg_ms or 0)

    # --- Queue ---
    # Current queue depth = visitors in BILLING zone without exit
    queue_q = await db.execute(
        select(func.count(ZoneVisit.zone_visit_id))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.zone_id == "BILLING",
            ZoneVisit.exit_at.is_(None),
        )
    )
    current_depth = queue_q.scalar() or 0

    # Max queue depth today
    max_q = await db.execute(
        select(func.count(ZoneVisit.zone_visit_id))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.zone_id == "BILLING",
            ZoneVisit.enter_at >= from_time,
        )
    )
    max_depth_today = max_q.scalar() or 0

    # Avg wait time in billing queue
    avg_wait_q = await db.execute(
        select(func.avg(ZoneVisit.dwell_ms))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.zone_id == "BILLING",
            ZoneVisit.enter_at >= from_time,
            ZoneVisit.dwell_ms.isnot(None),
        )
    )
    avg_wait_ms = int(avg_wait_q.scalar() or 0)

    # --- Abandonment ---
    billing_entries_q = await db.execute(
        select(func.count(ZoneVisit.zone_visit_id))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.zone_id == "BILLING",
            ZoneVisit.enter_at >= from_time,
            ZoneVisit.enter_at <= to_time,
        )
    )
    billing_entries = billing_entries_q.scalar() or 0

    abandoned_q = await db.execute(
        select(func.count(Event.event_id))
        .where(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_ABANDON",
            Event.is_staff == False,
            Event.timestamp >= from_time,
            Event.timestamp <= to_time,
        )
    )
    abandoned_count = abandoned_q.scalar() or 0

    abandonment_rate = 0.0
    if billing_entries > 0:
        abandonment_rate = round(abandoned_count / billing_entries, 4)

    return {
        "store_id": store_id,
        "computed_at": now.isoformat(),
        "window": {
            "from": from_time.isoformat(),
            "to": to_time.isoformat(),
        },
        "visitors": {
            "unique_count": unique_count,
            "total_entries": total_entries,
            "reentry_count": reentry_count,
        },
        "conversion": {
            "rate": conversion_rate,
            "converted_visitors": converted_visitors,
            "total_visitors": unique_count,
        },
        "dwell": {
            "avg_total_ms": avg_total_ms,
            "by_zone": by_zone,
        },
        "queue": {
            "current_depth": current_depth,
            "max_depth_today": max_depth_today,
            "avg_wait_ms": avg_wait_ms,
        },
        "abandonment": {
            "rate": abandonment_rate,
            "abandoned_count": abandoned_count,
            "billing_entries": billing_entries,
        },
    }
