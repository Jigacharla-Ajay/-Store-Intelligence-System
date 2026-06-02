"""
Funnel computation service.

4-stage funnel: STORE_ENTRY -> ZONE_VISIT -> BILLING_REACH -> PURCHASE
Session-based (not raw events). Re-entries deduplicated by visitor_id.

Satisfies FR-A03.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Session, ZoneVisit, PosTransaction


async def compute_funnel(
    db: AsyncSession,
    store_id: str,
    date_str: str = None,
) -> dict:
    """
    Compute 4-stage conversion funnel for the given date.
    Deduplicates re-entries by counting unique visitor_ids at each stage.
    """
    now = datetime.now(timezone.utc)

    # Parse date or use today
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = now.date()
    else:
        target_date = now.date()

    # Time range for the date (full day)
    day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Stage 1: STORE_ENTRY — unique visitors who entered
    entry_q = await db.execute(
        select(func.count(distinct(Session.visitor_id)))
        .where(
            Session.store_id == store_id,
            Session.entry_at >= day_start,
            Session.entry_at < day_end,
        )
    )
    entry_count = entry_q.scalar() or 0

    # Stage 2: ZONE_VISIT — unique visitors who visited at least one zone
    zone_q = await db.execute(
        select(func.count(distinct(Session.visitor_id)))
        .select_from(Session)
        .join(ZoneVisit, ZoneVisit.session_id == Session.session_id)
        .where(
            Session.store_id == store_id,
            Session.entry_at >= day_start,
            Session.entry_at < day_end,
        )
    )
    zone_count = zone_q.scalar() or 0

    # Stage 3: BILLING_REACH — unique visitors who reached billing zone
    billing_q = await db.execute(
        select(func.count(distinct(Session.visitor_id)))
        .select_from(Session)
        .join(ZoneVisit, ZoneVisit.session_id == Session.session_id)
        .where(
            Session.store_id == store_id,
            Session.entry_at >= day_start,
            Session.entry_at < day_end,
            ZoneVisit.zone_id == "BILLING",
        )
    )
    billing_count = billing_q.scalar() or 0

    # Stage 4: PURCHASE — unique visitors who converted (have POS correlation)
    purchase_q = await db.execute(
        select(func.count(distinct(Session.visitor_id)))
        .where(
            Session.store_id == store_id,
            Session.entry_at >= day_start,
            Session.entry_at < day_end,
            Session.is_converted == True,
        )
    )
    purchase_count = purchase_q.scalar() or 0

    # Build funnel stages with dropoff percentages
    stages = _build_stages(entry_count, zone_count, billing_count, purchase_count)

    # Overall conversion
    overall_pct = 0.0
    if entry_count > 0:
        overall_pct = round((purchase_count / entry_count) * 100, 2)

    # Find largest dropoff stage
    largest_dropoff = ""
    max_dropoff = 0.0
    for s in stages:
        if s["dropoff_pct"] > max_dropoff:
            max_dropoff = s["dropoff_pct"]
            largest_dropoff = s["stage"]

    return {
        "store_id": store_id,
        "date": str(target_date),
        "funnel": stages,
        "overall_conversion_pct": overall_pct,
        "largest_dropoff_stage": largest_dropoff,
    }


def _build_stages(entry: int, zone: int, billing: int, purchase: int) -> list:
    """Build funnel stages with dropoff_pct at each transition."""
    counts = [
        ("STORE_ENTRY", "Store Entry", entry),
        ("ZONE_VISIT", "Zone Visit", zone),
        ("BILLING_REACH", "Billing Reach", billing),
        ("PURCHASE", "Purchase", purchase),
    ]

    stages = []
    for i, (stage_id, label, count) in enumerate(counts):
        dropoff = 0.0
        if i > 0 and counts[i - 1][2] > 0:
            prev_count = counts[i - 1][2]
            dropoff = round(((prev_count - count) / prev_count) * 100, 2)

        stages.append({
            "stage": stage_id,
            "label": label,
            "sessions": count,
            "dropoff_pct": max(dropoff, 0.0),  # Never negative
        })

    return stages
