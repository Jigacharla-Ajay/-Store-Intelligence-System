"""
Event emitter — converts tracked person states into API events.

Monitors track state transitions to emit:
  - ENTRY when a person first appears on entry camera
  - EXIT when a tracked person disappears from entry camera
  - ZONE_ENTER when a person enters a new zone
  - ZONE_EXIT when a person leaves a zone
  - ZONE_DWELL periodic dwell updates
  - BILLING_QUEUE_JOIN when entering billing zone
  - BILLING_QUEUE_ABANDON when leaving billing without completion
  - REENTRY when a recently-exited person reappears
"""

import uuid
import time
from datetime import datetime, timezone
from collections import defaultdict

from pipeline.zone_mapper import get_zone, get_camera_type


# Track last known zones per visitor
_visitor_zones = defaultdict(lambda: None)
# Track exit timestamps for re-entry detection
_recent_exits = {}
REENTRY_WINDOW_SEC = 60


def emit_events(
    camera_id: str,
    current_tracks: list,
    previous_tracks: dict,
    store_id: str = "STORE_BLR_002",
) -> list:
    """
    Compare current tracks with previous frame's tracks to detect state changes.

    Args:
        camera_id: Camera identifier
        current_tracks: List of active tracks from tracker
        previous_tracks: Dict of {track_id: track_data} from previous frame
        store_id: Store identifier

    Returns:
        List of event dicts ready for API ingestion
    """
    events = []
    now = datetime.now(timezone.utc)
    cam_type = get_camera_type(camera_id)

    current_ids = {t["track_id"] for t in current_tracks}
    previous_ids = set(previous_tracks.keys())

    # New tracks (appeared in this frame)
    new_ids = current_ids - previous_ids
    for track in current_tracks:
        if track["track_id"] in new_ids:
            tid = track["track_id"]
            cx, cy = track["centroid"]
            zone = get_zone(camera_id, cx, cy)

            # Check for re-entry
            if tid in _recent_exits and (time.time() - _recent_exits[tid]) < REENTRY_WINDOW_SEC:
                events.append(_make_event(
                    store_id, camera_id, tid, "REENTRY",
                    now, zone, track["confidence"],
                ))
                del _recent_exits[tid]
            elif cam_type == "entry_exit":
                events.append(_make_event(
                    store_id, camera_id, tid, "ENTRY",
                    now, zone, track["confidence"],
                ))

            # Zone entry
            if zone and cam_type != "entry_exit":
                _visitor_zones[tid] = zone
                event_type = "BILLING_QUEUE_JOIN" if zone == "BILLING" else "ZONE_ENTER"
                events.append(_make_event(
                    store_id, camera_id, tid, event_type,
                    now, zone, track["confidence"],
                ))

    # Disappeared tracks (were in previous, not in current)
    lost_ids = previous_ids - current_ids
    for tid in lost_ids:
        prev_data = previous_tracks[tid]
        conf = prev_data.get("confidence", 0.8)

        if cam_type == "entry_exit":
            events.append(_make_event(
                store_id, camera_id, tid, "EXIT",
                now, None, conf,
            ))
            _recent_exits[tid] = time.time()

        # Zone exit
        old_zone = _visitor_zones.get(tid)
        if old_zone:
            event_type = "BILLING_QUEUE_ABANDON" if old_zone == "BILLING" else "ZONE_EXIT"
            events.append(_make_event(
                store_id, camera_id, tid, event_type,
                now, old_zone, conf,
            ))
            _visitor_zones[tid] = None

    # Zone transitions (track moved between zones)
    for track in current_tracks:
        tid = track["track_id"]
        if tid in new_ids:
            continue  # Already handled

        cx, cy = track["centroid"]
        new_zone = get_zone(camera_id, cx, cy)
        old_zone = _visitor_zones.get(tid)

        if new_zone != old_zone and new_zone is not None:
            # Exit old zone
            if old_zone:
                exit_type = "BILLING_QUEUE_ABANDON" if old_zone == "BILLING" else "ZONE_EXIT"
                events.append(_make_event(
                    store_id, camera_id, tid, exit_type,
                    now, old_zone, track["confidence"],
                ))

            # Enter new zone
            enter_type = "BILLING_QUEUE_JOIN" if new_zone == "BILLING" else "ZONE_ENTER"
            events.append(_make_event(
                store_id, camera_id, tid, enter_type,
                now, new_zone, track["confidence"],
            ))
            _visitor_zones[tid] = new_zone

    return events


def _make_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: datetime,
    zone_id: str,
    confidence: float,
    dwell_ms: int = 0,
) -> dict:
    """Create a standardized event dict."""
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.isoformat(),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": False,  # Staff classification applied separately
        "confidence": round(confidence, 3),
        "metadata": {"session_seq": 1},
    }
