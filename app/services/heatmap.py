"""
Zone heatmap computation service.

Per zone: visit_count, avg_dwell_ms, visit_score (0-100), dwell_score (0-100).
Scores normalized relative to the highest zone. Zero-visit zones included with score 0.

Satisfies FR-A04.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ZoneVisit, Session

# Known store zones
STORE_ZONES = {
    "SKINCARE": "Skincare",
    "MAKEUP": "Makeup",
    "BATH_BODY": "Bath & Body",
    "BILLING": "Billing",
}

LOW_CONFIDENCE_THRESHOLD = 20  # sessions


async def compute_heatmap(
    db: AsyncSession,
    store_id: str,
    window_minutes: int = 60,
) -> dict:
    """
    Compute zone heatmap data with normalized scores.
    """
    now = datetime.now(timezone.utc)
    from_time = now - timedelta(minutes=window_minutes)

    # Query zone visit stats
    zone_stats_q = await db.execute(
        select(
            ZoneVisit.zone_id,
            func.count(ZoneVisit.zone_visit_id).label("visit_count"),
            func.avg(ZoneVisit.dwell_ms).label("avg_dwell_ms"),
        )
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.enter_at >= from_time,
        )
        .group_by(ZoneVisit.zone_id)
    )
    zone_data = {}
    for row in zone_stats_q.fetchall():
        zone_data[row[0]] = {
            "visit_count": row[1] or 0,
            "avg_dwell_ms": int(row[2] or 0),
        }

    # Count total sessions in the window (for confidence)
    session_count_q = await db.execute(
        select(func.count(Session.session_id))
        .where(
            Session.store_id == store_id,
            Session.entry_at >= from_time,
        )
    )
    total_sessions = session_count_q.scalar() or 0

    # Find max values for normalization
    max_visits = max((d["visit_count"] for d in zone_data.values()), default=0)
    max_dwell = max((d["avg_dwell_ms"] for d in zone_data.values()), default=0)

    # Build zone entries (include all known zones)
    zones = []
    for zone_id, label in STORE_ZONES.items():
        data = zone_data.get(zone_id, {"visit_count": 0, "avg_dwell_ms": 0})

        visit_score = 0
        if max_visits > 0:
            visit_score = int(round((data["visit_count"] / max_visits) * 100))

        dwell_score = 0
        if max_dwell > 0:
            dwell_score = int(round((data["avg_dwell_ms"] / max_dwell) * 100))

        zones.append({
            "zone_id": zone_id,
            "label": label,
            "visit_count": data["visit_count"],
            "avg_dwell_ms": data["avg_dwell_ms"],
            "visit_score": visit_score,
            "dwell_score": dwell_score,
        })

    # Data confidence
    confidence = "HIGH" if total_sessions >= LOW_CONFIDENCE_THRESHOLD else "LOW"

    return {
        "store_id": store_id,
        "window_minutes": window_minutes,
        "computed_at": now.isoformat(),
        "data_confidence": confidence,
        "zones": zones,
    }
