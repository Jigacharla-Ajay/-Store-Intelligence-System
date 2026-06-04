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
from pydantic import BaseModel

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
            # Normalize fields
            raw_type = getattr(event, "event_type", "").upper()
            
            # Map new types to our DB enum
            event_type = raw_type
            if raw_type == "ENTRY": event_type = "ENTRY"
            elif raw_type == "EXIT": event_type = "EXIT"
            elif raw_type == "ZONE_ENTERED": event_type = "ZONE_ENTER"
            elif raw_type == "ZONE_EXITED": event_type = "ZONE_EXIT"
            elif raw_type == "QUEUE_COMPLETED": event_type = "ZONE_EXIT"
            elif raw_type == "QUEUE_ABANDONED": event_type = "BILLING_QUEUE_ABANDON"
            
            event_id = getattr(event, "event_id", None) or getattr(event, "queue_event_id", None) or str(uuid.uuid4())
            store_id = getattr(event, "store_id", None) or getattr(event, "store_code", None) or "UNKNOWN"
            camera_id = getattr(event, "camera_id", None) or "UNKNOWN"
            
            visitor_id = getattr(event, "visitor_id", None) or getattr(event, "id_token", None) or getattr(event, "track_id", None)
            if visitor_id is not None:
                visitor_id = str(visitor_id)
            else:
                visitor_id = "UNKNOWN"
                
            timestamp = getattr(event, "timestamp", None) or getattr(event, "event_timestamp", None) or getattr(event, "event_time", None) or getattr(event, "queue_exit_ts", None)
            if not timestamp:
                timestamp = datetime.now(timezone.utc)
                
            zone_id = getattr(event, "zone_id", None)
            if zone_id:
                zu = zone_id.upper()
                if "BILLING" in zu:
                    zone_id = "BILLING"
                elif "SKINCARE" in zu:
                    zone_id = "SKINCARE"
                elif "MAKEUP" in zu:
                    zone_id = "MAKEUP"
                elif "BATH" in zu:
                    zone_id = "BATH_BODY"
            
            # Extract dwell_ms if available
            dwell_ms = getattr(event, "dwell_ms", 0)
            wait_seconds = getattr(event, "wait_seconds", None)
            if wait_seconds is not None:
                dwell_ms = int(wait_seconds * 1000)
                
            is_staff = getattr(event, "is_staff", False)
            confidence = float(getattr(event, "confidence", 1.0))
            
            # Manual validation to prevent DB IntegrityError rollback
            valid_types = ("ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL", 
                           "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY")
            if event_type not in valid_types:
                raise ValueError(f"event_type '{event_type}' is not valid.")
            if not (0.0 <= confidence <= 1.0):
                raise ValueError(f"confidence {confidence} must be between 0 and 1.")
            
            metadata = getattr(event, "metadata", {})
            if isinstance(metadata, BaseModel):
                metadata = metadata.model_dump()

            # Pass the normalized data via a temporary dictionary or directly to Event
            
            # Check if event already exists (idempotent check)
            existing = await db.execute(
                select(Event.event_id).where(Event.event_id == event_id)
            )
            if existing.scalar_one_or_none() is not None:
                duplicates += 1
                continue

            # Build event record
            event_record = Event(
                event_id=event_id,
                store_id=store_id,
                camera_id=camera_id,
                visitor_id=visitor_id,
                event_type=event_type,
                timestamp=timestamp,
                zone_id=zone_id,
                dwell_ms=dwell_ms,
                is_staff=is_staff,
                confidence=confidence,
                event_metadata=metadata,
                ingested_at=datetime.now(timezone.utc),
            )
            db.add(event_record)
            await db.flush()

            # Pass the original event and normalized timestamp to session state
            setattr(event, "_norm_event_type", event_type)
            setattr(event, "_norm_timestamp", timestamp)
            setattr(event, "_norm_visitor_id", visitor_id)
            setattr(event, "_norm_store_id", store_id)
            setattr(event, "_norm_zone_id", zone_id)
            setattr(event, "_norm_dwell_ms", dwell_ms)

            # Update session state based on event type
            await _update_session_state(db, event)

            accepted += 1

        except Exception as e:
            rejected += 1
            # Retrieve the local event_id if defined, else fallback to event.event_id
            err_id = locals().get("event_id") or getattr(event, "event_id", "unknown")
            errors.append({
                "index": idx,
                "event_id": str(err_id),
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
    is_staff = getattr(event, "is_staff", False)
    if is_staff:
        # Staff events don't create sessions
        return

    event_type = getattr(event, "_norm_event_type")
    timestamp = getattr(event, "_norm_timestamp")
    visitor_id = getattr(event, "_norm_visitor_id")
    store_id = getattr(event, "_norm_store_id")

    if event_type == "ENTRY":
        # Create a new session for this visitor
        session = Session(
            session_id=str(uuid.uuid4()),
            visitor_id=visitor_id,
            store_id=store_id,
            entry_at=timestamp,
            session_seq=1,
        )
        db.add(session)
        await db.flush()

    elif event_type == "EXIT":
        # Close the most recent open session for this visitor
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == visitor_id,
                Session.store_id == store_id,
                Session.exit_at.is_(None),
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session:
            session.exit_at = timestamp
            session.updated_at = datetime.now(timezone.utc)

    elif event_type == "REENTRY":
        # Find the last session for this visitor to get session_seq
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == visitor_id,
                Session.store_id == store_id,
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
            visitor_id=visitor_id,
            store_id=store_id,
            entry_at=timestamp,
            session_seq=next_seq,
        )
        db.add(new_session)
        await db.flush()

    elif event_type in ("ZONE_ENTER", "BILLING_QUEUE_JOIN"):
        # Find active session for this visitor
        result = await db.execute(
            select(Session)
            .where(
                Session.visitor_id == visitor_id,
                Session.store_id == store_id,
                Session.exit_at.is_(None),
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session:
            zone_id = getattr(event, "_norm_zone_id") or "BILLING"
            zone_visit = ZoneVisit(
                zone_visit_id=str(uuid.uuid4()),
                session_id=session.session_id,
                store_id=store_id,
                zone_id=zone_id,
                enter_at=timestamp,
            )
            db.add(zone_visit)
            await db.flush()

    elif event_type in ("ZONE_EXIT", "BILLING_QUEUE_ABANDON"):
        # If this is a new queue format event, it contains join and exit in one event
        queue_join_ts = getattr(event, "queue_join_ts", None)
        
        # Find the visitor's active session
        sess_result = await db.execute(
            select(Session.session_id)
            .where(
                Session.visitor_id == visitor_id,
                Session.store_id == store_id,
            )
            .order_by(Session.entry_at.desc())
            .limit(1)
        )
        session_id = sess_result.scalar_one_or_none()

        if session_id:
            zone_id = getattr(event, "_norm_zone_id") or "BILLING"
            
            if queue_join_ts:
                # Direct insertion of completed zone visit
                zone_visit = ZoneVisit(
                    zone_visit_id=str(uuid.uuid4()),
                    session_id=session_id,
                    store_id=store_id,
                    zone_id=zone_id,
                    enter_at=queue_join_ts,
                    exit_at=timestamp,
                    dwell_ms=getattr(event, "_norm_dwell_ms", 0)
                )
                db.add(zone_visit)
                await db.flush()
            else:
                # Close the most recent open zone_visit for this visitor/zone
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
                    zone_visit.exit_at = timestamp
                    # Compute dwell_ms
                    enter_at = zone_visit.enter_at
                    exit_at = timestamp
                    if hasattr(enter_at, 'tzinfo') and enter_at.tzinfo is None:
                        from datetime import timezone as tz
                        enter_at = enter_at.replace(tzinfo=tz.utc)
                    if hasattr(exit_at, 'tzinfo') and exit_at.tzinfo is None:
                        from datetime import timezone as tz
                        exit_at = exit_at.replace(tzinfo=tz.utc)
                    delta = exit_at - enter_at
                    zone_visit.dwell_ms = int(delta.total_seconds() * 1000)
