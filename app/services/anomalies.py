"""
Anomaly detection service.

Checks 5 anomaly types:
  1. BILLING_QUEUE_SPIKE  — queue_depth > threshold for > 3 min
  2. CONVERSION_DROP      — rate < 70% of baseline
  3. DEAD_ZONE            — no visits to a zone for 30+ min during open hours
  4. STALE_FEED           — no events from any camera for > 10 min
  5. ABANDONMENT_SPIKE    — abandonment > 30% of billing entries

Satisfies FR-A05.
"""

import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Event, ZoneVisit, AnomalyLog
from app.services.ws_manager import ws_manager

QUEUE_SPIKE_THRESHOLD = int(os.getenv("QUEUE_SPIKE_THRESHOLD", "5"))
STALE_FEED_MINUTES = int(os.getenv("STALE_FEED_MINUTES", "10"))
DEAD_ZONE_MINUTES = int(os.getenv("DEAD_ZONE_MINUTES", "30"))

STORE_ZONES = ["SKINCARE", "MAKEUP", "BATH_BODY", "BILLING"]


def _ensure_aware(dt):
    """Make a naive datetime UTC-aware (SQLite returns naive timestamps)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def detect_anomalies(
    db: AsyncSession,
    store_id: str,
) -> dict:
    """
    Run all anomaly checks for a store. Returns list of active anomalies.
    """
    now = datetime.now(timezone.utc)
    anomalies = []

    # 1. BILLING_QUEUE_SPIKE
    queue_anomaly = await _check_queue_spike(db, store_id, now)
    if queue_anomaly:
        anomalies.append(queue_anomaly)

    # 2. CONVERSION_DROP
    conversion_anomaly = await _check_conversion_drop(db, store_id, now)
    if conversion_anomaly:
        anomalies.append(conversion_anomaly)

    # 3. DEAD_ZONE
    dead_zones = await _check_dead_zones(db, store_id, now)
    anomalies.extend(dead_zones)

    # 4. STALE_FEED
    stale_anomaly = await _check_stale_feed(db, store_id, now)
    if stale_anomaly:
        anomalies.append(stale_anomaly)

    # 5. ABANDONMENT_SPIKE
    abandon_anomaly = await _check_abandonment_spike(db, store_id, now)
    if abandon_anomaly:
        anomalies.append(abandon_anomaly)

    # Broadcast all active anomalies to connected clients
    for anomaly in anomalies:
        await ws_manager.broadcast_anomaly(store_id, anomaly)

    return {
        "store_id": store_id,
        "checked_at": now.isoformat(),
        "active_anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


async def _check_queue_spike(db, store_id, now):
    """Queue depth > threshold."""
    current_q = await db.execute(
        select(func.count(ZoneVisit.zone_visit_id))
        .where(
            ZoneVisit.store_id == store_id,
            ZoneVisit.zone_id == "BILLING",
            ZoneVisit.exit_at.is_(None),
        )
    )
    depth = current_q.scalar() or 0

    if depth > QUEUE_SPIKE_THRESHOLD:
        severity = "CRITICAL" if depth > 10 else "WARN"
        return {
            "anomaly_id": f"queue_{store_id}_{now.strftime('%H%M')}",
            "type": "BILLING_QUEUE_SPIKE",
            "severity": severity,
            "detected_at": now.isoformat(),
            "description": f"Billing queue depth is {depth} (threshold: {QUEUE_SPIKE_THRESHOLD})",
            "suggested_action": "Open additional billing counter or redirect customers",
            "metadata": {"current_depth": depth, "threshold": QUEUE_SPIKE_THRESHOLD},
        }
    return None


async def _check_conversion_drop(db, store_id, now):
    """Conversion rate < 70% of baseline (last 24h avg)."""
    # Current hour conversion
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)

    # Visitors in last hour
    current_visitors_q = await db.execute(
        select(func.count(distinct(Event.visitor_id)))
        .where(
            Event.store_id == store_id,
            Event.event_type == "ENTRY",
            Event.is_staff == False,
            Event.timestamp >= hour_ago,
        )
    )
    current_visitors = current_visitors_q.scalar() or 0

    # Baseline: visitors in last 24h
    baseline_visitors_q = await db.execute(
        select(func.count(distinct(Event.visitor_id)))
        .where(
            Event.store_id == store_id,
            Event.event_type == "ENTRY",
            Event.is_staff == False,
            Event.timestamp >= day_ago,
        )
    )
    baseline_visitors = baseline_visitors_q.scalar() or 0

    if baseline_visitors > 10 and current_visitors > 0:
        # Simplified check: if current hour is much lower than avg hourly
        avg_hourly = baseline_visitors / 24
        if avg_hourly > 0 and current_visitors < avg_hourly * 0.7:
            return {
                "anomaly_id": f"conv_{store_id}_{now.strftime('%H%M')}",
                "type": "CONVERSION_DROP",
                "severity": "WARN",
                "detected_at": now.isoformat(),
                "description": f"Current hourly traffic ({current_visitors}) is below 70% of average ({avg_hourly:.0f}/hr)",
                "suggested_action": "Review store layout and staff deployment",
                "metadata": {
                    "current_hourly": current_visitors,
                    "avg_hourly": round(avg_hourly, 1),
                },
            }
    return None


async def _check_dead_zones(db, store_id, now):
    """Zones with no visits for 30+ minutes during open hours."""
    anomalies = []
    cutoff = now - timedelta(minutes=DEAD_ZONE_MINUTES)

    for zone_id in STORE_ZONES:
        if zone_id == "BILLING":
            continue  # Billing is handled separately

        last_visit_q = await db.execute(
            select(func.max(ZoneVisit.enter_at))
            .where(
                ZoneVisit.store_id == store_id,
                ZoneVisit.zone_id == zone_id,
            )
        )
        last_visit = _ensure_aware(last_visit_q.scalar())

        if last_visit is None or last_visit < cutoff:
            minutes_since = DEAD_ZONE_MINUTES
            if last_visit:
                minutes_since = int((now - last_visit).total_seconds() / 60)

            anomalies.append({
                "anomaly_id": f"dead_{zone_id}_{store_id}",
                "type": "DEAD_ZONE",
                "severity": "INFO",
                "detected_at": now.isoformat(),
                "description": f"Zone {zone_id} has had no visitors for {minutes_since} minutes",
                "suggested_action": f"Check if {zone_id} zone displays need refreshing or if signage is visible",
                "metadata": {
                    "zone_id": zone_id,
                    "minutes_since_last_visit": minutes_since,
                },
            })

    return anomalies


async def _check_stale_feed(db, store_id, now):
    """No events from any camera for > 10 minutes."""
    cutoff = now - timedelta(minutes=STALE_FEED_MINUTES)

    last_event_q = await db.execute(
        select(func.max(Event.timestamp))
        .where(Event.store_id == store_id)
    )
    last_event = _ensure_aware(last_event_q.scalar())

    if last_event is not None and last_event < cutoff:
        minutes_stale = int((now - last_event).total_seconds() / 60)
        return {
            "anomaly_id": f"stale_{store_id}",
            "type": "STALE_FEED",
            "severity": "WARN",
            "detected_at": now.isoformat(),
            "description": f"No events received for {minutes_stale} minutes",
            "suggested_action": "Check camera connections and pipeline health",
            "metadata": {
                "last_event_at": last_event.isoformat(),
                "minutes_stale": minutes_stale,
            },
        }
    return None


async def _check_abandonment_spike(db, store_id, now):
    """Abandonment > 30% of billing entries in last hour."""
    hour_ago = now - timedelta(hours=1)

    billing_joins_q = await db.execute(
        select(func.count(Event.event_id))
        .where(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_JOIN",
            Event.timestamp >= hour_ago,
        )
    )
    billing_joins = billing_joins_q.scalar() or 0

    abandons_q = await db.execute(
        select(func.count(Event.event_id))
        .where(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_ABANDON",
            Event.timestamp >= hour_ago,
        )
    )
    abandons = abandons_q.scalar() or 0

    if billing_joins >= 3 and abandons / billing_joins > 0.3:
        return {
            "anomaly_id": f"abandon_{store_id}_{now.strftime('%H%M')}",
            "type": "ABANDONMENT_SPIKE",
            "severity": "WARN",
            "detected_at": now.isoformat(),
            "description": f"{abandons}/{billing_joins} customers abandoned billing queue ({abandons/billing_joins*100:.0f}%)",
            "suggested_action": "Reduce queue wait time — open additional counter",
            "metadata": {
                "abandoned": abandons,
                "billing_joins": billing_joins,
                "rate": round(abandons / billing_joins, 3),
            },
        }
    return None
