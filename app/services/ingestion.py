"""
Event ingestion service.

Handles:
  - Pydantic validation of each event
  - Idempotent insert via ON CONFLICT DO NOTHING on event_id
  - Session state management (ENTRY → open, EXIT → close, REENTRY → increment)
  - Zone visit tracking (ZONE_ENTER → open, ZONE_EXIT → close with dwell_ms)
  - Tracks accepted/rejected/duplicate counts

Satisfies FR-A01 and FR-P03.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Event, Session, ZoneVisit
from app.services.ws_manager import ws_manager


async def ingest_events(db: AsyncSession, events: list) -> dict:
    """
    Process a batch of validated events.

    Returns dict with accepted, rejected, duplicate counts and error list.
    Idempotent: re-ingesting the same event_id is a no-op (counted as duplicate).
    """
    accepted = 0
    rejected = 0
    duplicates = 0
    errors = []

    for idx, event in enumerate(events):
        try:
            # Check if event already exists (idempotent check)
            existing = await db.execute(
                select(Event.event_id).where(Event.event_id == event.event_id)
            )
            if existing.scalar_one_or_none() is not None:
                duplicates += 1
                continue

            # Build event record
            event_record = Event(
                event_id=event.event_id,
                store_id=event.store_id,
                camera_id=event.camera_id,
                visitor_id=event.visitor_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                zone_id=event.zone_id,
                dwell_ms=event.dwell_ms,
                is_staff=event.is_staff,
                confidence=event.confidence,
                event_metadata=event.metadata.model_dump() if event.metadata else {},
                ingested_at=datetime.now(timezone.utc),
            )
            db.add(event_record)
            await db.flush()

            # Update session state based on event type
            await _update_session_state(db, event)

            accepted += 1

        except Exception as e:
            rejected += 1
            errors.append({
                "index": idx,
                "event_id": str(event.event_id),
                "reason": str(e),
            })

    # Commit all changes in one transaction
    await db.commit()

    # Broadcast accepted events
    if accepted > 0:
        store_groups = {}
        for idx, event in enumerate(events):
            # Only broadcast if it wasn't rejected
            if not any(e["index"] == idx for e in errors):
                store_groups.setdefault(event.store_id, []).append(
                    event.model_dump(mode="json")
                )
        
        for store_id, valid_events in store_groups.items():
            await ws_manager.broadcast_events(store_id, valid_events)

    return {
        "accepted": accepted,
        "rejected": rejected,
        "duplicate": duplicates,
        "errors": errors,
    }


async def _update_session_state(db: AsyncSession, event) -> None:
    """
    Manage session lifecycle based on event type:
      ENTRY     → Create new session
      EXIT      → Close existing session (set exit_at)
      REENTRY   → Create new session with incremented session_seq
      ZONE_ENTER → Create zone_visit record
      ZONE_EXIT  → Close zone_visit record (set exit_at + dwell_ms)
      BILLING_QUEUE_JOIN → Create zone_visit for BILLING zone
      BILLING_QUEUE_ABANDON → Close BILLING zone_visit
    """
    if event.is_staff:
        # Staff events don't create sessions
        return

    if event.event_type == "ENTRY":
        # Create a new session for this visitor
        session = Session(
            session_id=str(uuid.uuid4()),
            visitor_id=event.visitor_id,
            store_id=event.store_id,
            entry_at=event.timestamp,
            session_seq=1,
        )
        db.add(session)
        await db.flush()

    elif event.event_type == "EXIT":
        # Close the most recent open session for this visitor
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == event.visitor_id,
                Session.store_id == event.store_id,
                Session.exit_at.is_(None),
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session:
            session.exit_at = event.timestamp
            session.updated_at = datetime.now(timezone.utc)

    elif event.event_type == "REENTRY":
        # Find the last session for this visitor to get session_seq
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == event.visitor_id,
                Session.store_id == event.store_id,
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        prev_session = result.scalar_one_or_none()
        next_seq = (prev_session.session_seq + 1) if prev_session else 1

        # Update reentry_count on the previous session
        if prev_session:
            prev_session.reentry_count += 1
            prev_session.updated_at = datetime.now(timezone.utc)

        # Create new session for the re-entry
        new_session = Session(
            session_id=str(uuid.uuid4()),
            visitor_id=event.visitor_id,
            store_id=event.store_id,
            entry_at=event.timestamp,
            session_seq=next_seq,
        )
        db.add(new_session)
        await db.flush()

    elif event.event_type in ("ZONE_ENTER", "BILLING_QUEUE_JOIN"):
        # Find active session for this visitor
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == event.visitor_id,
                Session.store_id == event.store_id,
                Session.exit_at.is_(None),
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session:
            zone_id = event.zone_id or "BILLING"
            zone_visit = ZoneVisit(
                zone_visit_id=str(uuid.uuid4()),
                session_id=session.session_id,
                store_id=event.store_id,
                zone_id=zone_id,
                enter_at=event.timestamp,
            )
            db.add(zone_visit)
            await db.flush()

    elif event.event_type in ("ZONE_EXIT", "BILLING_QUEUE_ABANDON"):
        # Close the most recent open zone_visit for this visitor/zone
        zone_id = event.zone_id or "BILLING"

        # Find the visitor's active session
        sess_result = await db.execute(
            select(Session.session_id)
            .where(
                Session.visitor_id == event.visitor_id,
                Session.store_id == event.store_id,
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session_id = sess_result.scalar_one_or_none()

        if session_id:
            zv_result = await db.execute(
                select(ZoneVisit)
                .where(
                    ZoneVisit.session_id == session_id,
                    ZoneVisit.zone_id == zone_id,
                    ZoneVisit.exit_at.is_(None),
                )
                .order_by(ZoneVisit.enter_at.desc())
                .limit(1)
            )
            zone_visit = zv_result.scalar_one_or_none()
            if zone_visit:
                zone_visit.exit_at = event.timestamp
                # Compute dwell_ms (handle naive/aware mismatch from SQLite)
                enter_at = zone_visit.enter_at
                exit_at = event.timestamp
                if hasattr(enter_at, 'tzinfo') and enter_at.tzinfo is None:
                    from datetime import timezone as tz
                    enter_at = enter_at.replace(tzinfo=tz.utc)
                if hasattr(exit_at, 'tzinfo') and exit_at.tzinfo is None:
                    from datetime import timezone as tz
                    exit_at = exit_at.replace(tzinfo=tz.utc)
                delta = exit_at - enter_at
                zone_visit.dwell_ms = int(delta.total_seconds() * 1000)
