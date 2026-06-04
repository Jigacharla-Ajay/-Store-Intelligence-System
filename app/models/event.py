"""
Pydantic v2 models for event ingestion.

Accepts multiple flexible schemas (from the actual sample_events.jsonl)
and normalizes them in the ingestion service.
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class EventModel(BaseModel):
    """Flexible event model that accepts the old schema and the new polymorphic schemas."""
    event_type: str = Field(..., description="Event type string")
    
    # Old Schema
    event_id: Optional[str] = None
    store_id: Optional[str] = None
    camera_id: Optional[str] = None
    visitor_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = 1.0
    metadata: dict = Field(default_factory=dict)

    # New Entry/Exit Schema
    id_token: Optional[str] = None
    store_code: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    gender_pred: Optional[str] = None
    age_pred: Optional[int] = None
    age_bucket: Optional[str] = None
    is_face_hidden: Optional[bool] = None
    group_id: Optional[str] = None
    group_size: Optional[int] = None
    
    # New Zone Schema
    track_id: Optional[Any] = None
    event_time: Optional[datetime] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    is_revenue_zone: Optional[str] = None
    zone_hotspot_x: Optional[float] = None
    zone_hotspot_y: Optional[float] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    
    # New Queue Schema
    queue_event_id: Optional[str] = None
    queue_join_ts: Optional[datetime] = None
    queue_served_ts: Optional[datetime] = None
    queue_exit_ts: Optional[datetime] = None
    wait_seconds: Optional[int] = None
    queue_position_at_join: Optional[int] = None
    abandoned: Optional[bool] = None

    model_config = {"extra": "allow"}


class IngestRequest(BaseModel):
    """Batch ingest request — max 500 events."""
    events: List[EventModel] = Field(..., max_length=500)


class IngestErrorDetail(BaseModel):
    index: int
    event_id: str
    reason: str

class IngestError(BaseModel):
    """Error detail for a rejected event."""
    index: int
    event_id: str
    reason: str
